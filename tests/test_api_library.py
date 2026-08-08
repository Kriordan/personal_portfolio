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
        mock_sync.assert_called_once_with()

    @patch("project.services.library_service.sync_playlists_and_videos")
    def test_sync_requires_jwt_and_does_not_run_job(self, mock_sync):
        response = self._post("/api/v1/library/sync")

        self.assertEqual(response.status_code, 401)
        mock_sync.assert_not_called()
