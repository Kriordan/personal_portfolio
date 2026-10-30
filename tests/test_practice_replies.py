"""Durable AI replies (checkpoint 4a): SQLite with foreign keys on, an injected clock, and the scripted provider."""
import contextlib
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import event

from project import create_app
from project.curriculum_terms import CURRENT_PROFILES
from project.database import db
from project.learning import interviewer
from project.models import AIRequest, LearningAICharge, PracticeReceipt, SessionMessage, User
from project.services import practice_budget, practice_service as service, practice_signals, practice_worker
from project.services.learning_service import NotFoundError
from project.services.practice_worker import FakeProvider
from tests.test_practice_service import EXERCISE, SENTINELS, PracticeServiceCase, enable_sqlite_foreign_keys, seed_catalog

ALL_AT_ZERO = {"api": 0, "schema": 0, "algorithm": 0}
AI_CONFIG = dict(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="Fixture1@Example.test")
OPENAI_CONFIG = dict(LEARNING_AI_PROVIDER="openai", LEARNING_AI_MODEL="test-model")
OPENAI_PRICES = {("test-model", "default"): {"input": 1_000_000, "cached_input": 100_000, "output": 4_000_000}}


@contextlib.contextmanager
def without_learning_key():
    """No Learning key, whatever the developer's .env holds: importing the app loads .env."""
    with patch.dict(os.environ):
        os.environ.pop("LEARNING_OPENAI_API_KEY", None)
        yield


