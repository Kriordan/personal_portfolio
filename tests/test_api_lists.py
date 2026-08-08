import unittest

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import CustomList, ListCategory, User


class ApiListsSecurityTests(unittest.TestCase):
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
            user = User(
                email="owner@example.com",
                username="owner",
                email_verified=True,
            )
            user.set_password("password123")
            custom_list = CustomList(title="Groceries", owner=user)
            category = ListCategory(
                name="Produce",
                custom_list=custom_list,
                ordering=1,
            )
            db.session.add_all((user, custom_list, category))
            db.session.commit()
            self.user_id = user.id
            self.list_id = custom_list.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _auth_headers(self) -> dict[str, str]:
        with self.app.app_context():
            token = create_access_token(identity=str(self.user_id))
        return {"Authorization": f"Bearer {token}"}

    def test_add_item_does_not_reflect_invalid_category_id(self):
        sensitive_input = "database-password-should-not-leak"

        response = self.client.post(
            f"/api/v1/lists/{self.list_id}/items",
            base_url="https://localhost",
            headers=self._auth_headers(),
            json={
                "name": "Apples",
                "category_id": sensitive_input,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Invalid category ID.")
        self.assertNotIn(sensitive_input, response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
