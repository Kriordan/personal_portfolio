"""Exercise Google/requests-oauthlib's client flow without external credentials."""

import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from requests import Request, Response

from project import create_app
from project.database import db
from project.models import User


class OAuthClientTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": "test-session-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(email="oauth@example.com", username="oauth", email_verified=True)
            user.set_password("test-password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        config = {"web": {
            "client_id": "test-client", "client_secret": "test-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["https://localhost/oauth/oauth2callback"],
        }}
        self.config = patch("project.oauth.views.client_config", config)
        self.config.start()
        self.addCleanup(self.config.stop)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch("project.library.jobs.save_credentials_to_file")
    @patch("requests.sessions.Session.request")
    def test_authorization_code_exchange_and_state_validation(self, request, save):
        response = self.client.get("/oauth/authorize", base_url="https://localhost")
        self.assertEqual(response.status_code, 302)
        url = urlparse(response.location)
        self.assertEqual(url.hostname, "accounts.google.com")
        params = parse_qs(url.query)
        self.assertEqual(params["client_id"], ["test-client"])
        self.assertEqual(params["response_type"], ["code"])
        state = params["state"][0]

        rejected = self.client.get(
            "/oauth/oauth2callback?state=wrong&code=test-code", base_url="https://localhost",
        )
        self.assertEqual(rejected.status_code, 400)
        request.assert_not_called()

        token_response = Response()
        token_response.status_code = 200
        token_response.request = Request("POST", "https://oauth2.googleapis.com/token").prepare()
        token_response._content = json.dumps({
            "access_token": "test-access", "refresh_token": "test-refresh",
            "token_type": "Bearer", "expires_in": 3600,
        }).encode()
        request.return_value = token_response
        accepted = self.client.get(
            "/oauth/oauth2callback", query_string={"state": state, "code": "test-code"},
            base_url="https://localhost",
        )
        self.assertEqual(accepted.status_code, 302)
        self.assertIn("oauth2.googleapis.com/token", request.call_args.args[1])
        self.assertEqual(save.call_args.args[0]["refresh_token"], "test-refresh")
        with self.client.session_transaction() as session:
            self.assertEqual(session["credentials"]["token"], "test-access")
