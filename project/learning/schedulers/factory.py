from . import BaseScheduler
from .hlr import HLRScheduler
from .sm2 import SM2Scheduler

_SCHEDULERS = {
    "sm2_v2_steps": SM2Scheduler,
    "hlr_v1": HLRScheduler,
}


def get_scheduler(name: str) -> BaseScheduler:
    cls = _SCHEDULERS.get(name, SM2Scheduler)
    return cls()
