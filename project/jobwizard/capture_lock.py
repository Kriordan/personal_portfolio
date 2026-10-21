"""Session locks survive commits and are released on process death."""
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import text
from project.database import db

_guard = Lock()
_locks = {}
NAMESPACE = 741938205


@contextmanager
def capture_lock(job_id):
    if db.engine.dialect.name == "sqlite":
        # Single-process disposable fixtures only; production uses PostgreSQL.
        with _guard:
            lock = _locks.setdefault(job_id, Lock())
        acquired = lock.acquire(blocking=False)
        try:
            yield (lambda: None) if acquired else None
        finally:
            if acquired:
                lock.release()
        return
    if db.engine.dialect.name != "postgresql":
        raise RuntimeError("Capture requires PostgreSQL")
    with db.engine.connect() as connection:
        params = dict(namespace=NAMESPACE, job_id=job_id)
        acquired = connection.execute(text("SELECT pg_try_advisory_lock(:namespace, :job_id)"), params).scalar()
        pid = connection.execute(text("SELECT pg_backend_pid()")).scalar() if acquired else None
        connection.commit()
        def fence():
            if connection.closed or connection.invalidated:
                raise RuntimeError("Capture lock lost")
            current_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar()
            held = connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory' AND classid=:namespace AND objid=:job_id AND objsubid=2 AND granted)"), params).scalar()
            connection.commit()
            if current_pid != pid or not held:
                raise RuntimeError("Capture lock lost")
        try:
            yield fence if acquired else None
        finally:
            if acquired:
                try:
                    connection.execute(text("SELECT pg_advisory_unlock(:namespace, :job_id)"), params)
                    connection.commit()
                except Exception:
                    connection.invalidate()
