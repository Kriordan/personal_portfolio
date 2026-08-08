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
