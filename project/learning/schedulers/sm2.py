from project.learning.scheduler_config import SCHEDULER_VERSION
from project.learning.spaced_repetition import compute_schedule

from . import BaseScheduler, ScheduleInput, ScheduleOutput


class SM2Scheduler(BaseScheduler):
    def compute(self, inp: ScheduleInput) -> ScheduleOutput:
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
            scheduler_version=SCHEDULER_VERSION,
        )
