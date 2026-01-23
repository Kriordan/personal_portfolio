from datetime import timedelta

from .scheduler_config import (
    GRADUATING_INTERVAL_DAYS,
    LEARNING_STEPS,
    MIN_EASINESS,
    POST_LAPSE_INTERVAL_DAYS,
    RELEARNING_STEPS,
)


def update_schedule(easiness: float, interval: int, repetitions: int, rating: int):
    """
    Update SM-2 schedule values.

    rating: 0-5 (0=Again, 3=Hard, 4=Good, 5=Easy)
    Returns: (new_easiness, new_interval, new_repetitions)
    """
    if rating < 3:
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = max(1, round(interval * easiness))

    easiness = easiness + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
    easiness = max(1.3, easiness)

    return easiness, interval, repetitions


def compute_schedule(
    learning_state: str,
    step_index: int | None,
    easiness: float,
    interval: int,
    repetitions: int,
    lapses: int,
    rating: int,
    now,
):

    if learning_state not in {"new", "learning", "review", "relearning"}:
        learning_state = "review"
        step_index = None

    if learning_state == "new":
        learning_state = "learning"
        step_index = 0
        next_review = now + LEARNING_STEPS[0]
        return {
            "learning_state": learning_state,
            "step_index": step_index,
            "easiness": max(MIN_EASINESS, easiness),
            "interval": interval,
            "repetitions": repetitions,
            "lapses": lapses,
            "next_review": next_review,
        }

    if learning_state == "learning":
        if rating < 3:
            step_index = 0
            next_review = now + LEARNING_STEPS[0]
            return {
                "learning_state": "learning",
                "step_index": step_index,
                "easiness": max(MIN_EASINESS, easiness),
                "interval": interval,
                "repetitions": repetitions,
                "lapses": lapses,
                "next_review": next_review,
            }

        step_index = (step_index or 0) + 1
        if step_index < len(LEARNING_STEPS):
            next_review = now + LEARNING_STEPS[step_index]
            return {
                "learning_state": "learning",
                "step_index": step_index,
                "easiness": max(MIN_EASINESS, easiness),
                "interval": interval,
                "repetitions": repetitions,
                "lapses": lapses,
                "next_review": next_review,
            }

        interval = GRADUATING_INTERVAL_DAYS
        repetitions = max(1, repetitions)
        next_review = now + timedelta(days=interval)
        return {
            "learning_state": "review",
            "step_index": None,
            "easiness": max(MIN_EASINESS, easiness),
            "interval": interval,
            "repetitions": repetitions,
            "lapses": lapses,
            "next_review": next_review,
        }

    if learning_state == "review":
        if rating < 3:
            lapses += 1
            learning_state = "relearning"
            step_index = 0
            next_review = now + RELEARNING_STEPS[0]
            return {
                "learning_state": learning_state,
                "step_index": step_index,
                "easiness": max(MIN_EASINESS, easiness),
                "interval": interval,
                "repetitions": repetitions,
                "lapses": lapses,
                "next_review": next_review,
            }

        easiness, interval, repetitions = update_schedule(
            easiness, interval, repetitions, rating
        )
        easiness = max(MIN_EASINESS, easiness)
        next_review = now + timedelta(days=interval)
        return {
            "learning_state": "review",
            "step_index": None,
            "easiness": easiness,
            "interval": interval,
            "repetitions": repetitions,
            "lapses": lapses,
            "next_review": next_review,
        }

    if learning_state == "relearning":
        if rating < 3:
            step_index = 0
            next_review = now + RELEARNING_STEPS[0]
            return {
                "learning_state": "relearning",
                "step_index": step_index,
                "easiness": max(MIN_EASINESS, easiness),
                "interval": interval,
                "repetitions": repetitions,
                "lapses": lapses,
                "next_review": next_review,
            }

        step_index = (step_index or 0) + 1
        if step_index < len(RELEARNING_STEPS):
            next_review = now + RELEARNING_STEPS[step_index]
            return {
                "learning_state": "relearning",
                "step_index": step_index,
                "easiness": max(MIN_EASINESS, easiness),
                "interval": interval,
                "repetitions": repetitions,
                "lapses": lapses,
                "next_review": next_review,
            }

        interval = POST_LAPSE_INTERVAL_DAYS
        next_review = now + timedelta(days=interval)
        return {
            "learning_state": "review",
            "step_index": None,
            "easiness": max(MIN_EASINESS, easiness),
            "interval": interval,
            "repetitions": repetitions,
            "lapses": lapses,
            "next_review": next_review,
        }

    return {
        "learning_state": "review",
        "step_index": None,
        "easiness": max(MIN_EASINESS, easiness),
        "interval": interval,
        "repetitions": repetitions,
        "lapses": lapses,
        "next_review": now,
    }
