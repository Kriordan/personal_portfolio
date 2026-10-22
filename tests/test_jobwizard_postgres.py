"""Concurrency and migration tests against an explicitly disposable PostgreSQL DB."""
import importlib.util
import os
from pathlib import Path
import select
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.models import Job, JobCapture, JobMutationReceipt, User
from project.services import jobwizard_capture as capture, jobwizard_service as service

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class JobwizardPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing fixtures outside the isolated local test database")
        self.config = dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL)
        self.app = create_app(self.config)
        self.context = self.app.app_context(); self.context.push()
        db.create_all()
        db.session.add(User(id=1, username="jobs", email="jobs@example.test")); db.session.commit()
        self.payload = dict(title="Engineer", company_name="Acme", listing_url="https://example.com/job")

    def tearDown(self):
        db.session.remove(); db.drop_all(); db.engine.dispose(); self.context.pop()

    def submit(self, payload, job_id=None, barrier=None):
        with self.app.app_context():
            if barrier: barrier.wait(timeout=10)
            try: return service.mutate_job(user_id=1, payload=payload, job_id=job_id)
            except service.StaleJobError: return "stale"

    def test_concurrent_creates_replay_one_committed_receipt(self):
        payload = dict(self.payload, request_id=str(uuid4())); barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            results = [future.result(timeout=15) for future in [pool.submit(self.submit, payload, None, barrier) for _ in range(2)]]
        self.assertEqual(results[0], results[1]); self.assertEqual(Job.query.count(), 1); self.assertEqual(JobMutationReceipt.query.count(), 1)
        script = f'''from project import create_app
from project.services.jobwizard_service import mutation_receipt
with create_app({self.config!r}).app_context():
    print(mutation_receipt(1, {payload['request_id']!r})['job']['id'])
'''
        result = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True, timeout=15, check=True)
        self.assertEqual(int(result.stdout.strip()), results[0]["job"]["id"])

    def test_two_devices_cannot_overwrite_same_revision(self):
        job_id = self.submit(self.payload)["job"]["id"]; barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.submit, dict(expected_revision=0, archived=value, request_id=str(uuid4())), job_id, barrier) for value in (True, False)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results.count("stale"), 1); self.assertEqual(Job.query.one().revision, 1)

    def test_process_death_recovers_capture_and_duplicate_cannot_call_provider(self):
        job_id = self.submit(self.payload)["job"]["id"]; request_id = str(uuid4())
        script = f'''from unittest.mock import patch
from project import create_app
from project.services.jobwizard_capture import capture_job
with create_app({self.config!r}).app_context():
    def blocked(url, key):
        print("READY", flush=True)
        input()
    with patch('project.services.jobwizard_capture.configured', return_value=True), patch('project.services.jobwizard_capture._run_capture', blocked):
        capture_job(user_id=1, job_id={job_id}, payload=dict(request_id={request_id!r}, expected_revision=0))
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 15)[0]); self.assertEqual(child.stdout.readline().strip(), "READY")
            with patch.object(capture, "_run_capture") as provider:
                duplicate = capture.capture_job(user_id=1, job_id=job_id, payload=dict(request_id=request_id, expected_revision=0))
                self.assertTrue(duplicate["busy"]); self.assertEqual(duplicate["requested"]["status"], "running"); provider.assert_not_called()
        finally:
            child.terminate(); child.communicate(timeout=10)
        status = capture.capture_status(user_id=1, job_id=job_id, request_id=request_id)
        self.assertEqual(status["requested"]["status"], "interrupted")
        self.assertEqual(JobCapture.query.count(), 1)

    def test_additive_migration_preserves_legacy_dates_ownership_and_image(self):
        job_id = self.submit(self.payload)["job"]["id"]
        job = db.session.get(Job, job_id); job.listing_image = "/static/img/job_listings/legacy.jpeg"; db.session.commit()
        before = (job.id, job.user_id, job.posted_date, job.listing_image)
        spec = importlib.util.spec_from_file_location("job_migration", Path(__file__).resolve().parents[1] / "migrations/versions/e1f2a3b4c5d6_jobwizard_organizer.py")
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration); db.session.remove()
        with db.engine.begin() as connection, patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            migration.downgrade(); migration.upgrade()
            row = connection.execute(text("SELECT id,user_id,posted_date,listing_image,saved_at,archived_at,revision FROM jobs")).one()
            self.assertEqual(tuple(row[:4]), before); self.assertIsNone(row.saved_at); self.assertIsNone(row.archived_at); self.assertEqual(row.revision, 0)
