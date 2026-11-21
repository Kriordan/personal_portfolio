"""Exports preserve saved history and use explicit learner-facing projections."""
from copy import deepcopy
import json
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import InvalidRequestError

from project.database import db
from project.models import (AIRequest, ArtifactRevision, ContentRevision, LearningAICharge, PracticeFeedback,
    PracticeFeedbackAnnotation, PracticeReceipt, PracticeSession, ReviewLog, ReviewProgress,
    SessionMessage, User)
from project.services import feedback_review_service as review, practice_export_service as exports, practice_service as practice
from project.services.learning_errors import NotFoundError
from tests.curriculum_v2_fixtures import PRIVATE_V2, publish_feedback_catalog
from tests.feedback_fixtures import DISCOVERY, RACE
from tests.test_feedback_review import completed_feedback
from tests.test_practice_replies import PracticeReplyCase, columns
from tests.test_practice_service import NOW, SENTINELS, PracticeServiceCase
from tests.test_practice_submissions import submission_input


def add_history(user, sid):
    entry = dict(id="chosen-boundary", type="decision", text="Keep the original reasoning.", pinned=True,
                 sources=[{"artifact_id": "api", "revision": 1}])
    practice.save_work(user, sid, request_id=str(uuid4()),
        edits=[dict(artifact_id="api", base_revision=1, language="text", body="A revised contract — café")],
        brief=dict(base_revision=0, entries=[entry]))
    # Leave a genuinely pending reply: exporting neither waits for it nor claims it.
    practice.send_turn(user, sid, body="Trace my revised contract.", expected_sequence=1,
        artifact_revisions={"api": 2, "schema": 0, "algorithm": 0}, brief_revision=1, request_id=str(uuid4()))
    practice.save_work(user, sid, request_id=str(uuid4()), brief=dict(base_revision=1,
        entries=[dict(entry, text="The decision evolved after another failure case.")]))


class PracticeExportV1Tests(PracticeServiceCase):
    def test_empty_legacy_session_and_unknown_or_foreign_ids(self):
        sid = self.start()
        practice.set_status(self.user, sid, status="paused", request_id=str(uuid4()))
        document = exports.session_export(1, sid, now=NOW)
        self.assertEqual(document["session"]["status"], "paused")
        self.assertEqual(document["exercise"]["version"], 1)
        self.assertEqual(document["brief_revisions"], [{"revision": 0, "entries": [], "saved_at": None}])
        self.assertEqual(document["submissions"], [])
        self.assertEqual([a["current_revision"] for a in document["artifacts"]], [0, 0, 0])
        for a in document["artifacts"]:
            self.assertEqual(a["revisions"][0]["body"], "")
        for secret in SENTINELS:
            self.assertNotIn(secret, exports.render(document, "json").decode())
            self.assertNotIn(secret, exports.render(document, "md").decode())
        for user_id, value in ((2, sid), (1, "bad-id"), (1, str(uuid4()))):
            with self.assertRaises(NotFoundError):
                exports.session_export(user_id, value)


