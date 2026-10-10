import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import Playlist, User, Video


class ApiLibraryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "JWT_SECRET_KEY": "test-jwt-secret-should-be-at-least-32",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_user(self, *, email: str, username: str) -> int:
        with self.app.app_context():
            user = User(email=email, username=username, email_verified=True)
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            return user.id

    def _create_playlist(
        self,
        *,
        playlist_id: str,
        title: str,
        published_at: datetime,
    ) -> None:
        with self.app.app_context():
            playlist = Playlist(
                id=playlist_id,
                title=title,
                description=f"{title} description",
                published_at=published_at,
                updated_at=published_at,
                thumbnail_url=f"https://img.example.com/{playlist_id}.jpg",
            )
            db.session.add(playlist)
            db.session.commit()

    def _create_video(
        self,
        *,
        video_id: str,
        playlist_id: str,
        title: str,
        published_at: datetime,
    ) -> None:
        with self.app.app_context():
            video = Video(
                id=video_id,
                playlist_id=playlist_id,
                video_url_id=f"url-{video_id}",
                title=title,
                description=f"{title} description",
                published_at=published_at,
                thumbnail_url=f"https://img.example.com/{video_id}.jpg",
                embed_url=f"https://www.youtube.com/embed/{video_id}",
            )
            db.session.add(video)
            db.session.commit()

    def _auth_headers(self, user_id: int) -> dict:
        with self.app.app_context():
            token = create_access_token(identity=str(user_id))
        return {"Authorization": f"Bearer {token}"}

    def _get(self, path: str, **kwargs):
        return self.client.get(path, base_url="https://localhost", **kwargs)

    def _post(self, path: str, **kwargs):
        return self.client.post(path, base_url="https://localhost", **kwargs)

    def test_library_endpoints_require_jwt(self):
        unauthenticated_requests = [
            self._get("/api/v1/library/playlists"),
            self._get("/api/v1/library/playlists/pl-1"),
            self._get("/api/v1/library/videos/vid-1"),
            self._post("/api/v1/library/sync"),
        ]

        for response in unauthenticated_requests:
            self.assertEqual(response.status_code, 401)

    def test_get_playlists_returns_serialized_playlists_newest_first(self):
        user_id = self._create_user(email="viewer@example.com", username="viewer")
        self._create_playlist(
            playlist_id="pl-old",
            title="Older Playlist",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self._create_playlist(
            playlist_id="pl-new",
            title="Newer Playlist",
            published_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )

        response = self._get("/api/v1/library/playlists", headers=self._auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        playlists = response.get_json()["playlists"]
        self.assertEqual([playlist["id"] for playlist in playlists], ["pl-new", "pl-old"])
        for key in (
            "id",
            "title",
            "description",
            "published_at",
            "updated_at",
            "thumbnail_url",
        ):
            self.assertIn(key, playlists[0])

    def test_get_playlist_returns_playlist_with_its_videos(self):
        user_id = self._create_user(email="viewer@example.com", username="viewer")
        self._create_playlist(
            playlist_id="pl-1",
            title="Playlist One",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self._create_playlist(
            playlist_id="pl-2",
            title="Playlist Two",
            published_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        self._create_video(
            video_id="vid-1",
            playlist_id="pl-1",
            title="First Video",
            published_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        self._create_video(
            video_id="vid-2",
            playlist_id="pl-1",
            title="Second Video",
            published_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
        )
        self._create_video(
            video_id="vid-other",
            playlist_id="pl-2",
            title="Other Playlist Video",
            published_at=datetime(2024, 2, 2, tzinfo=timezone.utc),
        )

        response = self._get(
            "/api/v1/library/playlists/pl-1", headers=self._auth_headers(user_id)
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["playlist"]["id"], "pl-1")
        self.assertEqual(
            [video["id"] for video in payload["videos"]], ["vid-2", "vid-1"]
        )
        video = payload["videos"][0]
        for key in (
            "id",
            "playlist_id",
            "video_url_id",
            "title",
            "description",
            "published_at",
            "thumbnail_url",
            "embed_url",
            "watched",
            "created_at",
            "updated_at",
        ):
            self.assertIn(key, video)
        self.assertFalse(video["watched"])

    def test_get_playlist_returns_404_for_unknown_playlist(self):
        user_id = self._create_user(email="viewer@example.com", username="viewer")

        response = self._get(
            "/api/v1/library/playlists/missing", headers=self._auth_headers(user_id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Playlist not found.")

    def test_get_video_returns_serialized_video(self):
        user_id = self._create_user(email="viewer@example.com", username="viewer")
        self._create_playlist(
            playlist_id="pl-1",
            title="Playlist One",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self._create_video(
            video_id="vid-1",
            playlist_id="pl-1",
            title="First Video",
            published_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        response = self._get(
            "/api/v1/library/videos/vid-1", headers=self._auth_headers(user_id)
        )

        self.assertEqual(response.status_code, 200)
        video = response.get_json()["video"]
        self.assertEqual(video["id"], "vid-1")
        self.assertEqual(video["playlist_id"], "pl-1")
        self.assertEqual(video["embed_url"], "https://www.youtube.com/embed/vid-1")

    def test_get_video_returns_404_for_unknown_video(self):
        user_id = self._create_user(email="viewer@example.com", username="viewer")

        response = self._get(
            "/api/v1/library/videos/missing", headers=self._auth_headers(user_id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Video not found.")

    @patch("project.services.library_service.sync_playlists_and_videos")
    def test_sync_triggers_job_without_real_external_calls(self, mock_sync):
        user_id = self._create_user(email="viewer@example.com", username="viewer")

        response = self._post("/api/v1/library/sync", headers=self._auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"], "Library sync completed.")
        mock_sync.assert_called_once_with(commit=False)

    @patch("project.services.library_service.sync_playlists_and_videos")
    def test_sync_requires_jwt_and_does_not_run_job(self, mock_sync):
        response = self._post("/api/v1/library/sync")

        self.assertEqual(response.status_code, 401)
        mock_sync.assert_not_called()

    def test_two_users_and_website_read_the_same_catalog(self):
        first = self._create_user(email="one@example.com", username="one")
        second = self._create_user(email="two@example.com", username="two")
        self._create_playlist(playlist_id="shared", title="Shared catalog", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        first_data = self._get("/api/v1/library/playlists", headers=self._auth_headers(first)).get_json()
        second_data = self._get("/api/v1/library/playlists", headers=self._auth_headers(second)).get_json()
        self.assertEqual(first_data, second_data)
        with self.client.session_transaction(base_url="https://localhost") as session:
            session["_user_id"] = str(second)
            session["_fresh"] = True
        website = self._get("/lib/")
        self.assertEqual(website.status_code, 200)
        self.assertIn(b"Shared catalog", website.data)

    def test_sync_failures_are_sanitized_and_roll_back_partial_imports(self):
        from google.auth.exceptions import RefreshError, TransportError
        from googleapiclient.errors import HttpError
        from httplib2 import Response
        from project.library.jobs import YouTubeConfigurationError

        user_id = self._create_user(email="viewer@example.com", username="viewer")
        secret = "provider-secret-must-not-leak"
        failures = [
            (YouTubeConfigurationError(secret), 503),
            (RefreshError(secret), 503),
            (HttpError(Response({"status": "401"}), secret.encode()), 503),
            (HttpError(Response({"status": "403"}), secret.encode()), 502),
            (TransportError(secret), 502),
            (RuntimeError(secret), 500),
        ]
        for error, status in failures:
            with self.subTest(error=type(error).__name__, status=status):
                def fail_after_write(**kwargs):
                    db.session.add(Playlist(id="partial", title="Partial import", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
                    db.session.flush()
                    raise error
                with patch("project.services.library_service.sync_playlists_and_videos", side_effect=fail_after_write):
                    response = self._post("/api/v1/library/sync", headers=self._auth_headers(user_id))
                self.assertEqual(response.status_code, status)
                self.assertIsInstance(response.get_json()["error"], str)
                self.assertNotIn(secret, response.get_data(as_text=True))
                with self.app.app_context():
                    self.assertIsNone(db.session.get(Playlist, "partial"))

    def test_sync_import_upserts_preserves_watched_and_retains_unavailable_records(self):
        from project.library.jobs import sync_playlists_and_videos
        user_id = self._create_user(email="viewer@example.com", username="viewer")
        self._create_playlist(playlist_id="pl-1", title="Old title", published_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        self._create_video(video_id="kept", playlist_id="pl-1", title="Old video", published_at=datetime(2024, 1, 2, tzinfo=timezone.utc))
        self._create_video(video_id="removed-upstream", playlist_id="pl-1", title="Previously imported", published_at=datetime(2024, 1, 2, tzinfo=timezone.utc))
        with self.app.app_context():
            db.session.get(Video, "kept").watched = True
            db.session.get(Video, "removed-upstream").position = 0
            db.session.commit()
        playlist = {"id": "pl-1", "snippet": {"title": "Updated playlist", "publishedAt": "2024-01-01T00:00:00Z"}}
        def item(id, title):
            return {"id": id, "snippet": {"title": title, "description": "Description", "publishedAt": "2024-01-02T00:00:00Z"}, "contentDetails": {"videoId": "abc123"}, "status": {"privacyStatus": "public"}}
        videos = [item("kept", "Updated video"), item("added", "New video"), item("removed-upstream", "Deleted video")]
        with self.app.app_context(), patch("project.library.jobs.get_youtube_service"), patch("project.library.jobs.fetch_playlists", return_value=[playlist]), patch("project.library.jobs.fetch_videos", return_value=videos):
            sync_playlists_and_videos()
            sync_playlists_and_videos()
            self.assertEqual(Video.query.count(), 3)
            self.assertTrue(db.session.get(Video, "kept").watched)
            self.assertEqual(db.session.get(Video, "kept").title, "Updated video")
            self.assertEqual(db.session.get(Video, "removed-upstream").title, "Previously imported")
            self.assertIsNone(db.session.get(Video, "removed-upstream").position)
        response = self._get("/api/v1/library/playlists/pl-1", headers=self._auth_headers(user_id))
        self.assertEqual(response.get_json()["playlist"]["title"], "Updated playlist")

    def test_website_sync_failure_uses_safe_flash(self):
        user_id = self._create_user(email="viewer@example.com", username="viewer")
        with self.client.session_transaction(base_url="https://localhost") as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        with patch("project.services.library_service.sync_playlists_and_videos", side_effect=RuntimeError("private provider error")):
            response = self._post("/lib/sync_playlists")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction(base_url="https://localhost") as session:
            self.assertEqual(session["_flashes"], [("error", "Library sync failed. Try again later.")])

    def test_sync_receipt_is_shared_and_same_request_never_reimports(self):
        from uuid import uuid4
        first = self._create_user(email="first@example.test", username="first")
        second = self._create_user(email="second@example.test", username="second")
        request_id = str(uuid4())
        summary = {kind: {"checked": 1, "added": 0, "updated": 0, "unchanged": 1, "skipped": 0} for kind in ("playlists", "videos")}
        with patch("project.services.library_service.sync_playlists_and_videos", return_value=summary) as importer:
            first_response = self._post("/api/v1/library/sync", headers=self._auth_headers(first), json={"request_id": request_id})
            replay = self._post("/api/v1/library/sync", headers=self._auth_headers(second), json={"request_id": request_id})
        self.assertEqual(importer.call_count, 1)
        self.assertEqual(first_response.get_json(), replay.get_json())
        response = self._get(f"/api/v1/library/sync-status?request_id={request_id}", headers=self._auth_headers(second))
        report = response.get_json()
        self.assertEqual(report["requested"]["status"], "succeeded")
        self.assertEqual(report["requested"]["summary"], summary)
        self.assertEqual(report["last_success"], report["requested"])
        self.assertIsNotNone(report["last_success"]["finished_at"])
        self.assertFalse(report["busy"])
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertEqual(self._get("/api/v1/library/sync-status").status_code, 401)
        self.assertEqual(self._post("/api/v1/library/sync", headers=self._auth_headers(first), json={"request_id": "invalid"}).status_code, 400)

    def test_active_import_is_not_interrupted_or_duplicated_by_status_checks(self):
        from uuid import uuid4
        from project.library.sync_tracking import import_lock
        from project.models import LibrarySyncRun
        user = self._create_user(email="active@example.test", username="active")
        headers = self._auth_headers(user)
        request_id = str(uuid4())
        with self.app.app_context(), import_lock() as acquired:
            self.assertTrue(acquired)
            db.session.add(LibrarySyncRun(id=request_id, status="running", started_at=datetime.now(timezone.utc)))
            db.session.commit()
            with patch("project.services.library_service.sync_playlists_and_videos") as importer:
                rejected = self._post("/api/v1/library/sync", headers=headers)
                report = self._get("/api/v1/library/sync-status", headers=headers).get_json()
            self.assertEqual(rejected.status_code, 409)
            importer.assert_not_called()
            self.assertTrue(report["busy"])
            self.assertEqual(report["latest"]["status"], "running")
        recovered = self._get("/api/v1/library/sync-status", headers=headers).get_json()
        self.assertEqual(recovered["latest"]["status"], "interrupted")
        self.assertIsNone(recovered["last_success"])

    def test_failed_import_has_a_receipt_but_cannot_replace_last_success(self):
        from uuid import uuid4
        from project.models import LibrarySyncRun
        user = self._create_user(email="failure@example.test", username="failure")
        headers = self._auth_headers(user)
        with patch("project.services.library_service.sync_playlists_and_videos", return_value={}):
            successful = self._post("/api/v1/library/sync", headers=headers, json={"request_id": str(uuid4())}).get_json()["run"]
        def invalid_write(**kwargs):
            db.session.add(Playlist(id="not-committed", title=None, published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            return {"fake": "summary"}
        request_id = str(uuid4())
        with patch("project.services.library_service.sync_playlists_and_videos", side_effect=invalid_write):
            self.assertEqual(self._post("/api/v1/library/sync", headers=headers, json={"request_id": request_id}).status_code, 500)
        report = self._get(f"/api/v1/library/sync-status?request_id={request_id}", headers=headers).get_json()
        self.assertEqual(report["requested"]["status"], "failed")
        self.assertIsNone(report["requested"]["summary"])
        self.assertEqual(report["last_success"]["id"], successful["id"])
        with self.app.app_context():
            self.assertIsNone(db.session.get(Playlist, "not-committed"))
            self.assertEqual(LibrarySyncRun.query.count(), 2)

    def test_import_counts_deduplicate_and_detect_playlist_position_changes(self):
        from project.library.jobs import sync_playlists_and_videos
        playlist = {"id": "counted", "snippet": {"title": "Lessons", "publishedAt": "2024-01-01T00:00:00Z"}}
        def video(id, title, position):
            return {"id": id, "snippet": {"title": title, "description": "", "position": position, "publishedAt": "2024-01-02T00:00:00Z"}, "contentDetails": {"videoId": id}, "status": {"privacyStatus": "public"}}
        items = [video("first", "Lesson 1", 0), video("second", "Lesson 2", 1), video("skipped", "Deleted video", 2)]
        with self.app.app_context(), patch("project.library.jobs.get_youtube_service"), patch("project.library.jobs.fetch_playlists", return_value=[playlist, playlist]), patch("project.library.jobs.fetch_videos", return_value=items):
            added = sync_playlists_and_videos()
            self.assertEqual(added["playlists"]["checked"], 1)
            self.assertEqual(added["videos"], {"checked": 3, "added": 2, "updated": 0, "unchanged": 0, "skipped": 1})
            db.session.get(Video, "first").watched = True
            db.session.commit()
            unchanged = sync_playlists_and_videos()
            self.assertEqual(unchanged["videos"]["unchanged"], 2)
            self.assertEqual(unchanged["playlists"]["unchanged"], 1)
            items[0]["snippet"]["position"] = 1
            items[1]["snippet"]["position"] = 0
            moved = sync_playlists_and_videos()
            self.assertEqual(moved["videos"]["updated"], 2)
            self.assertTrue(db.session.get(Video, "first").watched)
            self.assertEqual(db.session.get(Video, "second").position, 0)
