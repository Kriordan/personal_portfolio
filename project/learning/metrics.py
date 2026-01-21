from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from project.database import db
from project.models import ReviewLog


def reviews_per_day(user_id: int, days: int = 7) -> list[dict]:
    """Returns [{date, count}, ...] for the last N days."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            func.date_trunc("day", ReviewLog.reviewed_at).label("day"),
            func.count().label("count"),
        )
        .filter(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= start)
        .group_by(func.date_trunc("day", ReviewLog.reviewed_at))
        .order_by(func.date_trunc("day", ReviewLog.reviewed_at))
        .all()
    )

    return [{"date": row.day.date().isoformat(), "count": row.count} for row in rows]


def lapse_rate(user_id: int, days: int = 30) -> float:
    """Returns % of reviews with rating < 3."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    total = (
        db.session.query(func.count())
        .filter(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= start)
        .scalar()
        or 0
    )
    if total == 0:
        return 0.0

    lapses = (
        db.session.query(func.count())
        .filter(
            ReviewLog.user_id == user_id,
            ReviewLog.reviewed_at >= start,
            ReviewLog.rating < 3,
        )
        .scalar()
        or 0
    )
    return lapses / total


def average_interval_growth(user_id: int, days: int = 30) -> float:
    """Returns avg(interval_after / interval_before) for non-lapse reviews."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            ReviewLog.interval_before,
            ReviewLog.interval_after,
        )
        .filter(
            ReviewLog.user_id == user_id,
            ReviewLog.reviewed_at >= start,
            ReviewLog.rating >= 3,
            ReviewLog.interval_before > 0,
        )
        .all()
    )

    if not rows:
        return 0.0

    total = sum(row.interval_after / row.interval_before for row in rows)
    return total / len(rows)


def cards_reviewed_per_session(user_id: int, days: int = 30) -> list[dict]:
    """Returns review counts grouped by session_id (if available)."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.session.query(
            ReviewLog.session_id.label("session_id"),
            func.count().label("count"),
        )
        .filter(
            ReviewLog.user_id == user_id,
            ReviewLog.reviewed_at >= start,
            ReviewLog.session_id.isnot(None),
        )
        .group_by(ReviewLog.session_id)
        .order_by(func.count().desc())
        .all()
    )

    return [{"session_id": row.session_id, "count": row.count} for row in rows]
