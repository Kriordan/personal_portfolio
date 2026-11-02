"""Durable AI replies on an explicitly disposable PostgreSQL database: claims, budget races, fencing, process death."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import select as io_select
import subprocess
import sys
import threading
from threading import Barrier
import time
import unittest
from uuid import uuid4

from sqlalchemy import event, text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.learning import interviewer
from project.learning.content_schema import load_catalog
from project.models import AIRequest, LearningAICharge, SessionMessage, User
from project.services import practice_budget, practice_service as service, practice_worker
from project.services.curriculum_service import import_catalog
from project.services.practice_worker import FakeProvider

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]
EXERCISE = "idempotent-order-api"
ALL_AT_ZERO = {"api": 0, "schema": 0, "algorithm": 0}
PRACTICE_TABLES = ("artifact_revision", "session_message", "session_message_artifact", "practice_receipt", "ai_request")
ORDERS = ("first", "second", "race")


def now():
    return datetime.now(timezone.utc)


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class PracticeReplyPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing destructive fixtures outside the isolated local test database")
        self.config = dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL, LEARNING_AI_ENABLED=True,
                           LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="practice1@example.test")
        self.app = create_app(self.config)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([User(id=i, username=f"practice{i}", email=f"practice{i}@example.test", email_verified=True)
                            for i in (1, 2)])
        db.session.commit()
        import_catalog(load_catalog(ROOT / "curriculum/idempotency/catalog.json"), dry_run=False, publish=True,
                       reviewed_by="Fixture reviewer", reviewed_on=date(2026, 10, 1))

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def user(self):
        return db.session.get(User, 1)

    def queue(self):
        """A session whose latest turn has a pending reply."""
        session_id = service.start_session(self.user(), exercise_id=EXERCISE, request_id=str(uuid4()))["session_id"]
        sent = service.send_turn(self.user(), session_id, body="Do keys expire?", expected_sequence=1,
                                 artifact_revisions=ALL_AT_ZERO, brief_revision=0, request_id=str(uuid4()))
        return session_id, sent["reply"]["id"]

    def claim(self):
        return service.claim_reply(now(), known_profiles=interviewer.PROFILES, worker_id="test")

    def status(self, reply_id):
        with db.engine.connect() as connection:
            return connection.execute(text("SELECT status, error_code, reply_message_id FROM ai_request WHERE id = :id"),
                                      {"id": reply_id}).one_or_none()

    def count(self, table, where="TRUE", **params):
        with db.engine.connect() as connection:
            return connection.execute(text(f"SELECT count(*) FROM {table} WHERE {where}"), params).scalar()

    def race(self, *operations):
        """Run each operation in its own app context from a shared starting line."""
        barrier = Barrier(len(operations))

        def run(operation):
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    return operation()
                except Exception as exc:
                    return exc
        with ThreadPoolExecutor(len(operations)) as pool:
            return [future.result(timeout=30) for future in [pool.submit(run, op) for op in operations]]

    def test_two_releases_claiming_at_once_claim_a_reply_once(self):
        _, reply_id = self.queue()
        second_app = create_app(self.config)  # the old and new dynos during a deploy

        def claim_in(app):
            def operation():
                with app.app_context():
                    return service.claim_reply(now(), known_profiles=interviewer.PROFILES, worker_id=str(id(app)))
            return operation
        results = self.race(claim_in(self.app), claim_in(second_app))
        claims = [result for result in results if result]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0][0], reply_id)
        self.assertEqual(self.status(reply_id).status, "running")

    def test_concurrent_reservations_never_exceed_the_cap(self):
        replies = [self.queue() for _ in range(2)]
        claims = [self.claim() for _ in replies]
        # Room for exactly one worst case: 1000 bytes at $2/M plus 100 tokens at $8/M is 2,800 micro-dollars.
        self.app.config["LEARNING_AI_MONTHLY_CAP_USD"] = 0.004

        def reserve(claim):
            return lambda: service.begin_call(*claim, purpose="reply", input_bytes=1000, max_output_tokens=100,
                                              deadline_seconds=60, now=now())
        results = self.race(*(reserve(claim) for claim in claims))
        self.assertEqual(sorted(type(result).__name__ for result in results), ["BudgetExhausted", "int"])
        spent = practice_budget.committed(practice_budget.period(now()))
        self.assertLessEqual(spent, 4_000)
        self.assertIs(type(spent), int)  # PostgreSQL sums bigint as numeric; JSON would get a string
        self.assertEqual(json.loads(json.dumps(service.ai_budget(1, now())))["spent_microusd"], spent)
        self.assertEqual(self.count("learning_ai_charge"), 1)

    def waits_on_a_lock(self):
        """Whether another connection to this database is waiting on a lock, polled for up to five seconds."""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with db.engine.connect() as connection:  # a new transaction each time: activity is a per-transaction snapshot
                if connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                                           "AND wait_event_type = 'Lock'")).scalar():
                    return True
            time.sleep(0.02)
        return False

    # Where the worker's next-call check is held: just before it share-locks the session row
    # (holding only the request row), or just before the budget lock (holding both rows).
    HOLD_POINTS = {"before the session lock": "FOR SHARE", "before the budget lock": "pg_advisory_xact_lock"}

    def during_call_check(self, claim, other, *, hold_before, call_now=None):
        """Hold the worker's next-call check at a lock, run `other`, then let the check finish.

        Returns the check's result, the other operation's result, and whether the other waited on a lock.
        Natural races rarely land in these windows, so they are forced.
        """
        holding, release = threading.Event(), threading.Event()
        results = {}

        def run(name, operation):
            with self.app.app_context():
                try:
                    results[name] = operation()
                except Exception as exc:
                    results[name] = exc
                finally:
                    db.session.remove()
        check = threading.Thread(target=run, args=("check", lambda: service.begin_call(
            *claim, purpose="reply", input_bytes=500, max_output_tokens=50, deadline_seconds=60,
            now=call_now or now())))
        rival = threading.Thread(target=run, args=("other", other))

        def hold(_connection, _cursor, statement, *_args):
            if threading.current_thread() is check and self.HOLD_POINTS[hold_before] in statement \
                    and not holding.is_set():
                holding.set()
                release.wait(15)
        event.listen(db.engine, "before_cursor_execute", hold)
        try:
            check.start()
            self.assertTrue(holding.wait(10))
            rival.start()
            waited = self.waits_on_a_lock()
            release.set()
            check.join(30)
            rival.join(30)
        finally:
            event.remove(db.engine, "before_cursor_execute", hold)
        return results.get("check"), results.get("other"), waited

    def test_a_delete_during_the_next_call_check_waits_its_turn(self):
        for hold_before in self.HOLD_POINTS:
            with self.subTest(hold_before=hold_before):
                session_id, reply_id = self.queue()
                claim = self.claim()
                charge, deleted, waited = self.during_call_check(
                    claim, lambda: service.delete_session(db.session.get(User, 1), session_id),  # noqa: B023
                    hold_before=hold_before)
                self.assertTrue(waited)
                self.assertIsInstance(charge, int)  # no deadlock: the check finished, then the delete
                self.assertEqual(deleted["session_id"], session_id)
                self.assertEqual(self.completion(claim)(), "fenced")
                service.finish_call(charge, outcome="settled", usage={"input_tokens": 100, "output_tokens": 10},
                                    now=now())
                self.assertEqual(sum(self.count(table, "practice_session_id = :id", id=session_id)
                                     for table in PRACTICE_TABLES), 0)
                self.assertEqual(self.count("learning_ai_charge", "reply_id = :id AND state = 'settled'",
                                            id=reply_id), 1)

    def test_a_pause_during_the_next_call_check_waits_until_the_call_has_started(self):
        for hold_before in self.HOLD_POINTS:
            with self.subTest(hold_before=hold_before):
                session_id, reply_id = self.queue()
                claim = self.claim()
                charge, paused, waited = self.during_call_check(
                    claim, lambda: service.set_status(db.session.get(User, 1), session_id,  # noqa: B023
                                                      status="paused", request_id=str(uuid4())),
                    hold_before=hold_before)
                self.assertTrue(waited)  # it can't slip in between the check's status read and its reservation
                self.assertIsInstance(charge, int)
                self.assertEqual(paused["status"], "paused")
                self.assertEqual(self.status(reply_id).status, "running")  # the call in flight finishes...
                self.assertEqual(self.completion(claim)(), "written")  # ...and its reply is kept

    def test_a_send_during_the_next_call_check_sees_the_lease_it_extended(self):
        for hold_before in self.HOLD_POINTS:
            with self.subTest(hold_before=hold_before):
                session_id, reply_id = self.queue()
                claim = self.claim()
                started = now()
                with db.engine.begin() as connection:  # the lease is about to run out
                    connection.execute(text("UPDATE ai_request SET lease_expires_at = :at WHERE id = :id"),
                                       {"at": started + timedelta(seconds=5), "id": reply_id})
                send = lambda: service.send_turn(  # noqa: E731,B023
                    db.session.get(User, 1), session_id, body="Are you there?", expected_sequence=2,
                    artifact_revisions=ALL_AT_ZERO, brief_revision=0, request_id=str(uuid4()),
                    now=started + timedelta(seconds=10))  # by the old lease, the reply is interrupted
                charge, sent, waited = self.during_call_check(claim, send, hold_before=hold_before,
                                                              call_now=started)
                self.assertTrue(waited)
                self.assertIsInstance(charge, int)
                self.assertIsInstance(sent, service.ReplyPendingError)  # not marked interrupted; no second reply
                self.assertEqual(self.status(reply_id).status, "running")
                self.assertEqual(self.count("ai_request", "practice_session_id = :id", id=session_id), 1)
                self.assertEqual(self.completion(claim)(), "written")

    def in_order(self, order, first, second):
        """Run two operations with `first` winning, `second` winning, or racing; returns both results.

        A forced order proves each outcome; the race proves the locking.
        """
        if order == "first":
            return first(), second()
        if order == "second":
            later = second()
            return first(), later
        return tuple(self.race(first, second))

    def completion(self, claim, body="A reply."):
        return lambda: service.complete_reply(*claim, body=body, now=now())

    def test_submission_and_reply_completion_require_an_up_to_date_transcript_in_every_order(self):
        from tests.test_practice_submissions import submission_input
        for order in ORDERS:
            with self.subTest(order=order):
                sid, _reply = self.queue()
                claim = self.claim()
                values = submission_input(service.session_detail(1, sid), '{}')
                db.session.commit()  # release any read transaction before concurrent workers

                def submit():
                    try:
                        return service.save_and_submit(self.user(), sid, **values)
                    except (service.StaleViewError, service.ReplyPendingError) as exc:
                        return exc

                completed, submitted = self.in_order(order, self.completion(claim), submit)
                self.assertEqual(completed, "written")
                self.assertIsInstance(submitted, (service.StaleViewError, service.ReplyPendingError))
                self.assertEqual(self.count("session_message", "kind = 'submission' AND practice_session_id = :id", id=sid), 0)
                fresh = submission_input(service.session_detail(1, sid), '{}')
                result = service.save_and_submit(self.user(), sid, **fresh)
                self.assertGreater(result["submission"]["turn_sequence"], values["expected_sequence"])

    def test_submission_obeys_lock_order_while_worker_checks_its_next_call(self):
        from tests.test_practice_submissions import submission_input
        for hold_before in self.HOLD_POINTS:
            with self.subTest(hold_before=hold_before):
                sid, _reply = self.queue()
                claim = self.claim()
                values = submission_input(service.session_detail(1, sid), '{}')
                db.session.commit()
                charge, submitted, waited = self.during_call_check(claim,
                    lambda: service.save_and_submit(self.user(), sid, **values), hold_before=hold_before)
                self.assertTrue(waited)
                self.assertIsInstance(charge, int)
                self.assertIsInstance(submitted, service.ReplyPendingError)
                self.assertEqual(self.count("session_message", "kind = 'submission' AND practice_session_id = :id", id=sid), 0)
                self.assertEqual(self.completion(claim)(), "written")

    def test_completion_and_delete_in_either_order_leave_nothing_behind(self):
        for order in ORDERS:
            with self.subTest(order=order):
                session_id, reply_id = self.queue()
                claim = self.claim()
                charge = service.begin_call(*claim, purpose="reply", input_bytes=500, max_output_tokens=50,
                                            deadline_seconds=60, now=now())
                service.finish_call(charge, outcome="settled", usage={"input_tokens": 100, "output_tokens": 10},
                                    now=now())
                delete = lambda: service.delete_session(db.session.get(User, 1), session_id)  # noqa: E731
                completed, _ = self.in_order(order, self.completion(claim), delete)
                self.assertEqual(completed, {"first": "written", "second": "fenced"}.get(order, completed))
                self.assertIn(completed, ("written", "fenced"))
                self.assertEqual(sum(self.count(table, "practice_session_id = :id", id=session_id)
                                     for table in PRACTICE_TABLES), 0)
                self.assertEqual(self.count("learning_ai_charge", "reply_id = :id", id=reply_id), 1)

    def test_a_pause_in_either_order_never_discards_a_returned_reply(self):
        for order in ORDERS:
            with self.subTest(order=order):
                session_id, reply_id = self.queue()
                claim = self.claim()
                pause = lambda: service.set_status(db.session.get(User, 1), session_id, status="paused",  # noqa: E731
                                                   request_id=str(uuid4()))
                completed, _ = self.in_order(order, self.completion(claim), pause)
                self.assertEqual((completed, self.status(reply_id).status), ("written", "completed"))

    def test_a_late_completion_and_the_sweep_in_either_order(self):
        for order in ORDERS:
            with self.subTest(order=order):
                _, reply_id = self.queue()
                claim = self.claim()
                with db.engine.begin() as connection:  # the lease has run out
                    connection.execute(text("UPDATE ai_request SET lease_expires_at = now() - interval '1 second' "
                                            "WHERE id = :id"), {"id": reply_id})
                sweep = lambda: service.sweep_replies(now())  # noqa: E731
                completed, _ = self.in_order(order, self.completion(claim, "A late reply."), sweep)
                self.assertEqual(completed, {"first": "written", "second": "fenced"}.get(order, completed))
                row = self.status(reply_id)
                if completed == "written":  # kept: nothing had marked it interrupted yet
                    self.assertEqual((row.status, row.reply_message_id is not None), ("completed", True))
                else:
                    self.assertEqual((completed, row.status, row.reply_message_id), ("fenced", "interrupted", None))
                self.assertEqual(self.count("session_message", "role = 'interviewer' AND body = 'A late reply.' "
                                            "AND practice_session_id = (SELECT practice_session_id FROM ai_request "
                                            "WHERE id = :id)", id=reply_id), 1 if completed == "written" else 0)

    def test_a_claim_and_a_pause_in_either_order_never_make_a_paid_call(self):
        for order in ORDERS:
            with self.subTest(order=order):
                session_id, reply_id = self.queue()
                pause = lambda: service.set_status(db.session.get(User, 1), session_id, status="paused",  # noqa: E731
                                                   request_id=str(uuid4()))
                claimed, _ = self.in_order(order, self.claim, pause)
                self.assertEqual(bool(claimed), {"first": True, "second": False}.get(order, bool(claimed)))
                if claimed:
                    with self.assertRaises(service.CallFenced):
                        service.begin_call(*claimed, purpose="reply", input_bytes=100, max_output_tokens=10,
                                           deadline_seconds=60, now=now())
                self.assertEqual(self.status(reply_id).status, "cancelled")
                self.assertEqual(self.count("learning_ai_charge", "reply_id = :id", id=reply_id), 0)

    def run_worker_until(self, stage):
        """Run one reply in a child process that stops at `stage` until killed."""
        script = f'''
from unittest.mock import patch
from project import create_app
from project.services import practice_service, practice_worker

class Provider:
    def call(self, body, *, deadline):
        usage = {{"input_tokens": 10, "output_tokens": 5}}
        if body["text"]["format"]["name"] == "interviewer_selector":
            return {{"output": practice_worker.fake_selection(body), "usage": usage}}
        if {stage!r} == "call":
            print("READY", flush=True)
            input()
        return {{"output": {{"reply": "A reply that is never stored."}}, "usage": usage}}

def stop_before_storing(*args, **kwargs):
    print("READY", flush=True)
    input()

with create_app({self.config!r}).app_context():
    with patch.object(practice_service, "complete_reply", stop_before_storing):
        practice_worker.run_once(Provider(), worker_id="doomed")
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"})
        try:
            self.assertTrue(io_select.select([child.stdout], [], [], 20)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
        finally:
            child.kill()  # kill -9: no cleanup runs
            child.communicate(timeout=10)

    def test_process_death_mid_call_or_before_storing_is_recovered_by_an_explicit_retry(self):
        for stage, first_charge in (("call", "reserved"), ("store", "settled")):
            with self.subTest(stage=stage):
                session_id, reply_id = self.queue()
                self.run_worker_until(stage)
                self.assertEqual(self.status(reply_id).status, "running")
                charges = {charge.purpose: charge.state for charge in LearningAICharge.query.filter_by(reply_id=reply_id)}
                # The selector call settled; the reply call's outcome is unknown, so its reservation keeps counting.
                self.assertEqual(charges, {"select": "settled", "reply": first_charge})
                with db.engine.begin() as connection:  # the dead process's lease runs out
                    connection.execute(text("UPDATE ai_request SET lease_expires_at = now() - interval '1 second' "
                                            "WHERE id = :id"), {"id": reply_id})
                retried = service.request_reply(self.user(), session_id, request_id=str(uuid4()))
                self.assertEqual(self.status(reply_id)[:2], ("interrupted", "lease_expired"))
                self.assertTrue(practice_worker.run_once(FakeProvider(), worker_id="recovered"))
                self.assertEqual(self.status(retried["reply"]["id"]).status, "completed")
                self.assertEqual(SessionMessage.query.filter_by(practice_session_id=session_id,
                                                                role="interviewer").count(), 2)  # opening + reply
                self.assertEqual(sorted(row.state for row in LearningAICharge.query.filter(
                    LearningAICharge.reply_id.in_([reply_id, retried["reply"]["id"]]))),
                    sorted([first_charge, "settled", "settled", "settled"]))

    def test_a_fresh_process_picks_up_a_reply_queued_before_a_restart(self):
        _, reply_id = self.queue()
        script = f'''
from project import create_app
from project.services import practice_worker
with create_app({self.config!r}).app_context():
    print(practice_worker.run_once(practice_worker.FakeProvider(), worker_id="restarted"))
'''
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=True,
                                env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"})
        self.assertEqual(result.stdout.strip().splitlines()[-1], "True")
        self.assertEqual(self.status(reply_id).status, "completed")


if __name__ == "__main__":
    unittest.main()
