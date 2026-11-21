"""Immutable editable-session checkpoints and their receipt/recovery/privacy boundaries."""
from copy import deepcopy
import json
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import ArtifactRevision, LearningAICharge, PracticeReceipt, SessionMessage, SessionMessageArtifact
from project.services import practice_service as service
from project.services.learning_errors import NotFoundError
from tests.test_practice_service import NOW, PracticeServiceCase, SENTINELS, publish
from tests.test_practice_replies import PracticeReplyCase, columns
from tests.curriculum_v2_fixtures import PRIVATE_V2, publish_feedback_catalog


def submission_input(detail, body=None, language="json"):
    edits = [{"artifact_id": a["artifact_id"], "base_revision": a["revision"],
              "body": a["body"], "language": a["language"]} for a in detail["artifacts"]]
    if body is not None:
        edits[0].update(body=body, language=language)
    return {"edits": edits, "brief": {"base_revision": detail["session_brief"]["revision"],
                                       "entries": detail["session_brief"]["entries"]},
            "expected_sequence": detail["messages"][-1]["sequence"], "request_id": str(uuid4())}


class PracticeSubmissionTests(PracticeServiceCase):
    def submit(self, sid, body=None, **overrides):
        values = submission_input(service.session_detail(1, sid), body)
        values.update(overrides)
        return service.save_and_submit(self.user, sid, **values)

    def test_v1_and_v2_snapshots_do_not_expose_evaluator_material(self):
        old = self.start()
        publish_feedback_catalog()
        new = self.start()
        for sid, version in ((old, 1), (new, 2)):
            result = self.submit(sid, '{}')
            snapshot = result["submission"]
            self.assertEqual((snapshot["exercise_version"], snapshot["exercise_spec_version"]), (version, version))
            visible = json.dumps([result, service.submission_detail(1, sid, snapshot["sequence"]),
                                  service.session_detail(1, sid)])
            for private in (*SENTINELS, *PRIVATE_V2, 'misconceptions'):
                self.assertNotIn(private, visible)

    def test_snapshot_pins_records_brief_exercise_and_artifacts_without_copying_bodies(self):
        sid = self.start()
        # A context record is part of the boundary even though it is not a turn.
        db.session.add(SessionMessage(practice_session_id=sid, sequence=2, role="learner", kind="context",
                                      modality="text", body="", data={"from_sequence": 1}, created_at=NOW))
        db.session.commit()
        result = self.submit(sid, '{"private":"ARTIFACT_SENTINEL"}', brief={"base_revision": 0, "entries": [
            {"id": "decision", "type": "decision", "text": "NOTE_SENTINEL", "pinned": True}]})
        snap = result["submission"]
        self.assertEqual((snap["sequence"], snap["through_sequence"], snap["turn_sequence"], snap["brief_revision"]),
                         (4, 3, 1, 1))
        self.assertEqual((snap["exercise_version"], snap["exercise_spec_version"], snap["checker_version"]),
                         (1, 1, "syntax-1"))
        self.assertEqual([(c["revision"], c["status"]) for c in snap["checks"]],
                         [(1, "passed"), (0, "not_checked"), (0, "not_checked")])
        self.assertEqual(SessionMessageArtifact.query.count(), 1)
        row = SessionMessage.query.filter_by(kind="submission").one()
        for secret in (*SENTINELS, "ARTIFACT_SENTINEL", "NOTE_SENTINEL"):
            self.assertNotIn(secret, json.dumps(row.data) + row.body + json.dumps(result))
        self.assertEqual(service.submission_detail(1, sid, 4)["session_brief"]["entries"][0]["text"], "NOTE_SENTINEL")

    def test_later_edits_new_exercises_and_checker_changes_never_rewrite_a_snapshot(self):
        sid = self.start()
        first = self.submit(sid, '{}')["submission"]
        newer = deepcopy(self.catalog["items"][-1])
        newer["version"] = 2
        publish(newer)
        db.session.commit()
        self.save(sid, [self.edit("api", '{', base=1, language="json")])
        with patch.object(service, "check_artifact", side_effect=AssertionError("must read persisted results")):
            detail = service.submission_detail(1, sid, first["sequence"])
            self.assertEqual(detail["submission"], first)
            self.assertEqual(detail["artifacts"][0]["current_revision"], 2)
            self.assertEqual(service.session_detail(1, sid)["submissions"], [first])
        second = self.submit(sid)["submission"]
        self.assertEqual((second["exercise_version"], second["checks"][0]["status"]), (1, "error"))
        self.assertEqual(service.session_detail(1, sid)["session"]["status"], "active")
        self.assertEqual(ArtifactRevision.query.count(), 2)

    def test_receipt_replay_after_later_edits_does_not_recheck_or_resubmit(self):
        sid = self.start()
        values = submission_input(service.session_detail(1, sid), '{}')
        first = service.save_and_submit(self.user, sid, **values)
        self.save(sid, [self.edit("api", 'newer', base=1)])
        with patch.object(service, "check_artifact", side_effect=AssertionError("replayed")):
            self.assertEqual(service.save_and_submit(self.user, sid, **values), first)
        self.assertEqual(service.practice_receipt(1, values["request_id"])["response"], first)
        self.assertEqual(SessionMessage.query.filter_by(kind="submission").count(), 1)
        values["edits"][0]["body"] = 'changed'
        with self.assertRaises(service.RequestConflictError):
            service.save_and_submit(self.user, sid, **values)

    def test_stale_artifact_brief_and_transcript_each_refuse_all_writes(self):
        for change in ("artifact", "brief", "turn"):
            sid = self.start()
            values = submission_input(service.session_detail(1, sid), '{}')
            if change == "artifact":
                self.save(sid, [self.edit("schema", "new schema")])  # untouched stale field also blocks
            elif change == "brief":
                service.save_work(self.user, sid, brief={"base_revision": 0, "entries": [
                    {"id": "decision", "type": "decision", "text": "new note", "pinned": False}]},
                    request_id=str(uuid4()))
            else:
                service.send_turn(self.user, sid, body="New reasoning", expected_sequence=1,
                                  artifact_revisions={"api": 0, "schema": 0, "algorithm": 0}, brief_revision=0,
                                  request_id=str(uuid4()))
            with self.assertRaises(service.StaleViewError):
                service.save_and_submit(self.user, sid, **values)
            self.assertEqual(ArtifactRevision.query.filter_by(practice_session_id=sid, artifact_id="api").count(), 0)
            self.assertEqual(SessionMessage.query.filter_by(practice_session_id=sid, kind="submission").count(), 0)

    def test_failure_rolls_back_artifact_brief_snapshot_citations_and_receipt(self):
        sid = self.start()
        values = submission_input(service.session_detail(1, sid), '{}')
        with patch.object(db.session, "commit", side_effect=OperationalError("fixture", {}, Exception())):
            with self.assertRaises(OperationalError):
                service.save_and_submit(self.user, sid, **values)
        self.assertEqual(ArtifactRevision.query.count(), 0)
        self.assertEqual(SessionMessage.query.count(), 1)
        self.assertEqual(SessionMessageArtifact.query.count(), 0)
        self.assertIsNone(service.practice_receipt(1, values["request_id"]))
        self.assertEqual(service.save_and_submit(self.user, sid, **values)["submission"]["checks"][0]["status"], "passed")

    def test_owner_scope_projection_and_delete_cascade(self):
        sid = self.start()
        result = self.submit(sid, '{}')
        seq = result["submission"]["sequence"]
        with self.assertRaises(NotFoundError):
            service.submission_detail(2, sid, seq)
        with self.assertRaises(NotFoundError):
            service.submission_detail(1, sid, 1)  # a turn is not a submission
        with self.assertRaises(NotFoundError):
            service.save_and_submit(self.other, sid, **submission_input(service.session_detail(1, sid)))
        row = SessionMessage.query.filter_by(kind="submission").one()
        row.data = {**row.data, "private_future_evaluation": "EVALUATOR_SENTINEL"}
        db.session.commit()
        self.assertNotIn("EVALUATOR_SENTINEL", json.dumps(service.submission_detail(1, sid, seq)))
        self.assertEqual(service.session_counts(1, sid)["submissions"], 1)
        service.delete_session(self.user, sid)
        for model in (SessionMessage, SessionMessageArtifact, ArtifactRevision, PracticeReceipt):
            self.assertEqual(model.query.count(), 0)

    def test_incomplete_or_invalid_view_cannot_create_a_snapshot(self):
        sid = self.start()
        values = submission_input(service.session_detail(1, sid))
        cases = [{"edits": values["edits"][:1]}, {"expected_sequence": True},
                 {"brief": {"base_revision": 0, "entries": "invalid"}}]
        for override in cases:
            with self.assertRaises(service.PracticeValidationError):
                service.save_and_submit(self.user, sid, **(values | override))
        self.assertEqual(SessionMessage.query.count(), 1)


