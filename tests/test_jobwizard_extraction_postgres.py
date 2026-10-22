"""Real cross-process extraction exclusion, crash recovery and migration."""
import importlib.util
import os
from pathlib import Path
import select
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from project.database import db
from project.models import Job, JobExtraction
from project.services import jobwizard_extraction as service
from tests import test_jobwizard_postgres as fixtures
from tests.test_jobwizard_extraction_service import URL as SOURCE_URL, SOURCE, RESULT


@unittest.skipUnless(fixtures.URL, 'Requires isolated PostgreSQL')
class ExtractionPostgresTests(unittest.TestCase):
    setUp = fixtures.JobwizardPostgresTests.setUp
    tearDown = fixtures.JobwizardPostgresTests.tearDown

    def test_populated_migration_preserves_jobs_captures_and_receipts(self):
        from project.services.jobwizard_service import mutate_job
        saved = mutate_job(user_id=1, payload=dict(self.payload, request_id=str(uuid4())))
        job = db.session.get(Job, saved['job']['id']); job.listing_image = 'legacy.jpeg'; db.session.commit()
        before = (job.id, job.user_id, job.title, job.listing_image, job.posted_date, job.revision)
        spec = importlib.util.spec_from_file_location('extraction_migration', Path(__file__).resolve().parents[1] / 'migrations/versions/f2a3b4c5d6e7_jobwizard_extraction.py')
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration); db.session.remove()
        with db.engine.begin() as connection, patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            migration.downgrade(); migration.upgrade()
            row = connection.execute(text('SELECT id,user_id,title,listing_image,posted_date,revision,accepted_details FROM jobs')).one()
            self.assertEqual(tuple(row[:6]), before); self.assertIsNone(row.accepted_details)
            self.assertEqual(connection.execute(text('SELECT count(*) FROM job_mutation_receipt')).scalar(), 1)

    def test_process_death_duplicate_and_new_account_request(self):
        aid = str(uuid4()); payload = dict(request_id=aid, listing_url=SOURCE_URL)
        script = f'''from unittest.mock import patch
from project import create_app
from project.services.jobwizard_extraction import start
with create_app({self.config!r}).app_context():
    def blocked(*args, **kwargs):
        print("READY", flush=True)
        input()
    with patch('project.services.jobwizard_extraction.configured', return_value=True), patch('project.services.jobwizard_extraction._run', blocked):
        start(user_id=1, payload={payload!r})
'''
        child = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 15)[0]); self.assertEqual(child.stdout.readline().strip(), 'READY')
            with patch.object(service, '_run') as provider:
                self.assertEqual(service.start(user_id=1, payload=payload)['status'], 'running')
                self.assertEqual(service.status(user_id=1, attempt_id=aid)['status'], 'running')
                with self.assertRaises(service.SuggestionError): service.start(user_id=1, payload=dict(payload, request_id=str(uuid4())))
                provider.assert_not_called()
        finally:
            child.terminate(); child.communicate(timeout=10)
        self.assertEqual(service.status(user_id=1, attempt_id=aid)['status'], 'interrupted')
        self.assertEqual(JobExtraction.query.count(), 1)

    def test_summary_replay_after_process_boundary_and_stale_revision(self):
        aid = str(uuid4())
        with patch.object(service, 'configured', return_value=True), patch.object(service, '_run', return_value=dict(source=SOURCE, seconds=1)):
            service.start(user_id=1, payload=dict(request_id=aid, listing_url=SOURCE_URL))
        with patch.dict(os.environ, OPENAI_API_KEY='fixture'), patch.object(service, 'configured', return_value=True), patch.object(service, '_run', return_value=dict(result=RESULT, seconds=1)) as provider:
            self.assertEqual(service.summarize(user_id=1, attempt_id=aid)['status'], 'complete')
            self.assertEqual(service.summarize(user_id=1, attempt_id=aid)['status'], 'complete')
            self.assertEqual(provider.call_count, 1)
        script = f'''from project import create_app
from project.services.jobwizard_extraction import status
with create_app({self.config!r}).app_context():
    print(status(user_id=1, attempt_id={aid!r})['status'])
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(result.stdout.strip(), 'complete')
