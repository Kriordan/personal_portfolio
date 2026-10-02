import unittest

from flask_jwt_extended import create_access_token, create_refresh_token

from project import create_app
from project.database import db
from project.models import CustomList, User
from project.sockets import socketio


class SocketAuthTests(unittest.TestCase):
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
        self.http_client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_user(self, email: str, username: str) -> int:
        with self.app.app_context():
            user = User(email=email, username=username, email_verified=True)
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            return user.id

    def test_socket_connect_rejects_unauthenticated_client(self):
        client = socketio.test_client(self.app, flask_test_client=self.http_client)
        self.assertFalse(client.is_connected())

    def test_socket_connect_accepts_valid_jwt_access_token(self):
        user_id = self._create_user(email="socket@example.com", username="socket-user")
        with self.app.app_context():
            token = create_access_token(identity=str(user_id))

        client = socketio.test_client(
            self.app,
            auth={"token": token},
            flask_test_client=self.http_client,
        )
        self.assertTrue(client.is_connected())
        client.disconnect()

    def test_socket_connect_rejects_refresh_token(self):
        user_id = self._create_user(email="refresh@example.com", username="refresh-user")
        with self.app.app_context():
            token = create_refresh_token(identity=str(user_id))

        client = socketio.test_client(
            self.app,
            auth={"token": token},
            flask_test_client=self.http_client,
        )
        self.assertFalse(client.is_connected())

    def test_jwt_socket_client_can_join_owned_list(self):
        user_id = self._create_user(email="owner@example.com", username="owner-user")
        with self.app.app_context():
            custom_list = CustomList(title="Groceries", owner_id=user_id)
            db.session.add(custom_list)
            db.session.commit()
            list_id = custom_list.id
            token = create_access_token(identity=str(user_id))

        client = socketio.test_client(
            self.app,
            auth={"token": token},
            flask_test_client=self.http_client,
        )
        self.assertTrue(client.is_connected())

        response = client.emit("join_list", {"list_id": list_id}, callback=True)
        self.assertEqual(response["success"], True)
        self.assertEqual(response["room"], f"list_{list_id}")
        client.disconnect()

    def test_shared_jwt_and_website_session_exchange_list_events(self):
        owner_id = self._create_user("web@example.com", "web-owner")
        member_id = self._create_user("mobile@example.com", "mobile-member")
        stranger_id = self._create_user("outside@example.com", "outside")
        with self.app.app_context():
            custom_list = CustomList(title="Shared groceries", owner_id=owner_id)
            custom_list.shared_with.append(db.session.get(User, member_id))
            db.session.add(custom_list)
            db.session.commit()
            list_id = custom_list.id
            member_token = create_access_token(identity=str(member_id))
            stranger_token = create_access_token(identity=str(stranger_id))
        with self.http_client.session_transaction() as session:
            session["_user_id"] = str(owner_id)
            session["_fresh"] = True
        web = socketio.test_client(self.app, flask_test_client=self.http_client)
        mobile = socketio.test_client(self.app, auth={"token": member_token})
        stranger = socketio.test_client(self.app, auth={"token": stranger_token})
        self.addCleanup(lambda: web.disconnect() if web.is_connected() else None)
        self.addCleanup(lambda: mobile.disconnect() if mobile.is_connected() else None)
        self.addCleanup(lambda: stranger.disconnect() if stranger.is_connected() else None)
        self.assertTrue(web.emit("join_list", {"list_id": list_id}, callback=True)["success"])
        self.assertTrue(mobile.emit("join_list", {"list_id": list_id}, callback=True)["success"])
        self.assertFalse(stranger.emit("join_list", {"list_id": list_id}, callback=True)["success"])
        web.get_received()
        mobile.get_received()
        mobile.emit("item_toggled", {"list_id": list_id, "item_id": 1, "completed": True})
        event = next(event for event in web.get_received() if event["name"] == "item_toggled")
        self.assertEqual(event["args"][0]["toggled_by"], "mobile-member")
        self.assertTrue(event["args"][0]["completed"])
        self.assertFalse(any(event["name"] == "item_toggled" for event in stranger.get_received()))
        web.emit("settings_updated", {"list_id": list_id, "completed_display_mode": "global_section"})
        event = next(event for event in mobile.get_received() if event["name"] == "settings_updated")
        self.assertEqual(event["args"][0]["completed_display_mode"], "global_section")
