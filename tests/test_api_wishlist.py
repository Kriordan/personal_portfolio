import io
import unittest
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import Gift, User


class ApiWishlistTests(unittest.TestCase):
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

    def _create_gift(self, *, user_id: int, title: str = "Bike", body: str = "Red one") -> int:
        with self.app.app_context():
            gift = Gift(title=title, body=body, user_id=user_id)
            db.session.add(gift)
            db.session.commit()
            return gift.id

    def _auth_headers(self, user_id: int) -> dict:
        with self.app.app_context():
            token = create_access_token(identity=str(user_id))
        return {"Authorization": f"Bearer {token}"}

    def _get(self, path: str, **kwargs):
        return self.client.get(path, base_url="https://localhost", **kwargs)

    def _post(self, path: str, **kwargs):
        return self.client.post(path, base_url="https://localhost", **kwargs)

    def _put(self, path: str, **kwargs):
        return self.client.put(path, base_url="https://localhost", **kwargs)

    def _delete(self, path: str, **kwargs):
        return self.client.delete(path, base_url="https://localhost", **kwargs)

    def test_wishlist_endpoints_require_jwt(self):
        unauthenticated_requests = [
            self._get("/api/v1/wishlist/gifts"),
            self._post("/api/v1/wishlist/gifts", json={"title": "x", "body": "y"}),
            self._get("/api/v1/wishlist/gifts/1"),
            self._put("/api/v1/wishlist/gifts/1", json={"title": "x"}),
            self._delete("/api/v1/wishlist/gifts/1"),
        ]

        for response in unauthenticated_requests:
            self.assertEqual(response.status_code, 401)

    def test_get_gifts_returns_only_own_gifts(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        other_id = self._create_user(email="other@example.com", username="other")
        own_gift_id = self._create_gift(user_id=owner_id, title="Bike")
        self._create_gift(user_id=other_id, title="Skateboard")

        response = self._get("/api/v1/wishlist/gifts", headers=self._auth_headers(owner_id))

        self.assertEqual(response.status_code, 200)
        gifts = response.get_json()["gifts"]
        self.assertEqual(len(gifts), 1)
        self.assertEqual(gifts[0]["id"], own_gift_id)
        self.assertEqual(gifts[0]["title"], "Bike")

    def test_create_gift_returns_serialized_payload(self):
        user_id = self._create_user(email="owner@example.com", username="owner")

        response = self._post(
            "/api/v1/wishlist/gifts",
            headers=self._auth_headers(user_id),
            json={"title": "Bike", "body": "Red one"},
        )

        self.assertEqual(response.status_code, 201)
        gift = response.get_json()["gift"]
        for key in ("id", "title", "body", "image_url", "timestamp", "user_id"):
            self.assertIn(key, gift)
        self.assertEqual(gift["title"], "Bike")
        self.assertEqual(gift["body"], "Red one")
        self.assertEqual(gift["user_id"], user_id)
        self.assertIsNone(gift["image_url"])

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Gift, gift["id"]))

    def test_create_gift_validates_required_fields(self):
        user_id = self._create_user(email="owner@example.com", username="owner")

        response = self._post(
            "/api/v1/wishlist/gifts",
            headers=self._auth_headers(user_id),
            json={"title": "  ", "body": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "title and body are required")

    @patch("project.services.wishlist_service.upload_image_to_s3")
    def test_create_gift_uploads_image_without_real_s3(self, mock_upload):
        mock_upload.return_value = "https://bucket.s3.amazonaws.com/bike.png"
        user_id = self._create_user(email="owner@example.com", username="owner")

        response = self._post(
            "/api/v1/wishlist/gifts",
            headers=self._auth_headers(user_id),
            data={
                "title": "Bike",
                "body": "Red one",
                "image": (io.BytesIO(b"fake-image-bytes"), "bike.png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        mock_upload.assert_called_once()
        self.assertEqual(
            response.get_json()["gift"]["image_url"],
            "https://bucket.s3.amazonaws.com/bike.png",
        )

    def test_get_gift_returns_owned_gift(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        gift_id = self._create_gift(user_id=owner_id)

        response = self._get(
            f"/api/v1/wishlist/gifts/{gift_id}", headers=self._auth_headers(owner_id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["gift"]["id"], gift_id)

    def test_get_gift_returns_404_for_unknown_gift(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")

        response = self._get(
            "/api/v1/wishlist/gifts/9999", headers=self._auth_headers(owner_id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Gift not found.")

    def test_get_gift_hides_foreign_gift_as_404(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        intruder_id = self._create_user(email="intruder@example.com", username="intruder")
        gift_id = self._create_gift(user_id=owner_id)

        response = self._get(
            f"/api/v1/wishlist/gifts/{gift_id}", headers=self._auth_headers(intruder_id)
        )

        self.assertEqual(response.status_code, 404)

    def test_update_gift_changes_fields(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        gift_id = self._create_gift(user_id=owner_id, title="Bike", body="Red one")

        response = self._put(
            f"/api/v1/wishlist/gifts/{gift_id}",
            headers=self._auth_headers(owner_id),
            json={"title": "Mountain Bike"},
        )

        self.assertEqual(response.status_code, 200)
        gift = response.get_json()["gift"]
        self.assertEqual(gift["title"], "Mountain Bike")
        self.assertEqual(gift["body"], "Red one")

    def test_update_gift_rejects_blank_title(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        gift_id = self._create_gift(user_id=owner_id)

        response = self._put(
            f"/api/v1/wishlist/gifts/{gift_id}",
            headers=self._auth_headers(owner_id),
            json={"title": "   "},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "title cannot be empty")

    def test_update_gift_hides_foreign_gift_as_404(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        intruder_id = self._create_user(email="intruder@example.com", username="intruder")
        gift_id = self._create_gift(user_id=owner_id, title="Bike")

        response = self._put(
            f"/api/v1/wishlist/gifts/{gift_id}",
            headers=self._auth_headers(intruder_id),
            json={"title": "Hijacked"},
        )

        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertEqual(db.session.get(Gift, gift_id).title, "Bike")

    def test_delete_gift_removes_owned_gift(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        gift_id = self._create_gift(user_id=owner_id)

        response = self._delete(
            f"/api/v1/wishlist/gifts/{gift_id}", headers=self._auth_headers(owner_id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"], "Gift deleted.")
        with self.app.app_context():
            self.assertIsNone(db.session.get(Gift, gift_id))

    def test_delete_gift_hides_foreign_gift_as_404(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        intruder_id = self._create_user(email="intruder@example.com", username="intruder")
        gift_id = self._create_gift(user_id=owner_id)

        response = self._delete(
            f"/api/v1/wishlist/gifts/{gift_id}", headers=self._auth_headers(intruder_id)
        )

        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Gift, gift_id))
