"""Practice persistence on an explicitly disposable PostgreSQL database: races, crashes, constraints."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import os
from pathlib import Path
import select as io_select
import subprocess
import sys
from threading import Barrier
import unittest
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import ArtifactRevision, SessionMessage, SessionMessageArtifact, User
from project.services import practice_service as service
from project.services.curriculum_service import import_catalog

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]
EXERCISE = "idempotent-order-api"


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class PracticePostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing destructive fixtures outside the isolated local test database")
        self.config = dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL)
        self.app = create_app(self.config)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([User(id=i, username=f"practice{i}", email=f"practice{i}@example.test") for i in (1, 2)])
        db.session.commit()
        import_catalog(load_catalog(ROOT / "curriculum/idempotency/catalog.json"), dry_run=False, publish=True,
                       reviewed_by="Fixture reviewer", reviewed_on=date(2026, 10, 1))
        self.session_id = self.start()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def start(self):
        return service.start_session(db.session.get(User, 1), exercise_id=EXERCISE,
                                     request_id=str(uuid4()))["session_id"]

    def save(self, body, *, request_id=None, barrier=None, session_id=None):
        with self.app.app_context():
            user = db.session.get(User, 1)
            if barrier:
                barrier.wait(timeout=10)
            try:
                return service.save_artifacts(user, session_id or self.session_id, request_id=request_id or str(uuid4()),
                    edits=[{"artifact_id": "api", "base_revision": 0, "language": "text", "body": body}])
            except service.StaleArtifactError:
                return "stale"

    def count(self, table, where="TRUE"):
        with db.engine.connect() as connection:
            return connection.execute(text(f"SELECT count(*) FROM {table} WHERE {where}")).scalar()

    def test_two_devices_saving_from_one_base_commit_one_revision_and_one_conflict(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.save, body, barrier=barrier) for body in ("device one", "device two")]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results.count("stale"), 1)
        winner = next(result for result in results if result != "stale")
        self.assertEqual(winner["artifacts"]["api"], {"revision": 1, "changed": True})
        self.assertEqual(self.count("artifact_revision"), 1)

    def test_concurrent_replays_commit_once_and_return_identical_results(self):
        barrier = Barrier(2)
        request_id = str(uuid4())
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.save, "same attempt", request_id=request_id, barrier=barrier) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.count("artifact_revision"), 1)
        self.assertEqual(self.count("practice_receipt", "operation = 'save'"), 1)

    def test_process_death_before_commit_saves_nothing_and_the_retry_succeeds(self):
        request_id = str(uuid4())
        script = f'''
from unittest.mock import patch
from project import create_app
from project.database import db
from project.models import User
from project.services.practice_service import save_artifacts
with create_app({self.config!r}).app_context():
    def stop_before_commit():
        db.session.flush()
        print("READY", flush=True)
        input()
    with patch.object(db.session, "commit", stop_before_commit):
        save_artifacts(db.session.get(User, 1), {self.session_id!r}, request_id={request_id!r},
            edits=[dict(artifact_id="api", base_revision=0, language="text", body="crash attempt")])
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(io_select.select([child.stdout], [], [], 15)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
            self.assertEqual(self.count("artifact_revision"), 0)
            self.assertEqual(self.count("practice_receipt", "operation = 'save'"), 0)
        finally:
            child.terminate()
            child.communicate(timeout=10)
        self.assertEqual(self.save("crash attempt", request_id=request_id)["artifacts"]["api"]["revision"], 1)
        self.assertEqual(self.count("artifact_revision"), 1)

    def test_a_fresh_process_resumes_the_saved_session(self):
        self.save("durable work")
        script = f'''
import json
from project import create_app
from project.services.practice_service import session_detail
with create_app({self.config!r}).app_context():
    detail = session_detail(1, {self.session_id!r})
    print(json.dumps([[a["artifact_id"], a["revision"], a["body"]] for a in detail["artifacts"]]))
'''
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1]),
                         [["api", 1, "durable work"], ["schema", 0, ""], ["algorithm", 0, ""]])

    def test_the_database_rejects_citations_across_sessions(self):
        other = self.start()
        self.save("other session", session_id=other)
        message = SessionMessage.query.filter_by(practice_session_id=self.session_id).one()
        revision = ArtifactRevision.query.filter_by(practice_session_id=other).one()
        for session_id in (self.session_id, other):
            with self.subTest(session_id=session_id):
                db.session.add(SessionMessageArtifact(practice_session_id=session_id, message_id=message.id,
                                                      artifact_revision_id=revision.id))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_failure_summaries_omit_text_that_postgresql_echoes(self):
        db.session.add(ArtifactRevision(practice_session_id=self.session_id, artifact_id="api", revision=1,
            title="API", format="api-definition", language="not-a-language", body="PARAMETER_SENTINEL",
            body_sha256="0" * 64, created_at=SessionMessage.query.first().created_at))
        with self.assertRaises(IntegrityError) as raised:
            db.session.commit()
        db.session.rollback()
        # Parameters are hidden, but PostgreSQL's DETAIL still quotes the failing row.
        self.assertIn("SQL parameters hidden", str(raised.exception))
        self.assertIn("PARAMETER_SENTINEL", str(raised.exception))
        summary = service.describe_failure(raised.exception)
        self.assertEqual(summary, "IntegrityError sqlstate=23514 constraint=ck_artifact_revision_language")

    def test_nul_characters_are_rejected_before_the_database(self):
        with self.assertRaises(service.PracticeValidationError):
            self.save("before\x00after")
        self.assertEqual(self.count("artifact_revision"), 0)


if __name__ == "__main__":
    unittest.main()
