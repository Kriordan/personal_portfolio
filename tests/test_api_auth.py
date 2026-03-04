import unittest
from unittest.mock import patch

from project import create_app
from project.database import db
from project.models import SiteInvitation, User


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "JWT_SECRET_KEY": "test-jwt-secret-should-be-at-least-32",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "MAILERSEND_API_KEY": "test-mailersend-key",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_user(
        self,
        *,
        email: str,
        username: str,
        password: str = "password123",
        email_verified: bool = True,
    ) -> User:
        with self.app.app_context():
            user = User(email=email, username=username, email_verified=email_verified)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return user

    def _post(self, path: str, **kwargs):
        return self.client.post(path, base_url="https://localhost", **kwargs)

    def _options(self, path: str, **kwargs):
        return self.client.options(path, base_url="https://localhost", **kwargs)

    def test_cors_headers_apply_to_api_routes_only(self):
        response = self._options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://mobile.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.headers.get("Access-Control-Allow-Origin"))

        web_response = self._options(
            "/login",
            headers={
                "Origin": "https://mobile.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(web_response.status_code, 200)
        self.assertIsNone(web_response.headers.get("Access-Control-Allow-Origin"))

    def test_login_returns_tokens_for_verified_user(self):
        self._create_user(email="verified@example.com", username="verified")

        response = self._post(
            "/api/v1/auth/login",
            json={"email": "verified@example.com", "password": "password123"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("access_token", payload)
        self.assertIn("refresh_token", payload)
        self.assertEqual(payload["user"]["email"], "verified@example.com")

    def test_login_does_not_create_flask_login_session(self):
        self._create_user(email="jwt-only@example.com", username="jwt-only")

        response = self._post(
            "/api/v1/auth/login",
            json={"email": "jwt-only@example.com", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_login_rejects_unverified_user(self):
        self._create_user(
            email="unverified@example.com",
            username="unverified",
            email_verified=False,
        )

        response = self._post(
            "/api/v1/auth/login",
            json={"email": "unverified@example.com", "password": "password123"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Email verification required.",
        )

    def test_refresh_returns_new_access_token(self):
        self._create_user(email="refresh@example.com", username="refresh")
        login_response = self._post(
            "/api/v1/auth/login",
            json={"email": "refresh@example.com", "password": "password123"},
        )
        refresh_token = login_response.get_json()["refresh_token"]

        refresh_response = self._post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )

        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access_token", refresh_response.get_json())

    @patch("project.api.auth._send_verification_email")
    def test_signup_creates_user_from_site_invite(self, mock_send_verification_email):
        with self.app.app_context():
            invite = SiteInvitation.create_invitation(email="invitee@example.com")
            db.session.add(invite)
            db.session.commit()
            token = invite.token

        response = self._post(
            f"/api/v1/auth/signup/{token}",
            json={
                "email": "invitee@example.com",
                "username": "newuser",
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["message"], "Account created.")
        mock_send_verification_email.assert_called_once()

        with self.app.app_context():
            created_user = User.query.filter_by(email="invitee@example.com").one_or_none()
            self.assertIsNotNone(created_user)
            self.assertFalse(created_user.email_verified)
            self.assertIsNotNone(created_user.email_verification_token)
            invite = SiteInvitation.query.filter_by(email="invitee@example.com").one()
            self.assertIsNotNone(invite.accepted_at)
