from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from project.database import db
from project.learning.schedulers.factory import get_scheduler
from project.learning.schedulers import ScheduleInput
from project.models import ReviewLog, ReviewProgress


def evaluate_scheduler(user_id: int, days: int = 30) -> dict:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    logs = (
        ReviewLog.query.filter(
            ReviewLog.user_id == user_id,
            ReviewLog.reviewed_at >= start,
        )
        .all()
    )

    total = len(logs)
    successes = sum(1 for log in logs if log.rating >= 3)
    lapses = sum(1 for log in logs if log.rating < 3)

    reviews_per_day = (
        db.session.query(func.count())
        .filter(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= start)
        .scalar()
        or 0
    ) / max(1, days)

    avg_half_life_growth = _average_half_life_growth(logs)

    by_scheduler = {}
    for version in {log.scheduler_version for log in logs if log.scheduler_version}:
        version_logs = [log for log in logs if log.scheduler_version == version]
        by_scheduler[version] = {
            "success_rate": _ratio(
                sum(1 for log in version_logs if log.rating >= 3), len(version_logs)
            ),
            "lapse_rate": _ratio(
                sum(1 for log in version_logs if log.rating < 3), len(version_logs)
            ),
            "avg_half_life_growth": _average_half_life_growth(version_logs),
        }

    return {
        "success_rate": _ratio(successes, total),
        "lapse_rate": _ratio(lapses, total),
        "reviews_per_day": reviews_per_day,
        "avg_half_life_growth": avg_half_life_growth,
        "by_scheduler": by_scheduler,
    }


def replay_simulation(user_id: int, scheduler_name: str, days: int = 30) -> dict:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    logs = (
        ReviewLog.query.filter(
            ReviewLog.user_id == user_id,
            ReviewLog.reviewed_at >= start,
        )
        .order_by(ReviewLog.reviewed_at)
        .all()
    )

    scheduler = get_scheduler(scheduler_name)

    predicted_vs_actual = []
    calibration_errors = []

    for log in logs:
        progress = (
            ReviewProgress.query.filter_by(
                user_id=log.user_id, card_id=log.card_id
            ).one_or_none()
        )
        if progress is None:
            continue

        inp = ScheduleInput(
            learning_state=log.learning_state_before or "review",
            step_index=log.step_index_before,
            easiness=log.easiness_before,
            interval=log.interval_before,
            repetitions=log.repetitions_before,
            lapses=log.lapses_before or 0,
            half_life_days=log.half_life_before,
            predicted_recall=log.predicted_recall_before,
            target_recall=log.target_recall or progress.target_recall,
            rating=log.rating,
            now=log.reviewed_at,
            last_reviewed=progress.last_reviewed,
        )

        out = scheduler.compute(inp)
        predicted = out.predicted_recall
        actual = 1 if log.rating >= 3 else 0
        if predicted is not None:
            calibration_errors.append(abs(predicted - actual))

        predicted_vs_actual.append(
            {
                "card_id": log.card_id,
                "predicted_recall": predicted,
                "actual_outcome": actual,
            }
        )

    calibration_error = (
        sum(calibration_errors) / len(calibration_errors) if calibration_errors else 0.0
    )

    return {
        "predicted_vs_actual": predicted_vs_actual,
        "calibration_error": calibration_error,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _average_half_life_growth(logs) -> float:
    values = [
        log.half_life_after / log.half_life_before
        for log in logs
        if log.half_life_before and log.half_life_after and log.half_life_before > 0
    ]
    if not values:
        return 0.0
    return sum(values) / len(values)