class SubmissionReplyBoundaryTests(PracticeReplyCase):
    def test_pending_reply_blocks_snapshot_then_completed_reply_is_included_without_a_charge(self):
        sid = self.start()
        sent = self.send(sid)
        values = submission_input(service.session_detail(1, sid, now=self.clock()), '{}')
        with self.assertRaises(service.ReplyPendingError):
            service.save_and_submit(self.user, sid, **values, now=self.clock())
        self.assertEqual(ArtifactRevision.query.count(), 0)
        self.work()
        before = columns(LearningAICharge.query.all())
        with self.assertRaises(service.StaleViewError):
            service.save_and_submit(self.user, sid, **values, now=self.clock())
        values = submission_input(service.session_detail(1, sid, now=self.clock()), '{}')
        result = service.save_and_submit(self.user, sid, **values, now=self.clock())
        self.assertGreater(result["submission"]["turn_sequence"], sent["sequence"])
        self.assertEqual(columns(LearningAICharge.query.all()), before)
        self.assertEqual(len(self.provider.calls), 2)

    def test_checks_resume_paused_session_even_when_ai_budget_is_exhausted(self):
        sid = self.start()
        service.set_status(self.user, sid, status="paused", request_id=str(uuid4()))
        self.app.config["LEARNING_AI_MONTHLY_CAP_USD"] = 0
        values = submission_input(service.session_detail(1, sid), '{}')
        result = service.save_and_submit(self.user, sid, **values)
        self.assertEqual(result["status"], "active")
        self.assertEqual(LearningAICharge.query.count(), 0)
        self.assertEqual(self.provider.calls, [])
