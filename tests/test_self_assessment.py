"""Independent, versioned personal reflections and safe retry/deletion semantics."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.models import ConceptSelfAssessment, ContentRevision, ReviewProgress, User, UserConceptProgress
from project.services import self_assessment_service as service, concept_progress_service as progress, practice_service
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError
from tests.test_concept_progress import position
from tests.test_practice_web import PracticeWebCase


def checkin(revision=0, **ratings):
    return dict(content_version=1, expected_revision=revision, request_id=str(uuid4()),
        ratings={key: ratings.get(key, "not_assessed") for key in service.FIELDS})


def clear(revision):
    return dict(expected_revision=revision, request_id=str(uuid4()))


class SelfAssessmentTests(PracticeWebCase):
    def test_optional_baseline_and_dated_partial_ratings_with_independent_levels(self):
        self.assertEqual(service.history(1, "idempotency")["entries"], [])
        self.assertEqual(ConceptSelfAssessment.query.count(), 0)
        first = checkin(recognition="without_help", understanding="with_help", application="not_yet")
        saved = service.save(1, "idempotency", **first)
        self.assertEqual(saved["ratings"], first["ratings"])
        self.assertEqual((saved["revision"], saved["content_version"], saved["scale_version"]), (1, 1, 1))
        self.assertEqual(datetime.fromisoformat(saved["created_at"]).utcoffset().total_seconds(), 0)
        self.assertEqual(UserConceptProgress.query.count(), 0)
        second = service.save(1, "idempotency", **checkin(1, judgment="without_help"))
        history = service.history(1, "idempotency")
        self.assertEqual(history["current"], second)
        self.assertEqual(history["entries"], [second, saved])
        self.assertEqual(service.history(2, "idempotency")["entries"], [])

    def test_exact_old_retry_returns_original_snapshot_without_duplicate_or_reset(self):
        payload = checkin(recognition="without_help")
        first = service.save(1, "idempotency", **payload)
        second = service.save(1, "idempotency", **checkin(1, understanding="with_help"))
        self.assertEqual(service.save(1, "idempotency", **payload), first)
        self.assertEqual(service.history(1, "idempotency")["current"], second)
        with self.assertRaises(ConflictError):
            service.save(1, "idempotency", **dict(payload, ratings=checkin()["ratings"]))
        with self.assertRaises(service.AssessmentConflict) as raised:
            service.save(1, "idempotency", **checkin(1))
        self.assertEqual((raised.exception.revision, raised.exception.current), (2, second))
        self.assertEqual(ConceptSelfAssessment.query.count(), 2)
        # Request IDs are private to each account, not a cross-account oracle.
        self.assertEqual(service.save(2, "idempotency", **payload)["revision"], 1)

    def test_validation_and_nonconcepts_never_write(self):
        payload = checkin()
        for invalid in (dict(payload, expected_revision=True), dict(payload, expected_revision=-1),
                        dict(payload, expected_revision=service.MAX_INT), dict(payload, content_version=True),
                        dict(payload, request_id="bad"), dict(payload, ratings=[]), dict(payload, ratings={}),
                        dict(payload, ratings=dict(payload["ratings"], overall="without_help")),
                        dict(payload, ratings=dict(payload["ratings"], recognition="")),
                        dict(payload, ratings=dict(payload["ratings"], recognition=None))):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                service.save(1, "idempotency", **invalid)
        for value in (True, 0, -1, "1", service.MAX_INT + 1):
            with self.assertRaises(ValidationError):
                service.history(1, "idempotency", before=value)
        for concept_id in ("missing", "idempotent-order-api", "idempotency:timeout"):
            with self.assertRaises(NotFoundError):
                service.save(1, concept_id, **payload)
        self.assertEqual(ConceptSelfAssessment.query.count(), 0)

    def test_clear_removes_ratings_and_old_retries_cannot_resurrect_or_clear_new_work(self):
        first = checkin(recognition="with_help")
        service.save(1, "idempotency", **first)
        service.save(2, "idempotency", **first)
        deletion = clear(1)
        receipt = service.clear_history(1, "idempotency", **deletion)
        self.assertEqual(receipt, dict(revision=2, cleared_through=1))
        history = service.history(1, "idempotency")
        self.assertEqual((history["revision"], history["current"], history["entries"]), (2, None, []))
        row = db.session.get(ConceptSelfAssessment, (1, "idempotency", 1))
        self.assertTrue(row.deleted)
        self.assertTrue(all(getattr(row, key) is None for key in service.FIELDS))
        for payload in (first, checkin(1), checkin()):
            with self.assertRaises(ConflictError):
                service.save(1, "idempotency", **payload)
        new = service.save(1, "idempotency", **checkin(2, application="without_help"))
        self.assertEqual(service.clear_history(1, "idempotency", **deletion), receipt)
        self.assertEqual(service.history(1, "idempotency")["entries"], [new])
        self.assertEqual(len(service.history(2, "idempotency")["entries"]), 1)
        with self.assertRaises(ConflictError):
            service.clear_history(1, "idempotency", **dict(deletion, request_id=first["request_id"]))
        with self.assertRaises(service.AssessmentConflict):
            service.clear_history(1, "idempotency", **clear(2))

    def test_failed_commits_and_lost_responses_recover_with_original_request(self):
        payload = checkin()
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("fixture")), self.assertRaises(SQLAlchemyError):
            service.save(1, "idempotency", **payload)
        self.assertEqual(service.history(1, "idempotency")["revision"], 0)
        saved = service.save(1, "idempotency", **payload)
        deletion = clear(1)
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("fixture")), self.assertRaises(SQLAlchemyError):
            service.clear_history(1, "idempotency", **deletion)
        self.assertEqual(service.history(1, "idempotency")["current"], saved)
        service.clear_history(1, "idempotency", **deletion)
        self.assertEqual(service.clear_history(1, "idempotency", **deletion)["revision"], 2)

    def test_history_pagination_is_bounded_and_stable_during_new_saves(self):
        for rev in range(13):
            service.save(1, "idempotency", **checkin(rev))
        first = service.history(1, "idempotency")
        self.assertEqual([row["revision"] for row in first["entries"]], list(range(13, 3, -1)))
        service.save(1, "idempotency", **checkin(13))
        older = service.history(1, "idempotency", before=first["next_before"])
        self.assertEqual([row["revision"] for row in older["entries"]], [3, 2, 1])
        self.assertEqual(older["current"]["revision"], 14)
        self.assertIsNone(older["next_before"])

    def test_content_pins_old_history_and_withdrawal_preserves_owned_access(self):
        first = checkin()
        saved = service.save(1, "idempotency", **first)
        row = db.session.get(ContentRevision, ("idempotency", 1))
        payload = deepcopy(row.payload)
        payload["version"] = 2
        db.session.add(ContentRevision(item_id="idempotency", version=2, schema_version=1, payload=payload,
            checksum="fixture-v2", imported_at=datetime.now(timezone.utc)))
        db.session.commit()
        with self.assertRaises(NotFoundError):
            service.save(1, "idempotency", **dict(checkin(1), content_version=2))
        row.published_at = row.reviewed_by = row.reviewed_on = None
        db.session.commit()
        self.assertEqual(service.history(1, "idempotency")["current"], saved)
        self.assertIsNone(service.concept_for_reader(1, "idempotency"))
        self.assertEqual(service.save(1, "idempotency", **first), saved)
        with self.assertRaises(NotFoundError):
            service.save(1, "idempotency", **checkin(1))
        with self.assertRaises(NotFoundError):
            service.history(2, "idempotency")
        service.clear_history(1, "idempotency", **clear(1))
        self.assertEqual(service.history(1, "idempotency")["entries"], [])

    def test_no_effect_on_study_scheduling_practice_or_ai_budget(self):
        progress.enroll(1, "idempotency")
        bookmark = progress.save_position(1, "idempotency", **position())
        session_id = self.start()
        practice_service.save_work(db.session.get(User, 1), session_id, request_id=str(uuid4()), status="paused",
            edits=[dict(artifact_id="api", base_revision=0, language="text", body="Saved artifact")])
        db.session.add(ReviewProgress(user_id=1, card_id="idempotency:timeout", revision=7,
            next_review=datetime.now(timezone.utc)))
        db.session.commit()
        # All tables except the newly introduced reflection table must be byte-for-byte unchanged.
        def snapshot():
            return {name: [dict(row) for row in db.session.execute(table.select()).mappings()]
                for name, table in db.metadata.tables.items() if name != "concept_self_assessment"}
        before = snapshot()
        service.save(1, "idempotency", **checkin(recognition="without_help"))
        progress.save_position(1, "idempotency", **position(2, "design"))
        self.assertEqual(service.save(1, "idempotency", **checkin(1))["revision"], 2)
        service.clear_history(1, "idempotency", **clear(2))
        after = snapshot()
        # Bookmark changed only because of the explicit, intervening bookmark save.
        after.pop("user_concept_progress")
        before.pop("user_concept_progress")
        self.assertEqual(after, before)
        self.assertEqual(progress.progress(1, "idempotency")["revision"], bookmark["revision"] + 1)
