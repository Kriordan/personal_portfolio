"""The hosted pilot closes every Learning route to users outside its one-account allowlist."""
import unittest
from unittest.mock import patch

from flask import g, url_for
from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import PracticeSession, ReviewProgress, User


class HostedLearningAccessTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(dict(TESTING=True, SECRET_KEY="hosted-fixture-secret-at-least-32-characters", SENTRY_ENABLED=False,
            SQLALCHEMY_DATABASE_URI="sqlite://", WTF_CSRF_ENABLED=False,
            LEARNING_PRACTICE_ENABLED=True, LEARNING_AI_ENABLED=False,
            LEARNING_HOSTED_PILOT=True, LEARNING_HOSTED_OWNER_ID=1,
            LEARNING_AI_OWNER_EMAIL="owner@example.test"))
        self.app.debug = True
        @self.app.before_request
        def clear_test_login_cache():
            # The enclosing fixture app context spans multiple independent clients.
            g.pop("_login_user", None)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            User(id=1, username="owner", email="owner@example.test", email_verified=True),
            User(id=2, username="other-admin", email="other@example.test", email_verified=True, is_admin=True),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def browser(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"], session["_fresh"] = str(user_id), True
        return client

    def token(self, user_id):
        return {"Authorization": "Bearer " + create_access_token(identity=str(user_id))}

    def routes(self):
        with self.app.test_request_context():
            for rule in self.app.url_map.iter_rules():
                if rule.endpoint.startswith(("learning.", "api.api_learning.", "api.api_learning_practice.")):
                    values = {name: 1 if converter.__class__.__name__ == "IntegerConverter" else "fixture"
                              for name, converter in rule._converters.items()}
                    yield url_for(rule.endpoint, **values), rule.methods & {"GET", "POST", "PUT", "DELETE", "HEAD"}

    def test_every_learning_route_rejects_another_verified_admin_without_writes(self):
        client = self.browser(2)
        for path, methods in self.routes():
            for method in methods:
                with self.subTest(path=path, method=method):
                    response = client.open(path, method=method, json={}, headers=self.token(2))
                    self.assertEqual(response.status_code, 404)
                    if path.startswith("/api/"):
                        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertEqual(PracticeSession.query.count(), 0)
        self.assertEqual(ReviewProgress.query.count(), 0)
        self.assertEqual(client.get("/api/v1/auth/me", headers=self.token(2)).status_code, 200)

    def test_owner_keeps_access_and_navigation_but_anonymous_users_must_login(self):
        owner = self.browser(1)
        self.assertEqual(owner.get("/learning/").status_code, 200)
        self.assertEqual(owner.get("/api/v1/learning/notes", headers=self.token(1)).status_code, 200)
        self.assertIn('href="/learning/"', owner.get("/").get_data(as_text=True))
        other = self.browser(2).get("/").get_data(as_text=True)
        self.assertNotIn('href="/learning/"', other)
        self.assertIn("Scratch-offs", other)
        guest = self.app.test_client()
        self.assertEqual(guest.get("/learning/").status_code, 302)
        self.assertEqual(guest.get("/api/v1/learning/notes").status_code, 401)
        # A web login cookie never authorizes a Learning API call by itself.
        self.assertEqual(owner.get("/api/v1/learning/notes").status_code, 401)

    def test_missing_mismatched_or_revoked_owner_configuration_closes_access(self):
        owner = self.browser(1)
        for change in (dict(LEARNING_HOSTED_OWNER_ID=None), dict(LEARNING_HOSTED_OWNER_ID=True),
                       dict(LEARNING_HOSTED_OWNER_ID=2), dict(LEARNING_AI_OWNER_EMAIL=None),
                       dict(LEARNING_AI_OWNER_EMAIL="other@example.test")):
            with self.subTest(change=change), patch.dict(self.app.config, change):
                self.assertEqual(owner.get("/learning/").status_code, 404)
                self.assertEqual(owner.get("/api/v1/learning/notes", headers=self.token(1)).status_code, 404)
        db.session.get(User, 1).email_verified = False
        db.session.commit()
        self.assertEqual(owner.get("/learning/").status_code, 404)
        self.assertEqual(owner.get("/api/v1/learning/notes", headers=self.token(1)).status_code, 404)

    def test_normal_learning_configuration_retains_existing_access(self):
        with patch.dict(self.app.config, LEARNING_HOSTED_PILOT=False):
            other = self.browser(2)
            self.assertEqual(other.get("/learning/").status_code, 200)
            self.assertEqual(other.get("/api/v1/learning/notes", headers=self.token(2)).status_code, 200)
            self.assertIn('href="/learning/"', other.get("/").get_data(as_text=True))
