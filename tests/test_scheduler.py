import unittest
from datetime import datetime, timedelta, timezone

from project import create_app
from project.database import db
from project.learning.scheduler_config import (
    GRADUATING_INTERVAL_DAYS,
    LEARNING_STEPS,
    POST_LAPSE_INTERVAL_DAYS,
    RELEARNING_STEPS,
)
from project.learning.spaced_repetition import compute_schedule
from project.models import ReviewLog, ReviewProgress, User


class SchedulerUnitTests(unittest.TestCase):
    def test_new_card_enters_learning_step_zero(self):
        now = datetime.now(timezone.utc)
        result = compute_schedule(
            learning_state="new",
            step_index=None,
            easiness=2.5,
            interval=1,
            repetitions=0,
            lapses=0,
            rating=4,
            now=now,
        )

        self.assertEqual(result["learning_state"], "learning")
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(result["next_review"], now + LEARNING_STEPS[0])

    def test_learning_success_advances_step(self):
        now = datetime.now(timezone.utc)
        result = compute_schedule(
            learning_state="learning",
            step_index=0,
            easiness=2.5,
            interval=1,
            repetitions=0,
            lapses=0,
            rating=4,
            now=now,
        )

        self.assertEqual(result["learning_state"], "learning")
        self.assertEqual(result["step_index"], 1)
        self.assertEqual(result["next_review"], now + LEARNING_STEPS[1])

    def test_learning_failure_resets_step(self):
        now = datetime.now(timezone.utc)
        result = compute_schedule(
            learning_state="learning",
            step_index=1,
            easiness=2.5,
            interval=1,
            repetitions=0,
            lapses=0,
            rating=2,
            now=now,
        )

        self.assertEqual(result["learning_state"], "learning")
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(result["next_review"], now + LEARNING_STEPS[0])

    def test_learning_graduates_to_review(self):
        now = datetime.now(timezone.utc)
        result = compute_schedule(
            learning_state="learning",
            step_index=len(LEARNING_STEPS) - 1,
            easiness=2.5,
            interval=1,
            repetitions=0,
            lapses=0,
            rating=4,
            now=now,
        )

        self.assertEqual(result["learning_state"], "review")
        self.assertIsNone(result["step_index"])
        self.assertEqual(result["interval"], GRADUATING_INTERVAL_DAYS)

    def test_review_failure_enters_relearning(self):
        now = datetime.now(timezone.utc)
        result = compute_schedule(
            learning_state="review",
            step_index=None,
            easiness=2.5,
            interval=3,
            repetitions=2,
            lapses=0,
            rating=1,
            now=now,
        )

        self.assertEqual(result["learning_state"], "relearning")
        self.assertEqual(result["step_index"], 0)
        self.assertEqual(result["lapses"], 1)
        self.assertEqual(result["next_review"], now + RELEARNING_STEPS[0])

    def test_relearning_success_returns_to_review(self):
        now = datetime.now(timezone.utc)
        result = compute_schedule(
            learning_state="relearning",
            step_index=len(RELEARNING_STEPS) - 1,
            easiness=2.5,
            interval=4,
            repetitions=2,
            lapses=1,
            rating=4,
            now=now,
        )

        self.assertEqual(result["learning_state"], "review")
        self.assertIsNone(result["step_index"])
        self.assertEqual(result["interval"], POST_LAPSE_INTERVAL_DAYS)


class SchedulerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username="test", email="test@example.com")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_rate_creates_log_and_intra_day_review(self):
        start = datetime.now(timezone.utc)
        response = self.client.post(
            "/learning/rate",
            json={"card_id": "timezone-learning:tz-1", "rating": 2},
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            progress = ReviewProgress.query.one()
            logs = ReviewLog.query.all()

            self.assertEqual(progress.learning_state, "learning")
            self.assertEqual(len(logs), 1)
            self.assertIsNotNone(logs[0].learning_state_after)
            self.assertLessEqual(
                progress.next_review, start + LEARNING_STEPS[0] + timedelta(seconds=5)
            )
