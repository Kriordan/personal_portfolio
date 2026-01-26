import math
from datetime import timedelta

from project.learning.scheduler_config import (
    HLR_DEFAULT_TARGET_RECALL,
    HLR_CONFIDENCE_CHECK_INTERVAL_DAYS,
    HLR_GRADUATION_HALF_LIFE_DAYS,
    HLR_HALF_LIFE_MULTIPLIERS,
    HLR_INITIAL_HALF_LIFE,
    HLR_LAPSE_MULTIPLIER,
    HLR_MAX_HALF_LIFE,
    HLR_MIN_HALF_LIFE,
    HLR_MIN_INTERVAL_HOURS,
    HLR_SCHEDULER_VERSION,
)
from project.learning.spaced_repetition import compute_schedule

from . import BaseScheduler, ScheduleInput, ScheduleOutput


def predict_recall(half_life_days: float, days_elapsed: float) -> float:
    if half_life_days <= 0:
        return 0.0
    return 2 ** (-days_elapsed / half_life_days)


def next_review_days(half_life_days: float, target_recall: float) -> float:
    if target_recall <= 0 or target_recall >= 1:
        return half_life_days
    return -half_life_days * math.log2(target_recall)


class HLRScheduler(BaseScheduler):
    def compute(self, inp: ScheduleInput) -> ScheduleOutput:
        target_recall = inp.target_recall or HLR_DEFAULT_TARGET_RECALL

        if inp.learning_state in {"learning", "relearning", "new"}:
            schedule = compute_schedule(
                inp.learning_state,
                inp.step_index,
                inp.easiness,
                inp.interval,
                inp.repetitions,
                inp.lapses,
                inp.rating,
                inp.now,
            )
            return ScheduleOutput(
                learning_state=schedule["learning_state"],
                step_index=schedule["step_index"],
                easiness=schedule["easiness"],
                interval=schedule["interval"],
                repetitions=schedule["repetitions"],
                lapses=schedule["lapses"],
                half_life_days=inp.half_life_days,
                predicted_recall=inp.predicted_recall,
                next_review=schedule["next_review"],
                scheduler_version=HLR_SCHEDULER_VERSION,
                is_graduated=False,
            )

        half_life = inp.half_life_days or HLR_INITIAL_HALF_LIFE
        days_elapsed = 0.0
        if inp.last_reviewed is not None:
            days_elapsed = max(
                0.0, (inp.now - inp.last_reviewed).total_seconds() / 86400
            )
        predicted_recall_before = predict_recall(half_life, days_elapsed)

        if inp.rating < 3:
            half_life = max(HLR_MIN_HALF_LIFE, half_life * HLR_LAPSE_MULTIPLIER)
            schedule = compute_schedule(
                inp.learning_state,
                inp.step_index,
                inp.easiness,
                inp.interval,
                inp.repetitions,
                inp.lapses,
                inp.rating,
                inp.now,
            )
            predicted_recall_after = predict_recall(half_life, 0.0)
            return ScheduleOutput(
                learning_state=schedule["learning_state"],
                step_index=schedule["step_index"],
                easiness=schedule["easiness"],
                interval=schedule["interval"],
                repetitions=schedule["repetitions"],
                lapses=schedule["lapses"],
                half_life_days=half_life,
                predicted_recall=predicted_recall_after,
                next_review=schedule["next_review"],
                scheduler_version=HLR_SCHEDULER_VERSION,
                debug_info={
                    "predicted_recall_before": predicted_recall_before,
                    "predicted_recall_after": predicted_recall_after,
                },
                is_graduated=False,
            )

        multiplier = HLR_HALF_LIFE_MULTIPLIERS.get(inp.rating, 1.0)
        half_life = min(HLR_MAX_HALF_LIFE, half_life * multiplier)

        predicted_recall_after = predict_recall(half_life, 0.0)
        days_until = next_review_days(half_life, target_recall)
        min_interval_days = HLR_MIN_INTERVAL_HOURS / 24
        days_until = max(min_interval_days, days_until)
        days_until = min(HLR_MAX_HALF_LIFE, days_until)

        next_review = inp.now + timedelta(days=days_until)
        is_graduated = False
        if half_life >= HLR_GRADUATION_HALF_LIFE_DAYS:
            next_review = inp.now + timedelta(days=HLR_CONFIDENCE_CHECK_INTERVAL_DAYS)
            days_until = HLR_CONFIDENCE_CHECK_INTERVAL_DAYS
            is_graduated = True

        return ScheduleOutput(
            learning_state="review",
            step_index=None,
            easiness=inp.easiness,
            interval=max(1, int(round(days_until))),
            repetitions=inp.repetitions,
            lapses=inp.lapses,
            half_life_days=half_life,
            predicted_recall=predicted_recall_after,
            next_review=next_review,
            scheduler_version=HLR_SCHEDULER_VERSION,
            debug_info={
                "predicted_recall_before": predicted_recall_before,
                "predicted_recall_after": predicted_recall_after,
                "days_until": days_until,
            },
            is_graduated=is_graduated,
        )
