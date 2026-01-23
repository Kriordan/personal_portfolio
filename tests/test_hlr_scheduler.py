import unittest
from datetime import datetime, timezone

from project.learning.scheduler_config import HLR_DEFAULT_TARGET_RECALL
from project.learning.schedulers.hlr import HLRScheduler, next_review_days, predict_recall
from project.learning.schedulers import ScheduleInput


class HLRSchedulerTests(unittest.TestCase):
    def test_predict_recall_half_life(self):
        self.assertAlmostEqual(predict_recall(1.0, 0.0), 1.0)
        self.assertAlmostEqual(predict_recall(1.0, 1.0), 0.5)

    def test_next_review_days_targets_recall(self):
        days = next_review_days(2.0, 0.5)
        self.assertAlmostEqual(days, 2.0)

    def test_hlr_review_success_schedules_future(self):
        scheduler = HLRScheduler()
        now = datetime.now(timezone.utc)
        inp = ScheduleInput(
            learning_state="review",
            step_index=None,
            easiness=2.5,
            interval=3,
            repetitions=2,
            lapses=0,
            half_life_days=1.0,
            predicted_recall=None,
            target_recall=HLR_DEFAULT_TARGET_RECALL,
            rating=4,
            now=now,
            last_reviewed=now,
        )
        out = scheduler.compute(inp)
        self.assertEqual(out.learning_state, "review")
        self.assertGreater(out.half_life_days, 1.0)
        self.assertGreater(out.next_review, now)

    def test_hlr_review_failure_enters_relearning(self):
        scheduler = HLRScheduler()
        now = datetime.now(timezone.utc)
        inp = ScheduleInput(
            learning_state="review",
            step_index=None,
            easiness=2.5,
            interval=3,
            repetitions=2,
            lapses=0,
            half_life_days=1.0,
            predicted_recall=None,
            target_recall=HLR_DEFAULT_TARGET_RECALL,
            rating=1,
            now=now,
            last_reviewed=now,
        )
        out = scheduler.compute(inp)
        self.assertEqual(out.learning_state, "relearning")
        self.assertEqual(out.step_index, 0)