class Clock:
    def __init__(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def columns(rows):
    return json.dumps([{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows],
                      default=str)


class PracticeReplyCase(PracticeServiceCase):
    """AI on, user 1 the verified owner, the scripted provider, and a controllable clock."""

    def setUp(self):
        super().setUp()
        self.app.config.update(AI_CONFIG)
        self.user.email_verified = True
        db.session.commit()
        practice_signals.reply_queued.clear()
        self.clock = Clock()
        self.provider = FakeProvider()
        self.settings = service.ai_settings()

    def start(self, user=None, **kwargs):
        kwargs.setdefault("request_id", str(uuid4()))
        return service.start_session(user or self.user, exercise_id=EXERCISE, concept_id="idempotency",
                                     now=self.clock(), **kwargs)["session_id"]

    def save(self, session_id, edits, *, user=None, request_id=None):
        return service.save_work(user or self.user, session_id, edits=edits,
                                 request_id=request_id or str(uuid4()), now=self.clock())

    def send(self, session_id, body="Do keys expire?", *, user=None, request_id=None):
        user = user or self.user
        detail = service.session_detail(user.id, session_id, now=self.clock())
        return service.send_turn(user, session_id, body=body, expected_sequence=detail["messages"][-1]["sequence"],
                                 artifact_revisions={item["artifact_id"]: item["revision"] for item in detail["artifacts"]},
                                 brief_revision=detail["session_brief"]["revision"],
                                 request_id=request_id or str(uuid4()), now=self.clock())

    def ask(self, session_id, *, user=None, request_id=None):
        return service.request_reply(user or self.user, session_id, request_id=request_id or str(uuid4()),
                                     now=self.clock())

    def work(self, provider=None):
        return practice_worker.run_once(provider or self.provider, now=self.clock, worker_id="test")

    def claim(self):
        return service.claim_reply(self.clock(), known_profiles=interviewer.PROFILES, worker_id="test")

    def request(self, reply_id):
        return db.session.get(AIRequest, reply_id, populate_existing=True)

    def reply_state(self, session_id):
        return service.session_detail(1, session_id, now=self.clock())["reply"]


class PracticeReplyTests(PracticeReplyCase):
    def test_send_queues_a_reply_only_for_the_verified_owner_when_enabled(self):
        session_id = self.start()
        sent = self.send(session_id)
        self.assertEqual((sent["reply"]["status"], sent["latest_sequence"]), ("pending", 2))
        self.assertTrue(practice_signals.reply_queued.is_set())
        request = self.request(sent["reply"]["id"])
        self.assertEqual((request.status, request.kind, request.profile_version, request.provider, request.model),
                         ("pending", "reply", CURRENT_PROFILES["interviewer"], "fake", "fake-interviewer"))
        others = self.start(self.other)
        self.assertEqual(self.send(others, user=self.other)["reply"],
                         {"id": None, "status": "unavailable", "reason": "owner_only"})
        for change, reason in ((dict(LEARNING_AI_ENABLED=False), "disabled"),
                               (OPENAI_CONFIG, "disabled"),  # priced, but without LEARNING_OPENAI_API_KEY
                               (dict(LEARNING_AI_MODEL="unpriced-model"), "disabled"),
                               (dict(LEARNING_AI_OWNER_EMAIL=""), "owner_only")):
            with self.subTest(change=change), patch.dict(self.app.config, change), \
                    patch.dict(practice_budget.PRICES, OPENAI_PRICES), without_learning_key():
                self.assertEqual(self.send(self.start())["reply"]["reason"], reason)
        with patch.dict(self.app.config, OPENAI_CONFIG), patch.dict(practice_budget.PRICES, OPENAI_PRICES), \
                patch.dict(os.environ, {"LEARNING_OPENAI_API_KEY": "learning-test-key"}):
            self.assertIsNone(service.reply_unavailable(1, self.clock()))  # the key was all that was missing
        # An unverified owner, or an address that matches two accounts in different case, turns AI off.
        self.user.email_verified = False
        db.session.commit()
        self.assertEqual(service.reply_unavailable(1, self.clock()), "owner_only")
        self.user.email_verified = True
        db.session.add(User(id=3, username="twin", email="FIXTURE1@example.test", email_verified=True))
        db.session.commit()
        self.assertEqual(service.reply_unavailable(1, self.clock()), "owner_only")
        self.assertEqual(AIRequest.query.count(), 1)

    def test_openai_defaults_to_the_model_chosen_at_activation(self):
        with patch.dict(self.app.config, LEARNING_AI_PROVIDER="openai", LEARNING_AI_MODEL=None,
                        LEARNING_AI_SELECTOR_MODEL=None, LEARNING_AI_REASONING_EFFORT=None):
            settings = service.ai_settings()
            self.assertEqual((settings["model"], settings["selector_model"], settings["reasoning_effort"]),
                             ("gpt-6.1-sol", "gpt-6.1-sol", "low"))
            self.assertIsNotNone(practice_budget._rates("openai", settings["model"], settings["tier"])[0])
            with patch.dict(self.app.config, LEARNING_AI_MODEL="gpt-6-astra", LEARNING_AI_REASONING_EFFORT="medium"):
                self.assertEqual((service.ai_settings()["model"], service.ai_settings()["reasoning_effort"]),
                                 ("gpt-6-astra", "medium"))
        settings = service.ai_settings()  # the fake keeps its own model, and no reasoning setting
        self.assertEqual((settings["model"], settings["reasoning_effort"]), ("fake-interviewer", None))

    def test_the_worker_writes_a_reply_from_the_inputs_pinned_to_the_turn(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "PINNED_V1 POST /orders")])
        sent = self.send(session_id, "How long do clients retry?")
        # Editing during generation: the reply still reviews what the turn was sent with.
        self.save(session_id, [self.edit("api", "LATER_V2 POST /orders", base=1)])
        self.assertTrue(self.work())
        [selector], [body] = self.provider.selector_calls(), self.provider.reply_calls()
        self.assertIn("PINNED_V1", body["input"])
        self.assertNotIn("LATER_V2", body["input"])
        self.assertIs(body["store"], False)
        self.assertIn("INSTRUCTION_SENTINEL", body["instructions"])  # the provider needs the instructions
        serialized = json.dumps(body)
        for hidden in ("HIDDEN_SENTINEL", "HINT_SENTINEL", "EVALUATOR_SENTINEL", "clarification_cues", "Who owns the key"):
            self.assertNotIn(hidden, serialized)
        # The selector sees the message and the cues of what's still hidden: no facts, hints, or artifacts.
        self.assertEqual(json.loads(selector["input"])["message"], "How long do clients retry?")
        for private in ("HIDDEN_SENTINEL", "HINT_SENTINEL", "INSTRUCTION_SENTINEL", "EVALUATOR_SENTINEL",
                        "PINNED_V1", "2,000 order attempts"):
            self.assertNotIn(private, json.dumps(selector))
        detail = service.session_detail(1, session_id, now=self.clock())
        reply = detail["messages"][-1]
        self.assertEqual((reply["role"], reply["sequence"], reply["artifact_revisions"]),
                         ("interviewer", sent["sequence"] + 1, [{"artifact_id": "api", "revision": 1}]))
        self.assertEqual(detail["artifacts"][0]["revision"], 2)
        self.assertEqual((detail["reply"]["status"], detail["reply"]["answered"], detail["reply"]["can_request"]),
                         ("completed", True, False))
        charges = LearningAICharge.query.order_by(LearningAICharge.id).all()  # the selector's settles first
        self.assertEqual([(charge.state, charge.purpose, charge.reply_id, charge.pricing_version) for charge in charges],
                         [("settled", purpose, sent["reply"]["id"], "fake-1") for purpose in ("select", "reply")])
        self.assertTrue(all(charge.cost_microusd <= charge.reserved_microusd for charge in charges))
        self.assertFalse(self.work())

    def test_a_live_reply_refuses_a_send_and_a_stale_one_never_blocks(self):
        session_id = self.start()
        first = self.send(session_id)
        with self.assertRaises(service.ReplyPendingError):
            self.send(session_id, "again")
        self.clock.advance(self.settings["start_seconds"] + 1)  # no worker picked it up
        self.assertEqual(self.reply_state(session_id)["status"], "interrupted")
        second = self.send(session_id, "after the start deadline")
        self.assertEqual((self.request(first["reply"]["id"]).status, self.request(first["reply"]["id"]).error_code),
                         ("interrupted", "not_started"))
        self.assertIsNotNone(self.claim())  # then the process holding it dies
        with self.assertRaises(service.ReplyPendingError):
            self.send(session_id, "while it runs")
        self.clock.advance(self.settings["call_seconds"] + self.settings["lease_margin_seconds"] + 1)
        third = self.send(session_id, "after the lease")
        self.assertEqual((self.request(second["reply"]["id"]).status, self.request(second["reply"]["id"]).error_code),
                         ("interrupted", "lease_expired"))
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):  # switching AI off releases a pending reply
            self.assertEqual(self.reply_state(session_id)["error"], "disabled")
            self.assertEqual(self.send(session_id, "with AI off")["reply"]["reason"], "disabled")
        self.assertEqual(self.request(third["reply"]["id"]).status, "interrupted")
        self.assertEqual(SessionMessage.query.filter_by(role="learner", kind="turn").count(), 4)

    def test_pause_cancels_a_pending_reply_and_stops_a_running_one_before_its_next_call(self):
        session_id = self.start()
        sent = self.send(session_id)
        service.set_status(self.user, session_id, status="paused", request_id=str(uuid4()), now=self.clock())
        self.assertEqual((self.request(sent["reply"]["id"]).status, self.request(sent["reply"]["id"]).error_code),
                         ("cancelled", "paused"))
        self.assertFalse(self.work())
        asked = self.ask(session_id)
        self.assertEqual((asked["status"], asked["reply"]["status"]), ("active", "pending"))
        reply_id, token = self.claim()
        service.save_work(self.user, session_id, edits=[self.edit("api", "pausing")], request_id=str(uuid4()),
                          status="paused", now=self.clock())
        self.assertEqual(self.request(reply_id).status, "running")  # a call in flight isn't abandoned
        with self.assertRaises(service.CallFenced):
            service.begin_call(reply_id, token, purpose="reply", input_bytes=100, max_output_tokens=10,
                               deadline_seconds=60, now=self.clock())
        self.assertEqual((self.request(reply_id).status, self.request(reply_id).error_code), ("cancelled", "paused"))
        self.assertEqual(LearningAICharge.query.count(), 0)

    def test_delete_fences_a_late_reply_and_keeps_the_accounting(self):
        session_id = self.start()
        sent = self.send(session_id)
        reply_id, token = self.claim()
        charge = service.begin_call(reply_id, token, purpose="reply", input_bytes=1000, max_output_tokens=100,
                                    deadline_seconds=60, now=self.clock())
        service.delete_session(self.user, session_id)
        service.finish_call(charge, outcome="settled", usage={"input_tokens": 200, "output_tokens": 20}, now=self.clock())
        self.assertEqual(service.complete_reply(reply_id, token, body="too late", now=self.clock()), "fenced")
        self.assertIsNone(db.session.get(AIRequest, sent["reply"]["id"]))
        self.assertEqual(SessionMessage.query.filter_by(practice_session_id=session_id).count(), 0)
        settled = LearningAICharge.query.one()
        self.assertEqual((settled.state, settled.reply_id, settled.cost_microusd), ("settled", reply_id, 200 * 2 + 20 * 8))

    def test_each_failure_records_the_right_status_and_cost(self):
        expected = {"success": ("completed", None, "settled"), "fail": ("failed", "provider", "released"),
                    "lost": ("failed", "timeout", "reserved"), "invalid": ("failed", "invalid_output", "settled")}
        for mode, (status, code, state) in expected.items():
            with self.subTest(mode=mode):
                sent = self.send(self.start())
                with (self.assertLogs("project", "WARNING") if mode != "success" else contextlib.nullcontext()):
                    self.assertTrue(self.work(FakeProvider(mode)))
                request = self.request(sent["reply"]["id"])
                self.assertEqual((request.status, request.error_code), (status, code))
                charges = LearningAICharge.query.filter_by(reply_id=request.id).order_by(LearningAICharge.id).all()
                # A failing provider fails the selector call; otherwise both calls are made and paid for.
                self.assertEqual([charge.purpose for charge in charges],
                                 ["select"] if mode in ("fail", "lost") else ["select", "reply"])
                self.assertEqual(charges[-1].state, state)
                if state == "released":
                    self.assertEqual(charges[-1].cost_microusd, 0)
        # The lost call's reservation keeps counting: its outcome is unknown.
        lost = LearningAICharge.query.filter_by(state="reserved").one()
        settled = sum(charge.cost_microusd for charge in LearningAICharge.query.filter_by(state="settled"))
        self.assertEqual(practice_budget.committed(practice_budget.period(self.clock())),
                         settled + lost.reserved_microusd)

    def charge(self, microusd, state="settled"):
        """Another reply's charge this month: settled, or still reserved (in flight)."""
        row = LearningAICharge(
            user_id=1, reply_id=str(uuid4()), purpose="reply", period=practice_budget.period(self.clock()),
            provider="fake", model="fake-interviewer", service_tier="default", pricing_version="fake-1", state=state,
            reserved_microusd=microusd, cost_microusd=microusd if state == "settled" else None,
            expires_at=self.clock(), created_at=self.clock())
        db.session.add(row)
        db.session.commit()
        return row

    def cap(self, microusd):
        self.app.config["LEARNING_AI_MONTHLY_CAP_USD"] = microusd / 1_000_000

    def test_a_reply_is_queued_and_offered_only_when_its_worst_case_fits_the_month(self):
        session_id = self.start()
        smallest = self.settings["max_output_tokens"] * 8  # the fake model's output price: 8 micro-dollars a token
        self.cap(smallest + 1_000)  # room for a reply's output, but not for its input as well
        self.assertFalse(service.ai_budget(1, self.clock())["exhausted"])
        sent = self.send(session_id)
        self.assertEqual(sent["reply"], {"id": None, "status": "unavailable", "reason": "budget"})
        state = self.reply_state(session_id)
        self.assertEqual((state["status"], state["unavailable"], state["can_request"]), ("none", "budget", False))
        self.assertEqual(AIRequest.query.count(), 0)

        self.cap(60_000)
        self.assertTrue(self.reply_state(session_id)["can_request"])
        asked = self.ask(session_id)
        in_flight = self.charge(50_000, state="reserved")  # another session's call takes the room meanwhile
        with self.assertLogs("project", "WARNING"):
            self.assertTrue(self.work())
        self.assertEqual((self.request(asked["reply"]["id"]).status, self.request(asked["reply"]["id"]).error_code),
                         ("failed", "budget"))
        # The small selector call still fit; the reply's reservation didn't, so no reply call was made.
        self.assertEqual(([charge.purpose for charge in LearningAICharge.query.filter_by(reply_id=asked["reply"]["id"])],
                          len(self.provider.reply_calls())), (["select"], 0))
        state = self.reply_state(session_id)
        self.assertEqual((state["error"], state["unavailable"], state["can_request"]), ("budget", "budget", False))

        in_flight.state, in_flight.cost_microusd = "settled", 5_000  # it settles for less: room again
        db.session.commit()
        self.assertEqual((self.reply_state(session_id)["unavailable"], self.reply_state(session_id)["can_request"]),
                         (None, True))
        self.ask(session_id)
        self.assertTrue(self.work())
        self.assertTrue(self.reply_state(session_id)["answered"])

        spent = practice_budget.committed(practice_budget.period(self.clock()))
        self.assertIs(type(spent), int)
        self.cap(spent + smallest + 1)
        self.assertFalse(service.ai_budget(1, self.clock())["exhausted"])
        self.cap(spent + smallest)  # not even the smallest reply fits now
        budget = service.ai_budget(1, self.clock())
        self.assertEqual((budget["exhausted"], budget["spent_microusd"]), (True, spent))
        self.assertEqual(service.reply_unavailable(1, self.clock()), "budget")
        self.assertIsNone(service.session_detail(2, self.start(self.other), now=self.clock())["ai_budget"])
        self.clock.advance(40 * 86400)  # a new month starts fresh
        self.assertIsNone(service.reply_unavailable(1, self.clock()))

    def test_a_reply_whose_lease_ran_out_makes_no_call(self):
        session_id = self.start()
        self.send(session_id)
        reply_id, token = self.claim()
        self.clock.advance(self.settings["call_seconds"] + self.settings["lease_margin_seconds"] + 1)
        self.assertEqual(self.reply_state(session_id)["status"], "interrupted")
        with self.assertRaises(service.CallFenced):
            service.begin_call(reply_id, token, purpose="reply", input_bytes=100, max_output_tokens=10,
                               deadline_seconds=60, now=self.clock())
        self.assertEqual(LearningAICharge.query.count(), 0)

    def test_asking_for_a_reply_is_limited_to_the_latest_unanswered_turn(self):
        session_id = self.start()
        with self.assertRaises(service.PracticeValidationError):
            self.ask(session_id)  # nothing to answer yet
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):
            self.assertEqual(self.send(session_id)["reply"]["reason"], "disabled")
        self.assertTrue(self.reply_state(session_id)["can_request"])
        request_id = str(uuid4())
        asked = self.ask(session_id, request_id=request_id)
        self.assertEqual(asked["reply"]["status"], "pending")
        self.assertEqual(self.ask(session_id, request_id=request_id), asked)
        self.assertEqual(AIRequest.query.count(), 1)
        with self.assertRaises(service.ReplyPendingError):
            self.ask(session_id)
        with self.assertLogs("project", "WARNING"):
            self.work(FakeProvider("fail"))
        retried = self.ask(session_id)
        self.assertNotEqual(retried["reply"]["id"], asked["reply"]["id"])
        self.assertTrue(self.work())
        # Asked again from a page that missed the reply: it still saves, and nothing new is queued.
        late = service.request_reply(self.user, session_id, edits=[self.edit("api", "saved while asking")],
                                     request_id=str(uuid4()), now=self.clock())
        self.assertEqual((late["reply"], late["artifacts"]["api"]["revision"]),
                         ({"id": None, "status": "answered", "reason": None}, 1))
        self.assertEqual(AIRequest.query.count(), 2)
        with self.assertRaises(NotFoundError):
            self.ask(session_id, user=self.other)
        self.assertEqual(PracticeReceipt.query.filter_by(operation="reply").count(), 3)

    def test_the_worker_claims_only_fresh_replies_for_known_profiles(self):
        sent = self.send(self.start())
        request = self.request(sent["reply"]["id"])
        request.profile_version = "interviewer-99"  # written by a newer release during a deploy
        db.session.commit()
        self.assertFalse(self.work())
        self.assertEqual(self.request(sent["reply"]["id"]).status, "pending")
        self.clock.advance(self.settings["start_seconds"] + 1)
        self.assertFalse(self.work())
        self.assertEqual((self.request(sent["reply"]["id"]).status, self.request(sent["reply"]["id"]).error_code),
                         ("interrupted", "not_started"))

    def test_reply_text_is_normalized_and_bounded(self):
        for text, outcome in (("line one\r\nline two  ", "written"), ("bad\x00text", "invalid"),
                              ("x" * (service.REPLY_MAX_BYTES + 1), "invalid"), (" \n ", "invalid"), (None, "invalid")):
            with self.subTest(text=str(text)[:20]):
                self.send(self.start())
                reply_id, token = self.claim()
                self.assertEqual(service.complete_reply(reply_id, token, body=text, now=self.clock()), outcome)
                self.assertEqual(self.request(reply_id).status, "completed" if outcome == "written" else "failed")
        self.assertEqual(SessionMessage.query.filter_by(role="interviewer", kind="turn").filter(
            SessionMessage.body.like("line%")).one().body, "line one\nline two")

    def test_a_reply_landing_between_reads_shows_as_coming_rather_than_missing(self):
        session_id = self.start()
        self.send(session_id)
        claim = self.claim()
        real_turns = service._turns

        def reply_lands_first(session_key):
            service.complete_reply(*claim, body="landed between reads", now=self.clock())
            return real_turns(session_key)
        with patch.object(service, "_turns", side_effect=reply_lands_first):
            detail = service.session_detail(1, session_id, now=self.clock())
        self.assertEqual(detail["reply"]["status"], "running")  # the page keeps polling...
        self.assertEqual(detail["messages"][-1]["body"], "landed between reads")
        latest = detail["messages"][-1]["sequence"]
        settled = service.reply_updates(1, session_id, after=latest, now=self.clock())  # ...and the poll settles it
        self.assertEqual((settled["reply"]["status"], settled["turns"], settled["latest_sequence"]),
                         ("completed", [], latest))

    def test_requests_ledger_receipts_and_logs_hold_no_learner_text(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "ARTIFACT_SENTINEL")])
        self.send(session_id, "TURN_SENTINEL")
        self.work(FakeProvider(replies=["REPLY_SENTINEL"]))
        self.send(session_id, "SECOND_TURN_SENTINEL")
        with self.assertLogs("project", "WARNING") as logs:
            self.work(FakeProvider("fail"))
        stored = columns(AIRequest.query.all()) + columns(LearningAICharge.query.all()) + columns(PracticeReceipt.query.all())
        for sentinel in ("ARTIFACT_SENTINEL", "TURN_SENTINEL", "REPLY_SENTINEL") + SENTINELS:
            self.assertNotIn(sentinel, stored + "\n".join(logs.output))


