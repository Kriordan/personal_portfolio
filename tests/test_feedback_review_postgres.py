"""Real PostgreSQL serialization of feedback decisions, ratings, and deletion."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
from threading import Barrier, Event
import unittest
from uuid import uuid4

from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import LearningAICharge, PracticeFeedbackAnnotation, PracticeReceipt, ReviewLog, ReviewProgress, User
from project.services import feedback_review_service as review, learning_service, practice_service as practice
from project.services.curriculum_service import import_catalog
from tests.curriculum_v2_fixtures import publish_feedback_catalog
from tests.test_feedback_review import completed_feedback

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class FeedbackReviewPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing destructive fixtures outside the isolated local test database")
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL,
            LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="fixture1@example.test"))
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(id=1, username="Feedback fixture", email="fixture1@example.test", email_verified=True)
        db.session.add(user)
        db.session.commit()
        import_catalog(load_catalog(ROOT / "curriculum/idempotency/catalog.json"), dry_run=False, publish=True,
            reviewed_by="Disposable fixture", reviewed_on=date(2026, 10, 1))
        publish_feedback_catalog()
        self.sid, self.seq, self.rid = completed_feedback(user)
        db.session.remove()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def annotate(self, user, **kwargs):
        return review.annotate(user, self.sid, self.seq, "f2", **{
            "decision": "agree", "note": "Test both first attempts.", "expected_revision": 0,
            "request_id": str(uuid4()), **kwargs})

    def accept_and_attempt(self):
        self.annotate(db.session.get(User, 1))
        card = review.review_detail(1, self.sid, self.seq, "f2")["questions"][0]
        attempt = dict(card_id=card["card_id"], content_version=card["content_version"],
            expected_revision=card["progress_revision"], request_id=str(uuid4()), rating=4)
        db.session.remove()
        return attempt

    def rate(self, user, attempt):
        return review.rate_review(user, self.sid, self.seq, "f2", **attempt)

    def delete(self, user):
        return practice.delete_session(user, self.sid)

    def run_operation(self, operation, barrier=None):
        with self.app.app_context():
            user = db.session.get(User, 1)
            if barrier:
                barrier.wait(timeout=10)
            try:
                return operation(user)
            except learning_service.ConflictError as exc:
                return type(exc).__name__
            except learning_service.NotFoundError:
                return "NotFoundError"

    def race(self, operations):
        barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.run_operation, operation, barrier) for operation in operations]
            return [future.result(timeout=15) for future in futures]

    def ordered(self, first, second):
        """Hold the actual owner row lock before starting the competing transaction."""
        locked, competing = Event(), Event()

        def leader(user):
            practice._lock_owner(user.id)
            locked.set()
            self.assertTrue(competing.wait(timeout=10))
            return first(user)

        def follower(user):
            self.assertTrue(locked.wait(timeout=10))
            competing.set()
            return second(user)

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.run_operation, operation) for operation in (leader, follower)]
            return [future.result(timeout=15) for future in futures]

    def test_concurrent_annotation_replays_commit_one_revision_and_receipt(self):
        request_id = str(uuid4())
        operation = lambda user: self.annotate(user, request_id=request_id)
        results = self.race([operation, operation])
        self.assertEqual(results[0], results[1])
        self.assertEqual(PracticeFeedbackAnnotation.query.one().revision, 1)
        self.assertEqual(PracticeReceipt.query.filter_by(operation="annotate").count(), 1)
        self.assertEqual(ReviewLog.query.count(), 0)

    def test_two_annotation_drafts_do_not_overwrite_each_other(self):
        results = self.race([lambda user: self.annotate(user, note="First tab"),
                             lambda user: self.annotate(user, note="Second tab")])
        self.assertEqual(results.count("AnnotationConflict"), 1)
        self.assertEqual(PracticeFeedbackAnnotation.query.one().revision, 1)
        self.assertEqual(PracticeReceipt.query.filter_by(operation="annotate").count(), 1)

    def test_concurrent_rating_replays_change_the_schedule_once(self):
        attempt = self.accept_and_attempt()
        operation = lambda user: self.rate(user, attempt)
        results = self.race([operation, operation])
        self.assertEqual(results[0], results[1])
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)

    def test_distinct_rating_attempts_cannot_finish_a_question_twice(self):
        attempt = self.accept_and_attempt()
        results = self.race([lambda user: self.rate(user, attempt),
            lambda user: self.rate(user, dict(attempt, request_id=str(uuid4())))])
        self.assertEqual(results.count("StaleReviewError"), 1)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)

    def test_withdrawal_before_rating_blocks_the_new_rating(self):
        attempt = self.accept_and_attempt()
        results = self.ordered(lambda user: self.annotate(user, decision="disagree", expected_revision=1),
            lambda user: self.rate(user, attempt))
        self.assertEqual(results[1], "DecisionRequired")
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assertEqual(ReviewProgress.query.count(), 0)

    def test_rating_before_withdrawal_remains_saved_and_replayable(self):
        attempt = self.accept_and_attempt()
        results = self.ordered(lambda user: self.rate(user, attempt),
            lambda user: self.annotate(user, decision="disagree", expected_revision=1))
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(self.rate(db.session.get(User, 1), attempt), results[0])
        self.assertEqual(ReviewProgress.query.one().revision, 1)

    def test_annotation_before_delete_cascades_without_orphans(self):
        self.ordered(self.annotate, self.delete)
        self.assertEqual(PracticeFeedbackAnnotation.query.count(), 0)
        self.assertEqual(PracticeReceipt.query.count(), 0)
        self.assertEqual(LearningAICharge.query.count(), 1)

    def test_delete_before_annotation_does_not_recreate_private_content(self):
        results = self.ordered(self.delete, self.annotate)
        self.assertEqual(results[1], "NotFoundError")
        self.assertEqual(PracticeFeedbackAnnotation.query.count(), 0)
        self.assertEqual(PracticeReceipt.query.count(), 0)

    def test_rating_before_delete_preserves_explicit_review_history(self):
        attempt = self.accept_and_attempt()
        self.ordered(lambda user: self.rate(user, attempt), self.delete)
        self.assertEqual(PracticeFeedbackAnnotation.query.count(), 0)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)

    def test_delete_before_rating_saves_no_new_rating(self):
        attempt = self.accept_and_attempt()
        results = self.ordered(self.delete, lambda user: self.rate(user, attempt))
        self.assertEqual(results[1], "NotFoundError")
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assertEqual(ReviewProgress.query.count(), 0)
