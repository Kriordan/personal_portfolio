"""Exercise the shared OAuth connection without real credentials or Google calls."""

import importlib.util
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token
from google.oauth2.credentials import Credentials
from requests import Request, Response
from sqlalchemy import inspect

from project import create_app
from project.database import db
from project.library.credentials import (
    SCOPES, MOVE_SCOPES, YouTubeConfigurationError, load_shared_credentials, save_shared_credentials,
)
from project.library.jobs import get_youtube_service
from project.models import Playlist, User, YouTubeConnection


class OAuthClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = {
            "TESTING": True, "SECRET_KEY": "test-session-secret-at-least-32-bytes",
            "JWT_SECRET_KEY": "test-jwt-secret-at-least-32-bytes-long",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.directory.name}/connection.db",
            "WTF_CSRF_ENABLED": False,
            "GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "test-client-secret",
            "YOUTUBE_CREDENTIALS_KEY": Fernet.generate_key().decode(),
            "YOUTUBE_OAUTH_REDIRECT_URI": "https://localhost/oauth/oauth2callback",
        }
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            admin = User(email="admin@example.com", username="admin", is_admin=True, email_verified=True)
            user = User(email="member@example.com", username="member", is_admin=False, email_verified=True)
            db.session.add_all([admin, user])
            db.session.commit()
            self.admin_id, self.member_id = admin.id, user.id
        self.sign_in(self.admin_id)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def sign_in(self, user_id):
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def get(self, path):
        return self.client.get(path, base_url="https://localhost")

    def post(self, path, **kwargs):
        return self.client.post(path, base_url="https://localhost", **kwargs)

    def start(self):
        response = self.post("/oauth/authorize")
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlparse(response.location).query)
        return params["state"][0], params

    def credentials(self, refresh_token="test-refresh"):
        return Credentials(
            token="test-access", refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token", client_id="test-client",
            client_secret="test-client-secret", scopes=SCOPES,
        )

    def save(self, refresh_token="test-refresh"):
        with self.app.app_context():
            save_shared_credentials(self.credentials(refresh_token), connected_by_id=self.admin_id)

    def token_response(self, refresh_token="test-refresh"):
        response = Response()
        response.status_code = 200
        response.request = Request("POST", "https://oauth2.googleapis.com/token").prepare()
        payload = {"access_token": "test-access", "token_type": "Bearer", "expires_in": 3600}
        if refresh_token:
            payload["refresh_token"] = refresh_token
        response._content = json.dumps(payload).encode()
        return response

    @patch("requests.sessions.Session.request")
    def test_real_code_exchange_pkce_and_state_validation(self, request):
        with self.client.session_transaction() as session:
            session["credentials"] = {"token": "legacy-private-token"}
        state, params = self.start()
        self.assertEqual(params["client_id"], ["test-client"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["access_type"], ["offline"])
        self.assertEqual(params["prompt"], ["consent"])
        self.assertEqual(params["scope"], SCOPES)
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertEqual(self.get("/oauth/oauth2callback?state=wrong&code=test-code").status_code, 400)
        self.assertEqual(self.get("/oauth/oauth2callback?state=%E2%98%83&code=test-code").status_code, 400)
        request.assert_not_called()
        request.return_value = self.token_response()
        response = self.get(f"/oauth/oauth2callback?state={state}&code=test-code")
        self.assertEqual(response.status_code, 302)
        self.assertIn("oauth2.googleapis.com/token", request.call_args.args[1])
        self.assertIn("code_verifier", request.call_args.kwargs["data"])
        with self.client.session_transaction() as session:
            self.assertNotIn("credentials", session)
            self.assertNotIn("youtube_oauth", session)
            self.assertNotIn("test-refresh", str(dict(session)))
            self.assertNotIn("test-access", str(dict(session)))
        with self.app.app_context():
            saved = db.session.get(YouTubeConnection, 1)
            self.assertNotIn("test-refresh", saved.encrypted_refresh_token)
            self.assertNotIn("test-access", saved.encrypted_refresh_token)
            self.assertEqual(load_shared_credentials().refresh_token, "test-refresh")
        request.reset_mock()
        self.assertEqual(self.get(f"/oauth/oauth2callback?state={state}&code=test-code").status_code, 400)
        request.assert_not_called()

    def test_only_admins_can_manage_connection(self):
        self.sign_in(self.member_id)
        for method, path in [(self.get, "/oauth/"), (self.post, "/oauth/authorize"),
                             (self.get, "/oauth/oauth2callback"), (self.post, "/oauth/test"),
                             (self.post, "/oauth/revoke")]:
            self.assertEqual(method(path).status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.get("/oauth/").status_code, 302)

    def test_playlist_scope_upgrade_is_explicit_owner_only_and_decline_preserves_read_sync(self):
        self.save()
        response = self.post("/oauth/authorize", data={"playlist_changes": "yes"})
        params = parse_qs(urlparse(response.location).query)
        self.assertEqual(params["scope"][0].split(), MOVE_SCOPES)
        state = params["state"][0]
        self.assertEqual(self.get(f"/oauth/oauth2callback?state={state}&error=access_denied").status_code, 400)
        with self.app.app_context():
            self.assertEqual(load_shared_credentials().scopes, SCOPES)
            another = User(email="another-admin@example.test", username="another-admin", is_admin=True)
            db.session.add(another)
            db.session.commit()
            other_id = another.id
        self.sign_in(other_id)
        self.assertEqual(self.post("/oauth/authorize", data={"playlist_changes": "yes"}).status_code, 403)
        self.assertEqual(self.post("/oauth/workflow", data={"source_playlist_id": "PLone", "destination_playlist_id": "PLtwo"}).status_code, 403)

    def test_actual_scope_grant_is_persisted_and_partial_upgrade_is_rejected(self):
        self.save("original")
        with self.app.app_context():
            read_only = self.credentials()
            with self.assertRaises(YouTubeConfigurationError):
                save_shared_credentials(read_only, connected_by_id=self.admin_id, channel_id="channel", requested_scopes=MOVE_SCOPES)
            self.assertEqual(load_shared_credentials().refresh_token, "original")
            granted = Credentials(token="fixture", refresh_token="new", token_uri="https://oauth2.googleapis.com/token",
                client_id="test-client", scopes=MOVE_SCOPES, granted_scopes=MOVE_SCOPES)
            save_shared_credentials(granted, connected_by_id=self.admin_id, channel_id="channel", requested_scopes=MOVE_SCOPES)
            self.assertEqual(load_shared_credentials().scopes, MOVE_SCOPES)
            self.assertEqual(db.session.get(YouTubeConnection, 1).channel_id, "channel")

    @patch("requests.sessions.Session.request")
    def test_expired_or_cross_account_callback_never_exchanges_code(self, request):
        for change in ({"created_at": time.time() - 601}, {"user_id": self.member_id}):
            state, _ = self.start()
            with self.client.session_transaction() as session:
                pending = dict(session["youtube_oauth"])
                pending.update(change)
                session["youtube_oauth"] = pending
            self.assertEqual(self.get(f"/oauth/oauth2callback?state={state}&code=test-code").status_code, 400)
        request.assert_not_called()

    @patch("requests.sessions.Session.request")
    def test_duplicate_state_and_host_mismatch_never_exchange_code(self, request):
        state, _ = self.start()
        self.assertEqual(self.get(f"/oauth/oauth2callback?state={state}&state={state}&code=c").status_code, 400)
        self.app.config["YOUTUBE_OAUTH_REDIRECT_URI"] = "https://example.com/oauth/oauth2callback"
        self.assertEqual(self.get(f"/oauth/oauth2callback?state={state}&code=c").status_code, 400)
        request.assert_not_called()

    @patch("requests.sessions.Session.request")
    def test_declined_consent_preserves_previous_connection(self, request):
        self.save("original-refresh")
        state, _ = self.start()
        self.assertEqual(self.get(f"/oauth/oauth2callback?state={state}&error=access_denied").status_code, 400)
        request.assert_not_called()
        with self.app.app_context():
            self.assertEqual(load_shared_credentials().refresh_token, "original-refresh")

    @patch("requests.sessions.Session.request")
    def test_exchange_failure_and_missing_refresh_preserve_previous_connection(self, request):
        self.save("original-refresh")
        for fail in (True, False):
            state, _ = self.start()
            request.side_effect = RuntimeError("provider-private-token") if fail else None
            request.return_value = self.token_response(refresh_token=None)
            with self.assertLogs(self.app.logger, level="WARNING") as logs:
                response = self.get(f"/oauth/oauth2callback?state={state}&code=test-code")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("provider-private-token", response.get_data(as_text=True) + str(logs.output))
            with self.app.app_context():
                self.assertEqual(load_shared_credentials().refresh_token, "original-refresh")

    def test_connection_survives_fresh_app_with_no_browser_session_or_file(self):
        self.save()
        fresh_app = create_app(self.config)
        with fresh_app.app_context():
            credentials = load_shared_credentials()
            self.assertEqual(credentials.refresh_token, "test-refresh")
            self.assertIsNone(credentials.token)
            self.assertEqual(credentials.client_secret, "test-client-secret")
            db.session.remove()
            db.engine.dispose()

    @patch("requests.sessions.Session.request")
    def test_durable_refresh_token_can_obtain_a_new_access_token(self, request):
        from google.auth.transport.requests import Request as GoogleRequest
        self.save()
        request.return_value = self.token_response()
        with self.app.app_context():
            credentials = load_shared_credentials()
            credentials.refresh(GoogleRequest())
            self.assertEqual(credentials.token, "test-access")
            self.assertTrue(credentials.valid)
            self.assertEqual(load_shared_credentials().token, None)
        body = request.call_args.kwargs["data"]
        if isinstance(body, bytes):
            body = body.decode()
        self.assertEqual(parse_qs(body)["grant_type"], ["refresh_token"])
        self.assertEqual(parse_qs(body)["refresh_token"], ["test-refresh"])

    def test_api_sync_uses_shared_connection_for_another_user_ignoring_cookie(self):
        self.save()
        with self.app.app_context():
            token = create_access_token(identity=str(self.member_id))
        with self.client.session_transaction() as session:
            session["credentials"] = {"refresh_token": "wrong-browser-account"}
        with patch("project.library.jobs.build") as build, patch("project.library.jobs.fetch_playlists", return_value=[]):
            response = self.post("/api/v1/library/sync", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(build.call_args.kwargs["credentials"].refresh_token, "test-refresh")

    def test_missing_key_changed_client_or_tampering_fails_closed(self):
        self.save()
        with self.app.app_context():
            for overrides in ({"YOUTUBE_CREDENTIALS_KEY": None},
                              {"YOUTUBE_CREDENTIALS_KEY": "bad-key"},
                              {"YOUTUBE_CREDENTIALS_KEY": Fernet.generate_key().decode()},
                              {"GOOGLE_CLIENT_ID": "different-client"}):
                with patch.dict(self.app.config, overrides):
                    with self.assertRaises(YouTubeConfigurationError):
                        load_shared_credentials()
            record = db.session.get(YouTubeConnection, 1)
            record.encrypted_refresh_token = "tampered"
            db.session.commit()
            with self.assertRaises(YouTubeConfigurationError):
                load_shared_credentials()

    def test_missing_connection_does_not_use_legacy_cookie_or_file(self):
        with self.app.test_request_context("/"):
            from flask import session
            session["credentials"] = {"token": "legacy-token"}
            with self.assertRaises(YouTubeConfigurationError):
                get_youtube_service()

    def test_management_posts_require_csrf_and_gets_do_not_mutate(self):
        self.save()
        self.app.config["WTF_CSRF_ENABLED"] = True
        for path in ("/oauth/authorize", "/oauth/test", "/oauth/revoke"):
            self.assertEqual(self.post(path).status_code, 400)
            self.assertEqual(self.get(path).status_code, 302)
        self.assertEqual(self.post("/oauth/workflow").status_code, 400)
        with self.app.app_context():
            self.assertEqual(load_shared_credentials().refresh_token, "test-refresh")
        page = self.get("/oauth/")
        self.assertIn('name="csrf_token"', page.get_data(as_text=True))
        self.assertEqual(page.headers["Cache-Control"], "private, no-store")
        self.assertEqual(page.headers["Referrer-Policy"], "no-referrer")
        self.assertNotIn("test-refresh", page.get_data(as_text=True))
        self.assertNotIn("googletagmanager", page.get_data(as_text=True))

    @patch("project.library.jobs.get_youtube_service")
    def test_connection_check_does_not_import_catalog(self, service):
        self.save()
        with patch("project.library.jobs.sync_playlists_and_videos") as sync:
            response = self.post("/oauth/test")
            self.assertEqual(response.status_code, 302)
            sync.assert_not_called()
        service.return_value.__enter__.return_value.channels.return_value.list.assert_called_once_with(
            part="id", mine=True, maxResults=1,
        )

    @patch("requests.post")
    def test_revocation_is_explicit_and_does_not_delete_catalog(self, post):
        self.save()
        with self.app.app_context():
            db.session.add(Playlist(id="saved-playlist", title="Saved", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            db.session.commit()
        self.assertEqual(self.get("/oauth/revoke").status_code, 302)
        post.assert_not_called()
        self.assertEqual(self.post("/oauth/revoke").status_code, 302)
        self.assertEqual(post.call_args.kwargs["data"], {"token": "test-refresh"})
        self.assertNotIn("params", post.call_args.kwargs)
        with self.app.app_context():
            self.assertIsNone(db.session.get(YouTubeConnection, 1))
            self.assertIsNotNone(db.session.get(Playlist, "saved-playlist"))

    def test_new_migration_roundtrip_preserves_existing_catalog(self):
        spec = importlib.util.spec_from_file_location(
            "connection_migration", Path(__file__).parents[1] / "migrations/versions/f6a7b8c9d0e1_add_shared_youtube_connection.py",
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.app.app_context():
            db.session.add(Playlist(id="saved-playlist", title="Saved", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            db.session.commit()
            YouTubeConnection.__table__.drop(db.engine)
            with db.engine.begin() as connection:
                with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                    migration.upgrade()
                    self.assertIn("youtube_connection", inspect(connection).get_table_names())
                    migration.downgrade()
                    self.assertNotIn("youtube_connection", inspect(connection).get_table_names())
                    migration.upgrade()
            self.assertIsNotNone(db.session.get(Playlist, "saved-playlist"))
