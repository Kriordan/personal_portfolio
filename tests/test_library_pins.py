"""Personal pins remain independent of the shared catalog and other accounts."""
from datetime import datetime, timezone
import unittest
from flask_jwt_extended import create_access_token
from project import create_app
from project.database import db
from project.models import LibraryPin, Playlist, User


class LibraryPinTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "JWT_SECRET_KEY": "pin-test-key-at-least-32-characters", "WTF_CSRF_ENABLED": False})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        db.session.add_all([User(id=i, username=f"user{i}", email=f"user{i}@example.test") for i in (1, 2)])
        db.session.add(Playlist(id="playlist", title="Shared", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def call(self, method, path="/pins", user=1, **kwargs):
        headers = {"Authorization": f"Bearer {create_access_token(identity=str(user))}"} if user else {}
        return getattr(self.client, method)(f"/api/v1/library{path}", base_url="https://localhost", headers=headers, **kwargs)

    def test_pins_are_idempotent_private_and_shared_across_sessions(self):
        first = self.call("put", "/pins/playlist", json={"pinned": True}).get_json()
        again = self.call("put", "/pins/playlist", json={"pinned": True}).get_json()
        self.assertEqual(first, again)
        self.assertEqual(LibraryPin.query.count(), 1)
        # A fresh JWT/session for the same account sees the server-owned pins.
        self.assertEqual(self.call("get").get_json(), first)
        self.assertEqual(self.call("get", user=2).get_json(), {"pins": []})
        self.call("put", "/pins/playlist", user=2, json={"pinned": False})
        self.assertEqual(self.call("get").get_json(), first)
        self.assertEqual(self.call("get").headers["Cache-Control"], "private, no-store")
        for _ in range(2):
            self.assertEqual(self.call("put", "/pins/playlist", json={"pinned": False}).get_json(), {"pins": []})
        self.assertEqual(Playlist.query.count(), 1)

    def test_validation_and_authentication(self):
        self.assertEqual(self.call("get", user=None).status_code, 401)
        self.assertEqual(self.call("put", "/pins/playlist", user=None, json={"pinned": True}).status_code, 401)
        self.assertEqual(self.call("get", user=999).status_code, 401)
        for value in [None, 1, "true", [], {}]:
            self.assertEqual(self.call("put", "/pins/playlist", json={"pinned": value}).status_code, 400)
        self.assertEqual(self.call("put", "/pins/missing", json={"pinned": True}).status_code, 404)
        self.assertEqual(LibraryPin.query.count(), 0)
