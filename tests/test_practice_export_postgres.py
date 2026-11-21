"""Snapshot consistency without blocking writers, verified on real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import User
from project.services import feedback_service, feedback_review_service as review, practice_export_service as exports, practice_service as practice, practice_worker
from project.services.curriculum_service import import_catalog
from project.services.learning_errors import NotFoundError
from tests.curriculum_v2_fixtures import publish_feedback_catalog
from tests.feedback_fixtures import scripted_feedback
from tests.test_feedback_review import completed_feedback
from tests.test_practice_export import add_history
from tests.test_practice_service import NOW
from tests.test_practice_submissions import submission_input

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class PracticeExportPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing destructive fixtures outside the isolated local test database")
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL,
            LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="fixture1@example.test"))
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(id=1, username="Export fixture", email="fixture1@example.test", email_verified=True)
        db.session.add(user)
        db.session.commit()
        import_catalog(load_catalog(ROOT / "curriculum/idempotency/catalog.json"), dry_run=False, publish=True,
            reviewed_by="Disposable fixture", reviewed_on=date(2026, 11, 3))
        publish_feedback_catalog()
        self.sid, self.seq, _ = completed_feedback(user)
        db.session.remove()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def export(self):
        with self.app.app_context():
            return exports.session_export(1, self.sid, now=NOW)

    def during_export(self, change):
        captured, release = Event(), Event()
        collect = exports._contents

        def paused(reader, session, now):
            # The ownership SELECT already established this snapshot. The
            # competing writer must finish while this reader is still open.
            self.assertEqual(reader.scalar(text("SHOW transaction_isolation")), "repeatable read")
            self.assertEqual(reader.scalar(text("SHOW transaction_read_only")), "on")
            captured.set()
            self.assertTrue(release.wait(timeout=15))
            return collect(reader, session, now)

        def write():
            with self.app.app_context():
                change(db.session.get(User, 1))

        with patch.object(exports, "_contents", side_effect=paused), ThreadPoolExecutor(2) as pool:
            reading = pool.submit(self.export)
            try:
                self.assertTrue(captured.wait(timeout=10))
                pool.submit(write).result(timeout=10)
            finally:
                release.set()
            return reading.result(timeout=10)

    def test_concurrent_saves_commit_while_export_keeps_the_original_complete_state(self):
        before = self.export()
        result = self.during_export(lambda user: add_history(user, self.sid))
        self.assertEqual(result, before)
        after = self.export()
        self.assertEqual(after["artifacts"][0]["current_revision"], 2)
        self.assertEqual(after["brief_revisions"][-1]["revision"], 2)
        self.assertEqual(after["transcript"][-1]["body"], "Trace my revised contract.")
        self.assertEqual(after["submissions"][0]["checks"][0]["revision"], 1)

    def test_concurrent_annotation_and_rating_are_both_absent_until_the_next_export(self):
        before = self.export()

        def change(user):
            review.annotate(user, self.sid, self.seq, "f2", decision="agree", note="Saved while exporting.",
                expected_revision=0, request_id=str(uuid4()))
            review.rate_review(user, self.sid, self.seq, "f2", card_id="idempotency:race", content_version=2,
                expected_revision=0, request_id=str(uuid4()), rating=4)

        self.assertEqual(self.during_export(change), before)
        after = self.export()
        self.assertEqual(after["submissions"][0]["feedback"]["findings"][1]["annotation"]["decision"], "agree")
        self.assertEqual(len(after["followup_ratings"]), 1)

    def test_deletion_during_export_does_not_produce_a_partial_file_or_block_deletion(self):
        before = self.export()
        self.assertEqual(self.during_export(lambda user: practice.delete_session(user, self.sid)), before)
        with self.assertRaises(NotFoundError):
            self.export()

    def test_feedback_finishing_during_export_is_included_only_in_the_next_download(self):
        user = db.session.get(User, 1)
        seq = practice.save_and_submit(user, self.sid, **submission_input(
            practice.session_detail(1, self.sid)))["submission"]["sequence"]
        feedback_service.request_feedback(user, self.sid, seq, request_id=str(uuid4()))
        db.session.remove()
        before = self.export()
        self.assertIsNone(before["submissions"][-1]["feedback"])
        self.assertEqual(self.during_export(lambda _user: practice_worker.run_once(
            practice_worker.FakeProvider(feedbacks=[scripted_feedback]))), before)
        self.assertIsNotNone(self.export()["submissions"][-1]["feedback"])

    def test_request_transaction_is_not_committed_rolled_back_or_reconfigured_by_export(self):
        # A connection with an uncommitted change is deliberately held open by
        # the caller. Export sees the durable state on its separate connection.
        user = db.session.get(User, 1)
        user.username = "Not committed"
        db.session.flush()
        self.assertEqual(db.session.scalar(text("SHOW transaction_isolation")), "read committed")
        self.export()
        self.assertEqual(db.session.scalar(text("SELECT username FROM \"user\" WHERE id = 1")), "Not committed")
        self.assertEqual(db.session.scalar(text("SHOW transaction_read_only")), "off")
        db.session.rollback()
        self.assertEqual(db.session.get(User, 1).username, "Export fixture")
        with db.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SHOW transaction_isolation")), "read committed")
            self.assertEqual(connection.scalar(text("SHOW transaction_read_only")), "off")