class PracticeExportTests(PracticeReplyCase):
    def setUp(self):
        super().setUp()
        publish_feedback_catalog()
        self.sid, self.seq, self.rid = completed_feedback(self.user)

    def document(self):
        return exports.session_export(1, self.sid, now=NOW)

    def agree_and_rate(self):
        review.annotate(self.user, self.sid, self.seq, "f2", decision="agree", note="Test both first attempts.",
                        expected_revision=0, request_id=str(uuid4()))
        review.rate_review(self.user, self.sid, self.seq, "f2", card_id="idempotency:race", content_version=2,
            expected_revision=0, request_id=str(uuid4()), rating=4)

    def test_complete_history_resolves_snapshot_turn_and_feedback_references(self):
        self.agree_and_rate()
        add_history(self.user, self.sid)
        document = self.document()
        self.assertEqual((document["format"], document["schema_version"]), ("engineering-learning.practice-session", 1))
        self.assertEqual([r["revision"] for r in document["artifacts"][0]["revisions"]], [0, 1, 2])
        self.assertIn(RACE, document["artifacts"][0]["revisions"][1]["body"])
        self.assertEqual(document["artifacts"][0]["revisions"][2]["body"], "A revised contract — café")
        self.assertEqual([r["revision"] for r in document["brief_revisions"]], [0, 1, 2])
        self.assertEqual(document["brief_revisions"][1]["entries"][0]["text"], "Keep the original reasoning.")
        self.assertEqual(document["transcript"][-1]["artifact_revisions"], [{"artifact_id": "api", "revision": 2}])
        self.assertEqual(document["transcript"][-1]["brief_revision"], 1)
        snapshot = document["submissions"][0]
        self.assertEqual((snapshot["sequence"], snapshot["checks"][0]["revision"]), (self.seq, 1))
        concern = snapshot["feedback"]["findings"][1]
        self.assertEqual(concern["evidence"][0]["revision"], 1)
        self.assertEqual(concern["evidence"][0]["quote"], RACE)
        self.assertEqual(concern["annotation"]["note"], "Test both first attempts.")
        self.assertEqual(document["followup_ratings"][0]["card_id"], "idempotency:race")
        self.assertEqual(document["followup_ratings"][0]["finding_id"], "f2")
        self.assertEqual(json.loads(exports.render(document, "json")), document)
        self.assertEqual(self.document(), document)
        markdown = exports.render(document, "md").decode()
        for part in ("## Conversation", "Revision 1", "Revision 2", "Notes revision 1", "Notes revision 2",
                     "Snapshot 2", "Explicit follow-up ratings", "Test both first attempts"):
            self.assertIn(part, markdown)

    def test_export_never_writes_resumes_claims_ai_or_changes_budget_and_progress(self):
        self.agree_and_rate()
        add_history(self.user, self.sid)
        practice.set_status(self.user, self.sid, status="paused", request_id=str(uuid4()))
        self.app.config.update(LEARNING_AI_ENABLED=False, LEARNING_AI_MONTHLY_CAP_USD=0)
        models = (PracticeSession, AIRequest, ArtifactRevision, SessionMessage, PracticeFeedback, PracticeFeedbackAnnotation,
                  PracticeReceipt, LearningAICharge, ReviewLog, ReviewProgress)
        before = [columns(model.query.all()) for model in models]
        with patch.object(practice, "_lock_owner", side_effect=AssertionError("export must not block writes")), \
                patch.object(practice, "begin_call", side_effect=AssertionError("no generation")):
            for format in exports.FORMATS:
                self.assertGreater(len(exports.export_file(1, self.sid, format)["data"]), 100)
        self.assertEqual(before, [columns(model.query.all()) for model in models])

    def test_in_memory_sqlite_refuses_to_borrow_the_callers_uncommitted_write_connection(self):
        user = db.session.get(User, 1)
        original = user.username
        user.username = "Uncommitted REPL change"
        db.session.flush()
        with self.assertRaisesRegex(InvalidRequestError, "Commit or roll back"):
            self.document()
        self.assertEqual(db.session.scalar(db.select(User.username).where(User.id == 1)), "Uncommitted REPL change")
        db.session.rollback()
        self.assertEqual(db.session.get(User, 1).username, original)
        self.assertEqual(self.document()["session"]["id"], self.sid)

    def test_all_nested_private_fields_are_excluded_even_after_future_schema_additions(self):
        self.agree_and_rate()
        exercise = db.session.get(ContentRevision, ("idempotent-order-api", 2))
        content = deepcopy(exercise.payload)
        content["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        content["content"]["brief"]["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        content["content"]["brief"]["expected_artifacts"][0]["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        exercise.payload = content
        row = PracticeFeedback.query.one()
        data = deepcopy(row.data)
        data["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        data["coverage"]["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        data["coverage"]["artifact_revisions"][0]["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        for finding in data["findings"]:
            finding["future_private"] = "FUTURE_PRIVATE_SENTINEL"
            for nested in finding["evidence"] + finding["remediation"]:
                nested["future_private"] = "FUTURE_PRIVATE_SENTINEL"
        row.data = data
        db.session.commit()
        for format in exports.FORMATS:
            serialized = exports.render(self.document(), format).decode()
            for secret in (*PRIVATE_V2, "FUTURE_PRIVATE_SENTINEL", "misconception_ids", "reference_reasoning",
                           "clarification_cues", "fixture1@example.test", "claim_token", "payload_sha256"):
                self.assertNotIn(secret, serialized)

    def test_disclosure_hints_and_continuation_export_only_public_records_and_all_turns(self):
        payload = db.session.get(ContentRevision, ("idempotent-order-api", 2)).payload
        constraints = payload["content"]["facilitator"]["hidden_constraints"]
        values = [
            (3, "interviewer", "turn", "An already delivered explanation.", None),
            (4, "interviewer", "context", "", {"revealed": [constraints[0]["id"]], "turn_sequence": 3, "private": "RECORD_SECRET"}),
            (5, "interviewer", "assistance", "", {"hint_index": 0, "turn_sequence": 3}),
            (6, "learner", "context", "", {"from_sequence": 3, "private": "RECORD_SECRET"}),
        ]
        for seq, role, kind, body, data in values:
            db.session.add(SessionMessage(practice_session_id=self.sid, sequence=seq, role=role, kind=kind,
                modality="text", body=body, data=data, created_at=NOW))
        db.session.commit()
        document = self.document()
        self.assertEqual(document["revealed_requirements"], [{"id": constraints[0]["id"], "fact": constraints[0]["fact"], "sequence": 3}])
        self.assertTrue(document["transcript"][-1]["hint"])
        self.assertEqual(document["transcript"][0]["sequence"], 1)
        self.assertEqual(document["context_choices"], [{"sequence": 6, "from_sequence": 3}])
        for format in exports.FORMATS:
            body = exports.render(document, format).decode()
            self.assertNotIn("RECORD_SECRET", body)
            for constraint in constraints[1:]:
                self.assertNotIn(constraint["fact"], body)

    def test_other_session_content_and_ratings_are_not_exported(self):
        self.agree_and_rate()
        sid, seq, _ = completed_feedback(self.user)
        review.annotate(self.user, sid, seq, "f2", decision="agree", note="OTHER_SESSION_NOTE",
            expected_revision=0, request_id=str(uuid4()))
        review.rate_review(self.user, sid, seq, "f2", card_id="idempotency:race", content_version=2,
            expected_revision=1, request_id=str(uuid4()), rating=3)
        practice.save_work(self.user, sid, edits=[dict(artifact_id="api", base_revision=1, language="text", body="OTHER_SESSION_WORK")],
            request_id=str(uuid4()))
        document = self.document()
        self.assertEqual([r["rating"] for r in document["followup_ratings"]], [4])
        for secret in ("OTHER_SESSION_NOTE", "OTHER_SESSION_WORK", sid):
            self.assertNotIn(secret, json.dumps(document))

    def test_markdown_keeps_untrusted_prose_literal_and_fences_cannot_be_closed_by_work(self):
        hostile = '<script>alert(1)</script>\n![image](https://example.test/track)\n[click](javascript:alert(1))'
        review.annotate(self.user, self.sid, self.seq, "f2", decision="disagree", note=hostile,
            expected_revision=0, request_id=str(uuid4()))
        body = "``````\n" + hostile + "\nUnicode: 🧪 café\n"
        practice.save_work(self.user, self.sid, edits=[dict(artifact_id="api", base_revision=1, language="text", body=body)],
            request_id=str(uuid4()))
        document = self.document()
        self.assertEqual(document["artifacts"][0]["revisions"][-1]["body"], body)
        markdown = exports.render(document, "md").decode()
        self.assertIn("```````text\n" + body + "\n```````", markdown)
        note = markdown.split("Your response: disagree", 1)[1]
        self.assertNotIn("<script>", note)
        self.assertNotIn("![image]", note)
        self.assertNotIn("[click]", note)
        self.assertIn("&lt;script&gt;", note)

    def test_size_allowance_is_checked_in_utf8_and_never_silently_truncates(self):
        document = self.document()
        for format in exports.FORMATS:
            data = exports.render(document, format)
            with patch.dict(self.app.config, LEARNING_EXPORT_MAX_BYTES=len(data) - 1):
                with self.assertRaises(exports.ExportTooLarge):
                    exports.render(document, format)
        with patch.dict(self.app.config, LEARNING_EXPORT_MAX_BYTES=500):
            with self.assertRaises(exports.ExportTooLarge):
                self.document()
        self.assertEqual(self.document(), document)

    def test_deleted_session_cannot_be_downloaded_and_export_does_not_create_archive_rows(self):
        document = self.document()
        practice.delete_session(self.user, self.sid)
        with self.assertRaises(NotFoundError):
            self.document()
        self.assertIn(DISCOVERY, document["artifacts"][0]["revisions"][1]["body"])
        self.assertEqual(PracticeFeedback.query.count(), 0)
        self.assertEqual(LearningAICharge.query.count(), 1)
