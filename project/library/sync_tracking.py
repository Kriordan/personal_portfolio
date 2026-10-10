"""Shared import exclusion and receipts, independent of the HTTP response lifetime."""
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock

from flask import current_app
from sqlalchemy import text

from project.database import db
from project.models import LibrarySyncRun

LOCK_ID = 741938204
_development_lock = Lock()
INTERRUPTED = "The server stopped before this import completed. Your saved catalog is unchanged. Start a new sync when ready."


@contextmanager
def import_lock():
    """Postgres session lock spans commits and is released if the process dies.

    SQLite is supported only for single-process development/tests. Keep this
    separate connection checked out for the full import; never return a held
    session lock to the pool. Catalog writes have an additional completion fence.
    """
    if db.engine.dialect.name == "sqlite":
        acquired = _development_lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                _development_lock.release()
        return
    if db.engine.dialect.name != "postgresql":
        raise RuntimeError("Library sync requires PostgreSQL or development SQLite")
    with db.engine.connect() as connection:
        acquired = connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}).scalar()
        try:
            connection.commit()
            yield acquired
        finally:
            if acquired:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                    connection.commit()
                except Exception:
                    # A broken connection must not re-enter the pool with a lock.
                    connection.invalidate()
                    current_app.logger.warning("Library import lock connection closed")


def recover_interrupted_runs():
    """Called only with the import lock held, so no live importer owns these rows."""
    LibrarySyncRun.query.filter_by(status="running").update({
        "status": "interrupted", "finished_at": datetime.now(timezone.utc), "error": INTERRUPTED,
    }, synchronize_session=False)
    db.session.commit()


def serialize_run(run):
    if run is None:
        return None
    def iso(value):
        if value is None:
            return None
        return (value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    return {"id": run.id, "status": run.status, "started_at": iso(run.started_at),
            "finished_at": iso(run.finished_at), "summary": run.summary, "error": run.error}


def sync_status(request_id=None):
    with import_lock() as acquired:
        if acquired:
            recover_interrupted_runs()
        # Do not cache a previously read running ORM instance after recovery.
        db.session.expire_all()
        latest = LibrarySyncRun.query.order_by(LibrarySyncRun.started_at.desc(), LibrarySyncRun.id.desc()).first()
        succeeded = LibrarySyncRun.query.filter_by(status="succeeded").order_by(LibrarySyncRun.finished_at.desc()).first()
        requested = db.session.get(LibrarySyncRun, request_id) if request_id else None
        return {"latest": serialize_run(latest), "last_success": serialize_run(succeeded),
                "requested": serialize_run(requested), "busy": not acquired}
