"""Real session-lock/transaction checks, on an explicitly isolated test database."""
import os
import select
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.library.sync_tracking import sync_status
from project.models import LibrarySyncRun, Playlist
from project.services.library_service import SyncError, sync_library

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to an isolated local library_sync_test database")
class LibrarySyncPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing to run destructive fixtures outside the isolated local test database")
        self.config = {"TESTING": True, "SECRET_KEY": "fixture", "SQLALCHEMY_DATABASE_URI": URL}
        self.app = create_app(self.config)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def test_other_process_lock_survives_commit_and_dies_with_process(self):
        request_id = str(uuid4())
        script = f'''
from project import create_app
from project.database import db
from project.models import LibrarySyncRun, Playlist
from project.library.sync_tracking import import_lock
from datetime import datetime, timezone
with create_app({self.config!r}).app_context(), import_lock() as acquired:
    assert acquired
    db.session.add(LibrarySyncRun(id={request_id!r}, status="running", started_at=datetime.now(timezone.utc)))
    db.session.commit()
    db.session.add(Playlist(id="uncommitted", title="Temporary", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
    db.session.flush()
    print("READY", flush=True)
    input()
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 15)[0], "Child importer did not become ready")
            self.assertEqual(child.stdout.readline().strip(), "READY")
            report = sync_status(request_id)
            self.assertTrue(report["busy"])
            self.assertEqual(report["requested"]["status"], "running")
            with patch("project.services.library_service.sync_playlists_and_videos") as importer:
                with self.assertRaises(SyncError) as error:
                    sync_library()
                self.assertEqual(error.exception.status, 409)
                importer.assert_not_called()
            self.assertIsNone(db.session.get(Playlist, "uncommitted"))
        finally:
            child.terminate()
            child.communicate(timeout=10)
        report = sync_status(request_id)
        self.assertFalse(report["busy"])
        self.assertEqual(report["requested"]["status"], "interrupted")
        self.assertIsNone(db.session.get(Playlist, "uncommitted"))

    def test_catalog_and_completion_are_visible_together_and_fenced(self):
        request_id = str(uuid4())
        def import_after_lost_lock(**kwargs):
            db.session.add(Playlist(id="fenced", title="Do not commit", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            db.session.flush()
            # Another connection can mark the receipt after a lost lock. It must
            # prevent this old importer from later committing catalog changes.
            with db.engine.begin() as connection:
                connection.execute(text("UPDATE library_sync_run SET status='interrupted' WHERE id=:id"), {"id": request_id})
            return {"playlists": {"added": 1}}
        with patch("project.services.library_service.sync_playlists_and_videos", side_effect=import_after_lost_lock):
            with self.assertRaises(SyncError):
                sync_library(request_id)
        self.assertIsNone(db.session.get(Playlist, "fenced"))
        self.assertEqual(db.session.get(LibrarySyncRun, request_id).status, "interrupted")

        def valid_import(**kwargs):
            db.session.add(Playlist(id="committed", title="Saved", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            with db.engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT count(*) FROM playlist")).scalar(), 0)
                self.assertEqual(connection.execute(text("SELECT count(*) FROM library_sync_run WHERE status='succeeded'")).scalar(), 0)
            return {"playlists": {"added": 1}}
        with patch("project.services.library_service.sync_playlists_and_videos", side_effect=valid_import):
            completed = sync_library()
        with db.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT count(*) FROM playlist")).scalar(), 1)
            self.assertEqual(connection.execute(text("SELECT status FROM library_sync_run WHERE id=:id"), {"id": completed["id"]}).scalar(), "succeeded")

    def test_migration_roundtrip_preserves_catalog(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        source = Path(__file__).resolve().parents[1] / "migrations/versions/a7b8c9d0e1f2_track_library_sync.py"
        spec = importlib.util.spec_from_file_location("library_sync_migration", source)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        db.session.add(Playlist(id="saved", title="Saved", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
        db.session.commit()
        with db.engine.begin() as connection, patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            migration.downgrade()
            migration.upgrade()
            self.assertEqual(connection.execute(text("SELECT count(*) FROM playlist")).scalar(), 1)
