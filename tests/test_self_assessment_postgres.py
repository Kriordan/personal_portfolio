"""Real PostgreSQL locks, first writes, process loss, constraints and migration."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import select as io_select
import subprocess
import sys
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, stamp, upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from project.database import db
from project.models import ConceptSelfAssessment, ReviewProgress, User
from project.services import self_assessment_service as service, concept_progress_service as progress, practice_service
from project.services.learning_errors import ConflictError
from tests import test_concept_progress_postgres as fixtures
from tests.test_concept_progress import position
from tests.test_self_assessment import checkin, clear


@unittest.skipUnless(fixtures.URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated test database")
class SelfAssessmentPostgresTests(unittest.TestCase):
    setUp = fixtures.ConceptProgressPostgresTests.setUp
    tearDown = fixtures.ConceptProgressPostgresTests.tearDown

    def race(self, operations):
        barrier = Barrier(2)
        def run(operation, payload):
            with self.app.app_context():
                service.history(1, "idempotency")  # Preload: a lock must refresh stale ORM state.
                barrier.wait(timeout=10)
                try:
                    return operation(1, "idempotency", **payload)
                except ConflictError:
                    return "conflict"
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(run, operation, payload) for operation, payload in operations]
            return [future.result(timeout=15) for future in futures]

    def test_first_save_retries_write_once_and_first_competitors_are_fenced(self):
        payload = checkin(recognition="with_help")
        results = self.race([(service.save, payload), (service.save, payload)])
        self.assertEqual(results[0], results[1])
        original = results[0]
        self.assertEqual(results[0]["revision"], 1)
        self.assertEqual(ConceptSelfAssessment.query.count(), 1)
        results = self.race([(service.save, checkin(1, judgment="with_help")), (service.save, checkin(1))])
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(service.history(1, "idempotency")["revision"], 2)
        self.assertEqual(service.save(1, "idempotency", **payload), original)

    def test_different_first_saves_cannot_reuse_revision_one(self):
        results = self.race([(service.save, checkin(recognition="not_yet")), (service.save, checkin(judgment="with_help"))])
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(ConceptSelfAssessment.query.count(), 1)

    def test_bookmark_and_self_assessment_do_not_share_revision_or_overwrite(self):
        progress.enroll(1, "idempotency")
        results = self.race([(service.save, checkin()), (progress.save_position, position())])
        self.assertNotIn("conflict", results)
        db.session.expire_all()
        self.assertEqual(progress.progress(1, "idempotency")["reading_section"], "retries")
        self.assertEqual(service.history(1, "idempotency")["revision"], 1)

    def test_clear_and_save_fence_each_other_and_retries_preserve_later_work(self):
        first = checkin(recognition="without_help")
        service.save(1, "idempotency", **first)
        deletion = clear(1)
        results = self.race([(service.clear_history, deletion), (service.save, checkin(1, application="with_help"))])
        self.assertEqual(results.count("conflict"), 1)
        latest = service.history(1, "idempotency")
        self.assertEqual(latest["revision"], 2)
        if results[0] == "conflict":
            self.assertEqual(latest["current"]["ratings"]["application"], "with_help")
            deletion = clear(2)
            service.clear_history(1, "idempotency", **deletion)
        else:
            self.assertEqual(latest["entries"], [])
        revision = service.history(1, "idempotency")["revision"]
        saved = service.save(1, "idempotency", **checkin(revision, judgment="without_help"))
        service.clear_history(1, "idempotency", **deletion)
        self.assertEqual(service.history(1, "idempotency")["entries"], [saved])
        with self.assertRaises(ConflictError):
            service.save(1, "idempotency", **first)

    def test_process_death_before_commit_rolls_back_and_same_request_recovers(self):
        payload = checkin(recognition="with_help")
        script = f'''
from unittest.mock import patch
from project import create_app
from project.database import db
from project.services import self_assessment_service as service
with create_app({self.config!r}).app_context():
    def stop_before_commit():
        db.session.flush()
        print("READY", flush=True)
        input()
    with patch.object(db.session, "commit", stop_before_commit):
        service.save(1, "idempotency", **{payload!r})
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(io_select.select([child.stdout], [], [], 15)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
            self.assertEqual(service.history(1, "idempotency")["revision"], 0)
        finally:
            child.terminate()
            child.communicate(timeout=10)
        saved = service.save(1, "idempotency", **payload)
        self.assertEqual(service.save(1, "idempotency", **payload), saved)
        self.assertEqual(saved["revision"], 1)

    @patch("logging.config.fileConfig")
    def test_additive_migration_downgrade_and_database_constraints(self, _logging):
        progress.enroll(1, "idempotency")
        bookmark = progress.save_position(1, "idempotency", **position())
        db.session.add(ReviewProgress(user_id=1, card_id="idempotency:timeout", revision=7, next_review=datetime.now(timezone.utc)))
        db.session.commit()
        session_id = practice_service.start_session(db.session.get(User, 1), exercise_id="idempotent-order-api",
                                                   request_id=str(uuid4()))["session_id"]
        practice = practice_service.session_detail(1, session_id)
        reviews = [dict(row) for row in db.session.execute(ReviewProgress.__table__.select()).mappings()]
        directory = str(fixtures.ROOT / "migrations")
        db.session.remove()
        stamp(directory=directory, revision="head")
        downgrade(directory=directory, revision="d3e4f5a6b7c8")
        upgrade(directory=directory, revision="head")
        self.assertEqual(ConceptSelfAssessment.query.count(), 0)
        service.save(1, "idempotency", **checkin())
        for changes in ({"recognition": "mastered"}, {"recognition": None}, {"scale_version": 2},
                        {"deleted": True}, {"kind": "other"}, {"content_version": None},
                        {"revision": 0}, {"content_version": 999}):
            row = db.session.get(ConceptSelfAssessment, (1, "idempotency", 1))
            for key, value in changes.items():
                setattr(row, key, value)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()
        with db.engine.connect() as connection:
            self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
        db.session.remove()
        downgrade(directory=directory, revision="d3e4f5a6b7c8")
        upgrade(directory=directory, revision="head")
        self.assertEqual(progress.progress(1, "idempotency"), bookmark)
        self.assertEqual(practice_service.session_detail(1, session_id), practice)
        self.assertEqual([dict(row) for row in db.session.execute(ReviewProgress.__table__.select()).mappings()], reviews)
        self.assertEqual(ConceptSelfAssessment.query.count(), 0)
