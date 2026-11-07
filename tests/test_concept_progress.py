"""Opt-in study, immutable existing work, and recoverable bookmarks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.models import ContentRevision, ReviewLog, ReviewProgress, ReviewReceipt, User, UserConceptProgress
from project.services import concept_progress_service as service, curriculum_service, learning_service, practice_service
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError
from tests.test_practice_web import PracticeWebCase


def position(revision=1, section="retries", version=1):
    return dict(content_version=version, section_id=section, expected_revision=revision, request_id=str(uuid4()))


class ConceptProgressTests(PracticeWebCase):
    def test_browsing_is_read_only_and_enrollment_is_explicit_idempotent_and_owned(self):
        for path in ("/learning/", "/learning/concepts/idempotency", "/learning/concepts/idempotency/review"):
            self.assertEqual(self.get(path).status_code, 200)
        self.assertEqual(UserConceptProgress.query.count(), 0)
        concept = service.published_concept("idempotency")
        self.assertEqual(curriculum_service.concept_review_queue(concept, user_id=1), [])
        saved = service.enroll(1, "idempotency")
        self.assertEqual(service.enroll(1, "idempotency"), saved)
        self.assertEqual(saved["revision"], 1)
        self.assertIsNone(service.progress(2, "idempotency"))
        self.assertEqual(len(curriculum_service.concept_review_queue(concept, user_id=1)), 4)
        self.assertEqual(curriculum_service.concept_review_queue(concept, user_id=2), [])
        self.assertEqual(ReviewProgress.query.count(), 0)

    def test_existing_reviews_and_sessions_survive_without_enrollment(self):
        user = db.session.get(User, 1)
        session_id = self.start()
        practice_service.save_work(user, session_id, request_id=str(uuid4()), status="paused",
            edits=[dict(artifact_id="api", base_revision=0, language="text", body="My saved design")])
        before = practice_service.session_detail(1, session_id)
        home = self.get("/learning/")
        self.assertIn(b"Start learning", home.data)
        self.assertIn(b"Continue practice", home.data)
        self.assertIn(session_id.encode(), home.data)
        db.session.add(ReviewProgress(user_id=1, card_id="idempotency:timeout", revision=4,
            next_review=datetime.now(timezone.utc) - timedelta(days=1)))
        db.session.commit()
        concept = service.published_concept("idempotency")
        queue = curriculum_service.concept_review_queue(concept, user_id=1)
        self.assertEqual([card["card_id"] for card in queue], ["idempotency:timeout"])
        review = [dict(row) for row in db.session.execute(ReviewProgress.__table__.select()).mappings()]
        service.enroll(1, "idempotency")
        service.save_position(1, "idempotency", **position())
        self.assertEqual(practice_service.session_detail(1, session_id), before)
        self.assertEqual([dict(row) for row in db.session.execute(ReviewProgress.__table__.select()).mappings()], review)
        self.assertEqual((ReviewLog.query.count(), ReviewReceipt.query.count()), (0, 0))

    def test_bookmark_replay_and_stale_tabs_never_overwrite_a_newer_position(self):
        service.enroll(1, "idempotency")
        first = position()
        saved = service.save_position(1, "idempotency", **first)
        self.assertEqual(service.save_position(1, "idempotency", **first), saved)
        with self.assertRaises(ConflictError):
            service.save_position(1, "idempotency", **dict(first, section_id="design"))
        with self.assertRaises(ConflictError):
            service.save_position(1, "idempotency", **position(section="design"))
        latest = service.save_position(1, "idempotency", **position(2, "design"))
        with self.assertRaises(ConflictError):
            service.save_position(1, "idempotency", **first)
        self.assertEqual(service.progress(1, "idempotency"), latest)
        self.assertEqual(service.enroll(1, "idempotency"), latest)

    def test_invalid_or_unenrolled_positions_cannot_create_progress(self):
        with self.assertRaises(ConflictError):
            service.save_position(1, "idempotency", **position())
        for payload in (dict(position(), content_version=True), dict(position(), expected_revision=0),
                        dict(position(), section_id="<script>"), dict(position(), request_id="bad")):
            with self.assertRaises(ValidationError):
                service.save_position(1, "idempotency", **payload)
        for concept_id in ("missing", "idempotent-order-api", "idempotency:timeout"):
            with self.assertRaises(NotFoundError):
                service.enroll(1, concept_id)
        self.assertEqual(UserConceptProgress.query.count(), 0)

    def test_failed_commits_roll_back_and_same_request_can_recover(self):
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("fixture")):
            with self.assertRaises(SQLAlchemyError):
                service.enroll(1, "idempotency")
        self.assertIsNone(service.progress(1, "idempotency"))
        enrolled = service.enroll(1, "idempotency")
        payload = position()
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("fixture")):
            with self.assertRaises(SQLAlchemyError):
                service.save_position(1, "idempotency", **payload)
        self.assertEqual(service.progress(1, "idempotency"), enrolled)
        self.assertEqual(service.save_position(1, "idempotency", **payload)["revision"], 2)

    def test_content_changes_preserve_bookmarks_and_removed_sections_fall_back(self):
        service.enroll(1, "idempotency")
        saved = service.save_position(1, "idempotency", **position())
        previous = db.session.get(ContentRevision, ("idempotency", 1))
        revised = deepcopy(previous.payload)
        revised["version"] = 2
        revised["content"]["sections"] = [s for s in revised["content"]["sections"] if s["id"] != "retries"]
        now = datetime.now(timezone.utc)
        db.session.add(ContentRevision(item_id="idempotency", version=2, schema_version=1, payload=revised,
            checksum=curriculum_service.content_checksum(revised), imported_at=now, published_at=now,
            reviewed_by="Fixture", reviewed_on=now.date()))
        db.session.commit()
        self.assertEqual(service.resume_section(previous.payload, saved)["id"], "retries")
        self.assertIsNone(service.resume_section(service.published_concept("idempotency"), saved))
        self.assertEqual(service.progress(1, "idempotency"), saved)
        self.assertEqual(service.save_position(1, "idempotency", **position(2, "design", 2))["reading_version"], 2)
