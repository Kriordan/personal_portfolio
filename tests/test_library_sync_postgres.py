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
from project.models import LibraryMove, LibraryPin, LibraryWorkflow, User, Video, YouTubeConnection
from project.library.credentials import MOVE_SCOPES
from project.library.moves import move_status, move_video
from project.library.workflow import WorkflowError
from scripts.library_fixture_provider import LibraryFixtureProvider, Request, item

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

    def seed_move(self):
        now = datetime.now(timezone.utc)
        owner = User(id=1, username="fixture", email="fixture@example.test", is_admin=True)
        db.session.add(owner)
        db.session.flush()
        db.session.add_all([Playlist(id=key, title=key, published_at=now, updated_at=now) for key in ("PLadded", "PLwatched")])
        db.session.flush()
        db.session.add(Video(id="source-entry", playlist_id="PLadded", video_url_id="fixture-video", title="Fixture video", published_at=now, embed_url="https://www.youtube.com/embed/fixture-video"))
        db.session.add(YouTubeConnection(id=1, encrypted_refresh_token="fixture", oauth_client_id="fixture", connected_by_id=1,
            connected_at=now, channel_id="fixture-channel", granted_scopes=MOVE_SCOPES))
        self.version = str(uuid4())
        db.session.add(LibraryWorkflow(id=1, version=self.version, owner_id=1, channel_id="fixture-channel", source_playlist_id="PLadded", destination_playlist_id="PLwatched"))
        db.session.commit()
        return owner

    def test_move_process_death_reconciles_checkpoint_without_repeating_writes(self):
        owner = self.seed_move()
        request_id = str(uuid4())
        script = f'''
from unittest.mock import patch
from project import create_app
from project.database import db
from project.models import User
from project.library.moves import move_video
from scripts.library_fixture_provider import LibraryFixtureProvider, Request
provider = LibraryFixtureProvider()
original = provider.playlistItems
def resource():
    result = original()
    def insert(**kwargs):
        def wait():
            print("READY", flush=True)
            input()
        return Request(wait)
    result.insert = insert
    return result
provider.playlistItems = resource
with create_app({self.config!r}).app_context(), patch("project.library.moves.get_youtube_service", return_value=provider):
    move_video(db.session.get(User, 1), {request_id!r}, "source-entry", {self.version!r})
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 15)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
            self.assertEqual(move_status(owner)["moves"][0]["stage"], "inserting")
            self.assertTrue(move_status(owner)["busy"])
            with self.assertRaises(WorkflowError):
                move_video(owner, str(uuid4()), "source-entry", self.version)
            with self.assertRaises(SyncError):
                sync_library()
        finally:
            child.terminate()
            child.communicate(timeout=10)
        provider = LibraryFixtureProvider()
        # Model the provider accepting the insert before the process died.
        provider.items["confirmed-watched"] = item("confirmed-watched", "PLwatched")
        with patch("project.library.moves.get_youtube_service", return_value=provider):
            result = move_status(owner, request_id)
        self.assertEqual(result["moves"][0]["status"], "partial")
        self.assertFalse(result["busy"])
        self.assertTrue(all(name == "read" for name, args in provider.events))
        self.assertIsNotNone(db.session.get(Video, "source-entry"))

    def test_lost_move_lock_stops_before_delete_and_cannot_overwrite_recovery(self):
        owner = self.seed_move()
        provider = LibraryFixtureProvider()
        original = provider.playlistItems
        def resource():
            result = original()
            original_insert = result.insert
            def insert(**kwargs):
                request = original_insert(**kwargs)
                def lose_lock():
                    value = request.execute()
                    with db.engine.begin() as connection:
                        connection.execute(text("SELECT pg_terminate_backend(pid) FROM pg_locks WHERE locktype='advisory' AND classid=0 AND objid=741938204 AND granted"))
                    return value
                return Request(lose_lock)
            result.insert = insert
            return result
        provider.playlistItems = resource
        request_id = str(uuid4())
        with patch("project.library.moves.get_youtube_service", return_value=provider):
            with self.assertRaises(Exception):
                move_video(owner, request_id, "source-entry", self.version)
            db.session.rollback()
            self.assertEqual(db.session.get(LibraryMove, request_id).stage, "inserting")
            self.assertEqual(move_status(owner, request_id)["moves"][0]["status"], "partial")
        self.assertEqual([name for name, _ in provider.events].count("insert"), 1)
        self.assertNotIn("delete", [name for name, _ in provider.events])

    def test_pin_and_workflow_migrations_roundtrip_without_catalog_or_credential_loss(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        self.seed_move()
        migrations = []
        for name in ("b8c9d0e1f2a3_library_pins", "c9d0e1f2a3b4_library_watched_workflow"):
            spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / f"migrations/versions/{name}.py")
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            migrations.append(migration)
        db.session.remove()
        with db.engine.begin() as connection:
            for migration in reversed(migrations):
                with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                    migration.downgrade()
            for migration in migrations:
                with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                    migration.upgrade()
            self.assertEqual(connection.execute(text("SELECT count(*) FROM playlist")).scalar(), 2)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM video")).scalar(), 1)
            self.assertEqual(connection.execute(text("SELECT encrypted_refresh_token FROM youtube_connection")).scalar(), "fixture")
