"""Practice sessions on SQLite with foreign keys enforced. Races run on PostgreSQL."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from uuid import uuid4

from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import (
    ArtifactRevision, ContentRevision, CurriculumItem, PracticeReceipt, PracticeSession, SessionMessage,
    SessionMessageArtifact, User,
)
from project.services import curriculum_service, practice_service as service
from project.services.learning_service import NotFoundError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
EXERCISE = "idempotent-order-api"
NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)


def enable_sqlite_foreign_keys(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def publish(item, *, published=True):
    now = datetime.now(timezone.utc)
    db.session.add(ContentRevision(
        item_id=item["id"], version=item["version"], schema_version=1, payload=item,
        checksum=curriculum_service.content_checksum(item), imported_at=now,
        published_at=now if published else None, reviewed_by="Test fixture" if published else None,
        reviewed_on=now.date() if published else None))


def seed_catalog(testcase):
    testcase.catalog = load_catalog(ROOT / "curriculum/idempotency/catalog.json")
    exercise = testcase.catalog["items"][-1]["content"]
    exercise["facilitator"]["hidden_constraints"][0]["fact"] = "HIDDEN_SENTINEL"
    exercise["facilitator"]["permitted_hints"] = ["HINT_SENTINEL"]
    exercise["facilitator"]["instructions"] = ["INSTRUCTION_SENTINEL"]
    exercise["assessment"]["reference_reasoning"] = ["EVALUATOR_SENTINEL"]
    for item in testcase.catalog["items"]:
        db.session.add(CurriculumItem(id=item["id"], kind=item["kind"]))
    db.session.flush()
    for item in testcase.catalog["items"]:
        publish(item)
    db.session.commit()


SENTINELS = ("HIDDEN_SENTINEL", "HINT_SENTINEL", "INSTRUCTION_SENTINEL", "EVALUATOR_SENTINEL",
             "clarification_cues", "reference_reasoning", "permitted_hints")


class PracticeServiceCase(unittest.TestCase):
    """Shared fixtures for the practice service suites; no tests of its own."""

    def setUp(self):
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI="sqlite://"))
        self.context = self.app.app_context()
        self.context.push()
        event.listen(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()  # any earlier connection predates the listener
        db.create_all()
        db.session.add_all([User(id=i, username=f"fixture{i}", email=f"fixture{i}@example.test") for i in (1, 2)])
        db.session.commit()
        seed_catalog(self)
        self.user, self.other = db.session.get(User, 1), db.session.get(User, 2)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        event.remove(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()
        self.context.pop()

    def start(self, user=None, **kwargs):
        kwargs.setdefault("request_id", str(uuid4()))
        return service.start_session(user or self.user, exercise_id=EXERCISE, concept_id="idempotency",
                                     now=NOW, **kwargs)["session_id"]

    def save(self, session_id, edits, *, user=None, request_id=None):
        return service.save_work(user or self.user, session_id, edits=edits,
                                 request_id=request_id or str(uuid4()), now=NOW)

    @staticmethod
    def edit(artifact_id, body, base=0, language=None):
        defaults = {"api": "text", "schema": "sql", "algorithm": "pseudocode"}
        return {"artifact_id": artifact_id, "base_revision": base, "body": body,
                "language": language or defaults[artifact_id]}


class PracticeServiceTests(PracticeServiceCase):
    def test_foreign_keys_are_enforced_in_this_suite(self):
        self.assertEqual(db.session.execute(text("PRAGMA foreign_keys")).scalar(), 1)

    def test_start_pins_the_published_exercise_and_records_the_opening_turn(self):
        session_id = self.start()
        detail = service.session_detail(1, session_id)
        self.assertEqual(detail["session"]["exercise_version"], 1)
        self.assertEqual(detail["session"]["status"], "active")
        self.assertEqual(detail["session"]["concept_id"], "idempotency")
        opening = self.catalog["items"][-1]["content"]["facilitator"]["opening_prompt"]
        self.assertEqual(detail["messages"], [{"sequence": 1, "role": "interviewer", "kind": "turn",
            "body": opening, "created_at": NOW.isoformat(), "artifact_revisions": [], "brief_revision": None,
            "hint": False}])
        self.assertEqual(detail["session_brief"], {"revision": 0, "entries": [], "saved_at": None})
        self.assertEqual([(a["artifact_id"], a["revision"], a["language"], a["body"]) for a in detail["artifacts"]],
                         [("api", 0, "text", ""), ("schema", 0, "sql", ""), ("algorithm", 0, "pseudocode", "")])
        self.assertEqual(detail["artifacts"][0]["languages"], ["text", "json", "yaml"])
        self.assertIn("scenario", detail["brief"])
        serialized = json.dumps(detail)
        for secret in SENTINELS:
            self.assertNotIn(secret, serialized)

    def test_only_published_exercises_of_the_named_concept_can_start(self):
        for exercise_id, concept_id in (("idempotency:timeout", "idempotency"), (EXERCISE, "other-concept"),
                                        ("absent", None), ("Not An ID", None), (["list"], None)):
            with self.subTest(exercise_id=exercise_id):
                with self.assertRaises(NotFoundError):
                    service.start_session(self.user, exercise_id=exercise_id, concept_id=concept_id,
                                          request_id=str(uuid4()))
        revision = db.session.get(ContentRevision, (EXERCISE, 1))
        revision.published_at = revision.reviewed_by = revision.reviewed_on = None
        db.session.commit()
        with self.assertRaises(NotFoundError):
            self.start()
        self.assertEqual(PracticeSession.query.count(), 0)

    def test_start_replays_by_request_id_and_rejects_reuse_for_other_input(self):
        request_id = str(uuid4())
        first = self.start(request_id=request_id)
        self.assertEqual(self.start(request_id=request_id), first)
        self.assertEqual(PracticeSession.query.count(), 1)
        self.assertEqual(SessionMessage.query.count(), 1)
        with self.assertRaises(service.RequestConflictError):
            service.start_session(self.user, exercise_id=EXERCISE, request_id=request_id)
        with self.assertRaises(service.RequestConflictError):
            self.save(first, [self.edit("api", "x")], request_id=request_id)
        # Another account's identical request ID is that account's own new operation.
        self.assertNotEqual(self.start(self.other, request_id=request_id), first)

    def test_a_newer_exercise_version_leaves_existing_sessions_pinned(self):
        old = self.start()
        revised = deepcopy(self.catalog["items"][-1])
        revised.update(version=2, title="Revised exercise")
        revised["content"]["facilitator"]["opening_prompt"] = "A revised opening."
        publish(revised)
        db.session.commit()
        self.assertEqual(service.session_detail(1, old)["session"]["exercise_title"], "Design a retry-safe order API")
        self.assertEqual(service.session_detail(1, old)["messages"][0]["body"][:22], "How would you begin sc")
        new = service.session_detail(1, self.start())
        self.assertEqual((new["session"]["exercise_version"], new["messages"][0]["body"]), (2, "A revised opening."))

    def test_saves_create_revisions_and_unchanged_saves_create_none(self):
        session_id = self.start()
        empty = self.save(session_id, [self.edit("api", ""), self.edit("schema", ""), self.edit("algorithm", "")])
        self.assertEqual(empty["artifacts"], {name: {"revision": 0, "changed": False}
                                              for name in ("api", "schema", "algorithm")})
        result = self.save(session_id, [self.edit("api", "POST /orders"), self.edit("schema", "CREATE TABLE o();"),
                                        self.edit("algorithm", "")])
        self.assertEqual(result["artifacts"]["api"], {"revision": 1, "changed": True})
        self.assertEqual(result["artifacts"]["algorithm"], {"revision": 0, "changed": False})
        again = self.save(session_id, [self.edit("api", "POST /orders", base=1)])
        self.assertEqual(again["artifacts"]["api"], {"revision": 1, "changed": False})
        self.assertEqual(ArtifactRevision.query.count(), 2)
        self.assertEqual(db.session.get(PracticeSession, session_id).updated_at.replace(tzinfo=timezone.utc), NOW)

    def test_line_endings_are_normalized_and_notation_changes_are_changes(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "\nline one\r\nline two\r")])
        self.assertEqual(ArtifactRevision.query.one().body, "\nline one\nline two\n")
        unchanged = self.save(session_id, [self.edit("api", "\r\nline one\nline two\n", base=1)])
        self.assertFalse(unchanged["artifacts"]["api"]["changed"])
        as_json = self.save(session_id, [self.edit("api", "\nline one\nline two\n", base=1, language="json")])
        self.assertEqual(as_json["artifacts"]["api"], {"revision": 2, "changed": True})
        with self.assertRaises(service.PracticeValidationError) as raised:
            self.save(session_id, [self.edit("schema", "x", language="json")])
        self.assertEqual(raised.exception.field, "schema")

    def test_request_replays_return_the_identical_result(self):
        session_id = self.start()
        request_id = str(uuid4())
        edits = [self.edit("api", "first body")]
        first = self.save(session_id, edits, request_id=request_id)
        self.assertEqual(self.save(session_id, edits, request_id=request_id), first)
        self.assertEqual(ArtifactRevision.query.count(), 1)
        with self.assertRaises(service.RequestConflictError):
            self.save(session_id, [self.edit("api", "different body")], request_id=request_id)
        self.assertEqual(service.practice_receipt(1, request_id), {"operation": "save", "response": first})
        self.assertIsNone(service.practice_receipt(2, request_id))

    def test_stale_edits_conflict_and_save_nothing(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "tab A")])
        with self.assertRaises(service.StaleViewError) as raised:
            self.save(session_id, [self.edit("api", "tab B"), self.edit("schema", "tab B schema")])
        self.assertEqual(raised.exception.conflicts, [{"artifact_id": "api", "base_revision": 0, "revision": 1,
                                                       "language": "text", "body": "tab A"}])
        self.assertEqual(ArtifactRevision.query.count(), 1)  # the schema edit was not saved either
        retried = self.save(session_id, [self.edit("api", "tab B", base=1), self.edit("schema", "tab B schema")])
        self.assertEqual(retried["artifacts"]["api"]["revision"], 2)
        self.assertEqual(ArtifactRevision.query.filter_by(revision=1, artifact_id="api").one().body, "tab A")

    def test_an_untouched_artifact_does_not_block_or_revert_a_save(self):
        session_id = self.start()
        self.save(session_id, [self.edit("schema", "other tab schema")])
        # This view loaded before the other tab saved; its schema box is untouched.
        result = self.save(session_id, [self.edit("api", "this tab api"), self.edit("schema", "")])
        self.assertEqual(result["artifacts"], {"api": {"revision": 1, "changed": True},
                                               "schema": {"revision": 1, "changed": False}})
        self.assertEqual(service.session_detail(1, session_id)["artifacts"][1]["body"], "other tab schema")

    def test_invalid_input_is_rejected_before_anything_is_written(self):
        session_id = self.start()
        big = "x" * (service.ARTIFACT_MAX_BYTES + 1)
        cases = [
            [self.edit("api", big)], [self.edit("api", "a\x00b")], [self.edit("api", "\ud800")],
            [dict(self.edit("api", "x"), artifact_id="nope")],
            [self.edit("api", "x"), self.edit("api", "y")], [dict(self.edit("api", "x"), base_revision=True)],
            [self.edit("api", "x", base=3)], [{"artifact_id": "api", "body": "x"}], "not a list", [],
            [dict(self.edit("api", "x"), language="cobol")], [dict(self.edit("api", "x"), body=None)],
        ]
        for edits in cases:
            with self.subTest(edits=str(edits)[:60]):
                with self.assertRaises(ValidationError):
                    self.save(session_id, edits)
        self.assertEqual(ArtifactRevision.query.count(), 0)
        self.assertEqual(PracticeReceipt.query.filter_by(operation="save").count(), 0)
        with self.assertRaisesRegex(service.PracticeValidationError, "64 KiB"):
            self.save(session_id, [self.edit("api", big)])

    def test_other_accounts_cannot_read_or_change_a_session(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "private work")])
        for call in (lambda: service.session_detail(2, session_id),
                     lambda: service.artifact_history(2, session_id, "api"),
                     lambda: service.artifact_revision(2, session_id, "api", 1),
                     lambda: self.save(session_id, [self.edit("api", "intrusion", base=1)], user=self.other),
                     lambda: service.session_detail(1, "not-a-uuid"),
                     lambda: service.session_detail(1, str(uuid4()))):
            with self.assertRaises(NotFoundError):
                call()
        self.assertEqual(service.list_sessions(2), [])
        self.assertEqual(ArtifactRevision.query.count(), 1)

    def test_history_is_immutable_and_addressed_by_revision_number(self):
        session_id = self.start()
        for number, body in enumerate(("one", "two", "three")):
            self.save(session_id, [self.edit("api", body, base=number)])
        first = ArtifactRevision.query.filter_by(revision=1).one()
        snapshot = (first.id, first.body, first.body_sha256, first.created_at)
        history = service.artifact_history(1, session_id, "api")
        self.assertEqual([entry["revision"] for entry in history["revisions"]], [3, 2, 1])
        old = service.artifact_revision(1, session_id, "api", 1)
        self.assertEqual((old["revision"]["body"], old["current_revision"]), ("one", 3))
        db.session.expire_all()
        first = ArtifactRevision.query.filter_by(revision=1).one()
        self.assertEqual((first.id, first.body, first.body_sha256, first.created_at), snapshot)
        for call in (lambda: service.artifact_revision(1, session_id, "api", 4),
                     lambda: service.artifact_revision(1, session_id, "api", first.id + 1000),
                     lambda: service.artifact_history(1, session_id, "unknown")):
            with self.assertRaises(NotFoundError):
                call()

    def test_receipts_store_no_learner_text(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "RECEIPT_SENTINEL body")])
        for receipt in PracticeReceipt.query.all():
            self.assertNotIn("RECEIPT_SENTINEL", json.dumps(receipt.response) + receipt.payload_sha256)

    def test_database_rejects_citations_across_sessions(self):
        first, second = self.start(), self.start()
        self.save(second, [self.edit("api", "second session")])
        message = SessionMessage.query.filter_by(practice_session_id=first).one()
        revision = ArtifactRevision.query.filter_by(practice_session_id=second).one()
        for session_id in (first, second):
            with self.subTest(session_id=session_id):
                db.session.add(SessionMessageArtifact(practice_session_id=session_id, message_id=message.id,
                                                      artifact_revision_id=revision.id))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_database_errors_do_not_echo_parameters(self):
        session_id = self.start()
        db.session.add(ArtifactRevision(practice_session_id=session_id, artifact_id="api", revision=1, title="t",
                                        format="text", language="not-a-language", body="PARAMETER_SENTINEL",
                                        body_sha256="0" * 64, created_at=NOW))
        with self.assertRaises(IntegrityError) as raised:
            db.session.commit()
        db.session.rollback()
        self.assertNotIn("PARAMETER_SENTINEL", str(raised.exception))
        self.assertNotIn("PARAMETER_SENTINEL", service.describe_failure(raised.exception))

    def test_lists_open_sessions_newest_first_with_learner_safe_fields(self):
        older = self.start()
        newer = service.start_session(self.user, exercise_id=EXERCISE, request_id=str(uuid4()),
                                      now=NOW + timedelta(minutes=5))["session_id"]
        listed = service.list_sessions(1)
        self.assertEqual([entry["id"] for entry in listed], [newer, older])
        self.assertEqual(listed[0]["exercise_title"], "Design a retry-safe order API")
        concept = curriculum_service.published_learner_item("idempotency")
        exercises = service.concept_exercises(concept, user_id=1)
        self.assertEqual([(entry["id"], len(entry["sessions"])) for entry in exercises], [(EXERCISE, 2)])
        self.assertEqual(service.concept_exercises(concept, user_id=2)[0]["sessions"], [])
        for secret in SENTINELS:
            self.assertNotIn(secret, json.dumps([listed, exercises]))


if __name__ == "__main__":
    unittest.main()
