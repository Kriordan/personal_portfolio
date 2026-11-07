"""Real PostgreSQL first-write races, bookmark fencing and additive DDL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import select as io_select
import subprocess
import sys
from threading import Barrier
import unittest
from unittest.mock import patch

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, stamp, upgrade
from sqlalchemy import text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.models import ReviewProgress, User, UserConceptProgress
from project.services import concept_progress_service as service, practice_service
from project.services.learning_errors import ConflictError
from tests.test_concept_progress import position
from tests.test_practice_service import seed_catalog

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated test database")
class ConceptProgressPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing fixtures outside the isolated local test database")
        self.config = dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL,
                           LEARNING_PRACTICE_ENABLED=True)
        self.app = create_app(self.config)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(User(id=1, username="fixture", email="fixture@example.test"))
        db.session.commit()
        seed_catalog(self)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.engine.dispose()
        self.context.pop()

    def race(self, operation, payloads):
        barrier = Barrier(2)
        def run(payload):
            with self.app.app_context():
                # Preload the row to catch accidental stale identity-map reads.
                service.progress(1, "idempotency")
                barrier.wait(timeout=10)
                try:
                    return operation(1, "idempotency", **payload)
                except ConflictError:
                    return "conflict"
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(run, payload) for payload in payloads]
            return [future.result(timeout=15) for future in futures]

    def test_concurrent_first_enrollment_creates_one_row(self):
        results = self.race(service.enroll, [{}, {}])
        self.assertEqual(results[0], results[1])
        self.assertEqual(UserConceptProgress.query.count(), 1)
        self.assertEqual(ReviewProgress.query.count(), 0)

    def test_concurrent_retries_save_once_and_competing_tabs_are_fenced(self):
        service.enroll(1, "idempotency")
        payload = position()
        results = self.race(service.save_position, [payload, payload])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["revision"], 2)
        results = self.race(service.save_position, [position(2, "overview"), position(2, "design")])
        self.assertEqual(results.count("conflict"), 1)
        db.session.expire_all()
        self.assertEqual(service.progress(1, "idempotency")["revision"], 3)
        with self.assertRaises(ConflictError):
            service.save_position(1, "idempotency", **payload)

    def test_enrollment_retry_cannot_reset_an_in_flight_bookmark(self):
        service.enroll(1, "idempotency")
        barrier = Barrier(2)
        def run(save):
            with self.app.app_context():
                barrier.wait(timeout=10)
                return (service.save_position(1, "idempotency", **position()) if save
                        else service.enroll(1, "idempotency"))
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(run, save) for save in (True, False)]
            [future.result(timeout=15) for future in futures]
        db.session.expire_all()
        self.assertEqual(service.progress(1, "idempotency")["reading_section"], "retries")
        self.assertEqual(service.progress(1, "idempotency")["revision"], 2)

    def test_process_death_rolls_back_and_retry_recovers(self):
        service.enroll(1, "idempotency")
        payload = position()
        script = f'''
from unittest.mock import patch
from project import create_app
from project.database import db
from project.services import concept_progress_service as service
with create_app({self.config!r}).app_context():
    def stop_before_commit():
        db.session.flush()
        print("READY", flush=True)
        input()
    with patch.object(db.session, "commit", stop_before_commit):
        service.save_position(1, "idempotency", **{payload!r})
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(io_select.select([child.stdout], [], [], 15)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
            self.assertEqual(service.progress(1, "idempotency")["revision"], 1)
        finally:
            child.terminate()
            child.communicate(timeout=10)
        self.assertEqual(service.save_position(1, "idempotency", **payload)["revision"], 2)

    @patch("logging.config.fileConfig")
    def test_migration_and_downgrade_preserve_existing_history(self, _logging):
        from uuid import uuid4
        now = datetime.now(timezone.utc)
        db.session.add(ReviewProgress(user_id=1, card_id="idempotency:timeout", revision=7, next_review=now))
        db.session.commit()
        session_id = practice_service.start_session(db.session.get(User, 1),
            exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
        before = practice_service.session_detail(1, session_id)
        review = [dict(row) for row in db.session.execute(ReviewProgress.__table__.select()).mappings()]
        directory = str(ROOT / "migrations")
        db.session.remove()
        stamp(directory=directory, revision="head")
        downgrade(directory=directory, revision="c2d3e4f5a6b7")
        upgrade(directory=directory, revision="head")
        self.assertEqual(UserConceptProgress.query.count(), 0)
        service.enroll(1, "idempotency")
        service.save_position(1, "idempotency", **position())
        db.session.remove()
        downgrade(directory=directory, revision="c2d3e4f5a6b7")
        upgrade(directory=directory, revision="head")
        self.assertEqual(UserConceptProgress.query.count(), 0)
        self.assertEqual(practice_service.session_detail(1, session_id), before)
        self.assertEqual([dict(row) for row in db.session.execute(ReviewProgress.__table__.select()).mappings()], review)
        with db.engine.connect() as connection:
            self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
            checks = dict(connection.execute(text("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'user_concept_progress'::regclass AND contype = 'c'")).all())
            self.assertEqual(set(checks), {"ck_concept_progress_revision", "ck_concept_progress_reading"})
