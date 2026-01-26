from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ScheduleInput:
    learning_state: str
    step_index: Optional[int]
    easiness: float
    interval: int
    repetitions: int
    lapses: int
    half_life_days: Optional[float]
    predicted_recall: Optional[float]
    target_recall: float
    rating: int
    now: datetime
    last_reviewed: Optional[datetime]


@dataclass
class ScheduleOutput:
    learning_state: str
    step_index: Optional[int]
    easiness: float
    interval: int
    repetitions: int
    lapses: int
    half_life_days: Optional[float]
    predicted_recall: Optional[float]
    next_review: datetime
    scheduler_version: str
    debug_info: Optional[dict] = None
    is_graduated: bool = False


class BaseScheduler(ABC):
    @abstractmethod
    def compute(self, inp: ScheduleInput) -> ScheduleOutput:
        raise NotImplementedError
