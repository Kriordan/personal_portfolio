"""Rating serialization and atomicity on an explicitly disposable PostgreSQL DB."""
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.models import ReviewLog, ReviewProgress, ReviewReceipt, User
from project.services import learning_service as service

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class LearningPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing destructive fixtures outside the isolated local test database")
        self.config = dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL)
        self.app = create_app(self.config)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(User(id=1, username="learning", email="learning@example.test"))
        db.session.commit()
        self.directory = tempfile.TemporaryDirectory()
        self.notes = Path(self.directory.name)
        (self.notes / "fixture.json").write_text(json.dumps(dict(id="fixture", title="Fixture",
            flashcards=[dict(id="q", question="Question", answer="Answer")])))

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()
        self.directory.cleanup()

    def rate(self, request_id, barrier=None):
        with self.app.app_context():
            user = db.session.get(User, 1)
            if barrier:
                barrier.wait(timeout=10)
            try:
                return service.rate_card_for_user(user=user, notes_dir=self.notes, card_id="fixture:q",
                    rating=4, expected_revision=0, request_id=request_id)
            except service.StaleReviewError:
                return "stale"

    def test_concurrent_replays_commit_one_first_review(self):
        barrier = Barrier(2)
        request_id = str(uuid4())
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.rate, request_id, barrier) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(ReviewProgress.query.count(), 1)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewReceipt.query.count(), 1)
        script = f'''
from project import create_app
from project.database import db
from project.models import User
from project.services.learning_service import rating_receipt
with create_app({self.config!r}).app_context():
    result = rating_receipt(db.session.get(User, 1), {request_id!r})
    print(result["request_id"], result["progress_revision"])
'''
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(result.stdout.strip(), f"{request_id} 1")

    def test_two_devices_cannot_both_rate_a_stale_snapshot(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.rate, str(uuid4()), barrier) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results.count("stale"), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_process_death_rolls_back_progress_log_and_receipt(self):
        request_id = str(uuid4())
        script = f'''
from pathlib import Path
from unittest.mock import patch
from project import create_app
from project.database import db
from project.models import User
from project.services.learning_service import rate_card_for_user
with create_app({self.config!r}).app_context():
    def stop_before_commit():
        db.session.flush()
        print("READY", flush=True)
        input()
    with patch.object(db.session, "commit", stop_before_commit):
        rate_card_for_user(user=db.session.get(User, 1), notes_dir=Path({str(self.notes)!r}),
            card_id="fixture:q", rating=4, request_id={request_id!r}, expected_revision=0)
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 15)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
            with db.engine.connect() as connection:
                for table in ("review_progress", "review_log", "review_receipt"):
                    self.assertEqual(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar(), 0)
        finally:
            child.terminate()
            child.communicate(timeout=10)
        self.assertEqual(self.rate(request_id)["progress_revision"], 1)
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_migration_preserves_history_and_rejects_duplicate_progress(self):
        self.rate(str(uuid4()))
        before = ReviewProgress.query.one().next_review
        source = Path(__file__).resolve().parents[1] / "migrations/versions/d0e1f2a3b4c5_learning_review_receipts.py"
        spec = importlib.util.spec_from_file_location("learning_migration", source)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        db.session.remove()
        with db.engine.begin() as connection, patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            migration.downgrade()
            migration.upgrade()
            self.assertEqual(connection.execute(text("SELECT next_review FROM review_progress")).scalar(), before)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM review_log")).scalar(), 1)
            migration.downgrade()
            connection.execute(text("INSERT INTO review_progress (user_id, card_id, scheduler_version, learning_state, lapses, target_recall, is_suspended, easiness, interval, repetitions, next_review) SELECT user_id, card_id, scheduler_version, learning_state, lapses, target_recall, is_suspended, easiness, interval, repetitions, next_review FROM review_progress"))
            with self.assertRaisesRegex(RuntimeError, "Duplicate learning progress"):
                migration.upgrade()
            self.assertEqual(connection.execute(text("SELECT count(*) FROM review_progress")).scalar(), 2)
            connection.execute(text("DELETE FROM review_progress WHERE id=(SELECT max(id) FROM review_progress)"))
            migration.upgrade()