class PracticeWorkerStartTests(unittest.TestCase):
    """Only the web entry point starts the worker thread, once."""

    def make_app(self, **config):
        return create_app({"TESTING": True, "SECRET_KEY": "fixture", "SQLALCHEMY_DATABASE_URI": "sqlite://",
                           **AI_CONFIG, **config})

    def test_creating_the_app_starts_no_thread(self):
        self.make_app()
        self.assertNotIn("learning-ai-worker", [thread.name for thread in threading.enumerate()])

    def test_the_start_conditions(self):
        app = self.make_app()
        self.assertTrue(practice_worker.should_start(app))
        app.debug = True
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": ""}):
            self.assertFalse(practice_worker.should_start(app))  # the reloader's watcher process
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "true"}):
            self.assertTrue(practice_worker.should_start(app))
        app.debug = False
        for change in (dict(LEARNING_AI_ENABLED=False), dict(LEARNING_AI_PROVIDER="openai")):  # OpenAI without its key
            with self.subTest(change=change), patch.dict(app.config, change), without_learning_key():
                self.assertFalse(practice_worker.should_start(app))

    def test_run_py_starts_the_worker_only_when_allowed(self):
        import run
        app = MagicMock()
        for allowed in (True, False):
            with self.subTest(allowed=allowed), patch.object(run, "create_app", return_value=app), \
                    patch.object(run.practice_worker, "should_start", return_value=allowed), \
                    patch.object(run.practice_worker, "start") as start:
                run.main()
                self.assertEqual(start.called, allowed)
                app.run.assert_called()

    def test_the_command_refuses_without_a_provider(self):
        app = self.make_app(LEARNING_AI_PROVIDER="openai")
        with without_learning_key():  # with a key, the command would start the worker loop
            result = app.test_cli_runner().invoke(args=["learning-worker"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No Learning AI provider", result.output)


class PracticeWorkerThreadTests(unittest.TestCase):
    """The real thread on a file database: the suite's in-memory SQLite is one shared connection."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture", **AI_CONFIG,
                                   SQLALCHEMY_DATABASE_URI=f"sqlite:///{Path(self.directory.name) / 'worker.sqlite'}"))
        self.context = self.app.app_context()
        self.context.push()
        event.listen(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()
        db.create_all()
        db.session.add_all([User(id=i, username=f"fixture{i}", email=f"fixture{i}@example.test", email_verified=True)
                            for i in (1, 2)])
        db.session.commit()
        seed_catalog(self)

    def tearDown(self):
        practice_worker.stop()
        db.session.remove()
        db.drop_all()
        event.remove(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()
        self.context.pop()
        self.directory.cleanup()

    def test_the_thread_answers_a_queued_turn(self):
        user = db.session.get(User, 1)
        session_id = service.start_session(user, exercise_id=EXERCISE, request_id=str(uuid4()))["session_id"]
        worker = practice_worker.start(self.app, FakeProvider(), poll_seconds=0.2)
        self.assertIs(practice_worker.start(self.app), worker)
        self.assertEqual([thread.name for thread in threading.enumerate()].count("learning-ai-worker"), 1)
        sent = service.send_turn(user, session_id, body="Hello?", expected_sequence=1, artifact_revisions=ALL_AT_ZERO,
                                 brief_revision=0, request_id=str(uuid4()))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and db.session.get(AIRequest, sent["reply"]["id"],
                                                             populate_existing=True).status != "completed":
            time.sleep(0.05)
        self.assertEqual(db.session.get(AIRequest, sent["reply"]["id"], populate_existing=True).status, "completed")
        practice_worker.stop()
        self.assertNotIn("learning-ai-worker", [thread.name for thread in threading.enumerate()])

    def wait_for(self, reply_id, status):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and db.session.get(AIRequest, reply_id, populate_existing=True).status != status:
            time.sleep(0.05)
        return db.session.get(AIRequest, reply_id, populate_existing=True).status

    def test_restarting_while_a_call_is_stuck_keeps_one_thread(self):
        called, release = threading.Event(), threading.Event()

        class Stuck:
            def call(self, body, *, deadline):
                if body["text"]["format"]["name"] == interviewer.SELECTOR_SCHEMA_NAME:
                    return {"output": practice_worker.fake_selection(body), "usage": None}
                called.set()
                release.wait(10)
                return {"output": {"reply": "Unstuck."}, "usage": None}
        user = db.session.get(User, 1)
        session_id = service.start_session(user, exercise_id=EXERCISE, request_id=str(uuid4()))["session_id"]
        worker = practice_worker.start(self.app, Stuck(), poll_seconds=0.2)
        sent = service.send_turn(user, session_id, body="Hello?", expected_sequence=1, artifact_revisions=ALL_AT_ZERO,
                                 brief_revision=0, request_id=str(uuid4()))
        self.assertTrue(called.wait(10))
        practice_worker.stop(timeout=0.2)  # gives up waiting: the call is stuck
        self.assertIs(practice_worker.start(self.app, FakeProvider()), worker)
        self.assertEqual([thread.name for thread in threading.enumerate()].count("learning-ai-worker"), 1)
        release.set()
        self.assertEqual(self.wait_for(sent["reply"]["id"], "completed"), "completed")
        self.assertTrue(worker._thread.is_alive())  # restarted: it carries on after the call
        practice_worker.stop()
        self.assertNotIn("learning-ai-worker", [thread.name for thread in threading.enumerate()])


if __name__ == "__main__":
    unittest.main()
