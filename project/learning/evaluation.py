from datetime import datetime, timedelta, timezone

from project.models import ReviewLog


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

    reviews_per_day = total / max(1, days)

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
