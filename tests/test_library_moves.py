"""Exercise non-atomic provider writes, owner isolation and read-only recovery."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from flask_jwt_extended import create_access_token
from googleapiclient.errors import HttpError
from httplib2 import Response

from project import create_app
from project.database import db
from project.library.credentials import MOVE_SCOPES, SCOPES
from project.library.moves import move_status, move_video, retry_removal
from project.library.sync_tracking import import_lock
from project.library.workflow import WorkflowError, configure_workflow, workflow_status
from project.models import LibraryMove, LibraryWatchedMembership, LibraryWorkflow, Playlist, User, Video, YouTubeConnection
from scripts.library_fixture_provider import LibraryFixtureProvider, item


class LibraryMoveTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test", "JWT_SECRET_KEY": "test-key-with-at-least-32-characters"})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        self.provider = LibraryFixtureProvider()
        for path in ("project.library.moves.get_youtube_service", "project.library.workflow.get_youtube_service", "project.library.jobs.get_youtube_service"):
            patcher = patch(path, return_value=self.provider)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.owner = User(id=1, username="owner", email="owner@example.test", is_admin=True)
        self.other = User(id=2, username="other", email="other@example.test", is_admin=True)
        db.session.add_all([self.owner, self.other])
        db.session.flush()
        now = datetime.now(timezone.utc)
        db.session.add(YouTubeConnection(id=1, encrypted_refresh_token="fixture", oauth_client_id="fixture", connected_by_id=1,
            connected_at=now, channel_id=self.provider.channel, granted_scopes=MOVE_SCOPES))
        for key, value in self.provider.playlist_data.items():
            db.session.add(Playlist(id=key, title=value["snippet"]["title"], published_at=now, updated_at=now))
        db.session.flush()
        for entry, playlist in [("source-entry", "PLadded"), ("other-entry", "PLother"), ("duplicate-source", "PLadded")]:
            db.session.add(Video(id=entry, playlist_id=playlist, video_url_id="fixture-video", title="Fixture video", published_at=now, embed_url="https://www.youtube.com/embed/fixture-video"))
            self.provider.items[entry] = item(entry, playlist)
        db.session.commit()
        configure_workflow(self.owner, "PLadded", "PLwatched")
        self.version = db.session.get(LibraryWorkflow, 1).version

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def move(self, request_id=None, entry="source-entry"):
        return move_video(self.owner, request_id or str(uuid4()), entry, self.version)

    def calls(self, method):
        return [args for name, args in self.provider.events if name == method]

    def status(self, move_id):
        record = db.session.get(LibraryMove, move_id)
        record.last_checked_at = None
        db.session.commit()
        return move_status(self.owner, move_id)["moves"][0]

    def test_success_confirms_destination_then_removes_exact_source_only(self):
        result = self.move()
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.calls("delete"), [{"id": "source-entry"}])
        self.assertEqual(len(self.calls("insert")), 1)
        self.assertIsNone(db.session.get(Video, "source-entry"))
        self.assertIsNotNone(db.session.get(Video, "duplicate-source"))
        self.assertIsNotNone(db.session.get(Video, "other-entry"))
        self.assertEqual(Video.query.filter_by(playlist_id="PLwatched").count(), 1)
        self.assertIsNotNone(db.session.get(LibraryWatchedMembership, "fixture-video"))
        delete_index = next(i for i, (name, _) in enumerate(self.provider.events) if name == "delete")
        self.assertEqual(self.provider.events[delete_index - 1][0], "read")

    def test_repeated_and_different_request_ids_do_not_repeat_the_same_move(self):
        result = self.move()
        self.assertEqual(self.move(result["id"]), result)
        self.assertEqual(self.move()["id"], result["id"])
        self.assertEqual(len(self.calls("insert")), 1)
        self.assertEqual(len(self.calls("delete")), 1)

    def test_already_in_destination_does_not_duplicate_it(self):
        self.provider.items["existing-watched"] = item("existing-watched", "PLwatched")
        self.assertEqual(self.move()["status"], "succeeded")
        self.assertEqual(self.calls("insert"), [])

    def test_ambiguous_insert_reconciles_without_reinsert_or_auto_delete(self):
        self.provider.insert_failure = OSError("private-provider-message")
        self.provider.fail_after_insert = True
        result = self.move()
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("private-provider-message", str(result))
        self.assertEqual(self.calls("delete"), [])
        result = self.status(result["id"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(self.move()["id"], result["id"])
        self.assertEqual(len(self.calls("insert")), 1)
        self.assertEqual(self.calls("delete"), [])
        removal_id = str(uuid4())
        self.assertEqual(retry_removal(self.owner, result["id"], removal_id)["status"], "succeeded")
        retry_removal(self.owner, result["id"], removal_id)
        self.assertEqual(len(self.calls("delete")), 1)

    def test_unconfirmed_insert_never_retries_even_with_new_request_id(self):
        self.provider.insert_failure = OSError("timeout")
        result = self.move()
        self.assertEqual(self.status(result["id"])["status"], "unknown")
        self.assertEqual(self.move()["id"], result["id"])
        self.assertEqual(len(self.calls("insert")), 1)
        self.assertEqual(self.calls("delete"), [])
        with self.assertRaises(WorkflowError):
            retry_removal(self.owner, result["id"], str(uuid4()))

    def test_later_quota_or_auth_read_error_never_makes_ambiguous_insert_retryable(self):
        self.provider.insert_failure = OSError("ambiguous insert")
        result = self.move()
        for code in (401, 403, 404):
            self.provider.read_failure = HttpError(Response({"status": str(code)}), b"read failure")
            self.assertEqual(self.status(result["id"])["status"], "unknown")
            self.assertEqual(self.move()["id"], result["id"])
        self.assertEqual(len(self.calls("insert")), 1)
        self.assertEqual(self.calls("delete"), [])

    def test_slow_polling_reconciles_all_outstanding_moves(self):
        self.provider.insert_failure = OSError("ambiguous insert")
        first = self.move()
        second = self.move(entry="duplicate-source")
        move_status(self.owner)
        checked = LibraryMove.query.filter(LibraryMove.last_checked_at.isnot(None)).one()
        checked.last_checked_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        db.session.commit()
        move_status(self.owner)
        for request_id in (first["id"], second["id"]):
            self.assertIsNotNone(db.session.get(LibraryMove, request_id).last_checked_at)
        self.assertEqual(len(self.calls("insert")), 2)
        self.assertEqual(self.calls("delete"), [])

    def test_definitive_insert_rejection_keeps_source_and_allows_deliberate_new_attempt(self):
        self.provider.insert_failure = HttpError(Response({"status": "403"}), b"quota")
        result = self.move()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.calls("delete"), [])
        self.assertIsNotNone(db.session.get(Video, "source-entry"))
        self.provider.insert_failure = None
        self.assertEqual(self.move()["status"], "succeeded")

    def test_delete_failure_is_partial_and_retry_checks_destination_again(self):
        self.provider.delete_failure = HttpError(Response({"status": "403"}), b"quota-secret")
        result = self.move()
        result = self.status(result["id"])
        self.assertEqual(result["status"], "partial")
        self.assertIsNotNone(db.session.get(Video, "source-entry"))
        self.provider.items = {key: value for key, value in self.provider.items.items() if value["snippet"]["playlistId"] != "PLwatched"}
        self.assertEqual(retry_removal(self.owner, result["id"], str(uuid4()))["status"], "unknown")
        self.assertEqual(len(self.calls("delete")), 1)
        self.assertEqual(len(self.calls("insert")), 1)

    def test_lost_delete_response_is_completed_by_reads(self):
        self.provider.delete_failure = OSError("lost reply")
        self.provider.fail_after_delete = True
        result = self.move()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(self.status(result["id"])["status"], "succeeded")
        self.assertEqual(len(self.calls("delete")), 1)

    def test_process_death_after_insert_keeps_intent_and_never_repeats_addition(self):
        self.provider.insert_failure = SystemExit("simulate process death")
        self.provider.fail_after_insert = True
        request_id = str(uuid4())
        with self.assertRaises(SystemExit):
            self.move(request_id)
        db.session.remove()
        self.owner = db.session.get(User, 1)
        self.assertEqual(db.session.get(LibraryMove, request_id).stage, "inserting")
        self.assertEqual(self.status(request_id)["status"], "partial")
        self.assertEqual(self.calls("delete"), [])
        self.assertEqual(len(self.calls("insert")), 1)

    def test_readonly_nonowner_or_stale_configuration_cannot_move(self):
        with self.assertRaises(WorkflowError):
            move_video(self.other, str(uuid4()), "source-entry", self.version)
        with self.assertRaises(WorkflowError):
            move_status(self.other)
        with self.assertRaises(WorkflowError):
            configure_workflow(self.other, "PLadded", "PLwatched")
        with self.assertRaises(WorkflowError):
            move_video(self.owner, str(uuid4()), "source-entry", str(uuid4()))
        db.session.get(YouTubeConnection, 1).granted_scopes = SCOPES
        db.session.commit()
        self.assertFalse(workflow_status(self.owner)["can_move"])
        with self.assertRaises(WorkflowError):
            self.move()
        self.assertEqual(self.calls("insert"), [])

    def test_channel_change_and_invalid_playlists_are_rejected(self):
        for source, destination in [("PLadded", "PLadded"), ("WL", "PLwatched"), ("PLmissing", "PLwatched")]:
            with self.assertRaises(WorkflowError):
                configure_workflow(self.owner, source, destination)
            db.session.rollback()
        self.provider.playlist_data["PLwatched"]["snippet"]["channelId"] = "another-channel"
        self.assertEqual(self.move()["status"], "failed")
        db.session.get(YouTubeConnection, 1).channel_id = "different"
        db.session.commit()
        self.assertIsNone(workflow_status(self.owner)["source"])
        self.assertEqual(self.calls("insert"), [])

    def test_rename_does_not_change_saved_ids_and_source_is_verified(self):
        self.provider.playlist_data["PLadded"]["snippet"]["title"] = "Renamed added"
        self.provider.items["source-entry"]["snippet"]["playlistId"] = "PLother"
        self.assertEqual(self.move()["status"], "failed")
        self.assertEqual(self.calls("insert"), [])

    def test_shared_lock_excludes_sync_and_move(self):
        from project.services.library_service import SyncError, sync_library
        with import_lock() as acquired:
            self.assertTrue(acquired)
            with self.assertRaises(WorkflowError):
                self.move()
            with self.assertRaises(SyncError):
                sync_library()
            self.assertTrue(move_status(self.owner)["busy"])
        self.assertEqual(self.calls("insert"), [])

    def test_badges_are_from_membership_not_retained_rows_or_legacy_flags(self):
        from project.services.library_service import serialize_video
        video = db.session.get(Video, "other-entry")
        video.watched = True
        self.assertFalse(serialize_video(video)["in_watched_playlist"])
        self.move()
        self.assertTrue(serialize_video(video)["in_watched_playlist"])
        self.assertTrue(serialize_video(video)["watched"])

    def test_sync_replaces_membership_only_after_complete_fetch(self):
        from project.services.library_service import sync_library, SyncError
        self.move()
        self.provider.read_failure = OSError("page failed")
        with self.assertRaises(SyncError):
            sync_library()
        self.assertIsNotNone(db.session.get(LibraryWatchedMembership, "fixture-video"))
        self.provider.read_failure = None
        self.provider.items = {key: value for key, value in self.provider.items.items() if value["snippet"]["playlistId"] != "PLwatched"}
        with patch("project.library.jobs.fetch_playlists", return_value=list(self.provider.playlist_data.values())):
            sync_library()
        self.assertIsNone(db.session.get(LibraryWatchedMembership, "fixture-video"))
        self.assertEqual(Video.query.filter_by(playlist_id="PLwatched").count(), 1)

    def test_auth_api_validation_receipts_and_no_store(self):
        headers = {"Authorization": f"Bearer {create_access_token(identity='1')}"}
        self.assertEqual(self.client.get("/api/v1/library/workflow", base_url="https://localhost").status_code, 401)
        result = self.client.post("/api/v1/library/moves", base_url="https://localhost", headers=headers,
            json={"request_id": str(uuid4()), "source_entry_id": "source-entry", "workflow_version": self.version})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers["Cache-Control"], "private, no-store")
        self.assertEqual(result.get_json()["move"]["status"], "succeeded")
        self.assertEqual(self.client.post("/api/v1/library/moves", base_url="https://localhost", headers=headers, json={}).status_code, 400)
