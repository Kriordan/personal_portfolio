import unittest

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import CustomList, ListCategory, ListItem, User


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
            self.category_id = category.id
            shared = User(email="shared@example.com", username="shared", email_verified=True)
            stranger = User(email="stranger@example.com", username="stranger", email_verified=True)
            custom_list.shared_with.append(shared)
            other_list = CustomList(title="Private", owner=user)
            other_category = ListCategory(name="Private", custom_list=other_list, ordering=1)
            other_item = ListItem(name="Private item", category=other_category, ordering=1)
            db.session.add_all((shared, stranger, other_list, other_category, other_item))
            db.session.commit()
            self.shared_id = shared.id
            self.stranger_id = stranger.id
            self.other_category_id = other_category.id
            self.other_item_id = other_item.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _auth_headers(self, user_id=None) -> dict[str, str]:
        with self.app.app_context():
            token = create_access_token(identity=str(user_id or self.user_id))
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

    def test_shared_member_can_read_add_and_toggle(self):
        options = {"base_url": "https://localhost", "headers": self._auth_headers(self.shared_id)}
        overview = self.client.get("/api/v1/lists/", **options).get_json()
        self.assertEqual(overview["owned"], [])
        self.assertEqual([entry["id"] for entry in overview["shared"]], [self.list_id])
        self.assertEqual(self.client.get(f"/api/v1/lists/{self.list_id}", **options).status_code, 200)
        category = self.client.post(f"/api/v1/lists/{self.list_id}/categories", json={"name": "Dairy"}, **options)
        self.assertEqual(category.status_code, 201)
        response = self.client.post(f"/api/v1/lists/{self.list_id}/items", json={"name": "Milk", "category_id": category.get_json()["category"]["id"]}, **options)
        self.assertEqual(response.status_code, 201)
        item_id = response.get_json()["item"]["id"]
        toggled = self.client.post(f"/api/v1/lists/{self.list_id}/items/{item_id}/toggle", **options)
        self.assertEqual(toggled.get_json(), {"completed": True})
        detail = self.client.get(f"/api/v1/lists/{self.list_id}", **options).get_json()["list"]
        items = [item for category in detail["categories"] for item in category["items"]]
        self.assertEqual([(item["name"], item["completed"]) for item in items], [("Milk", True)])

    def test_shared_member_cannot_share_change_settings_or_reference_another_list(self):
        options = {"base_url": "https://localhost", "headers": self._auth_headers(self.shared_id)}
        self.assertEqual(self.client.post(f"/api/v1/lists/{self.list_id}/share", json={"email": "stranger@example.com"}, **options).status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/lists/{self.list_id}/settings", json={"completed_display_mode": "global_section"}, **options).status_code, 403)
        self.assertEqual(self.client.post(f"/api/v1/lists/{self.list_id}/items", json={"name": "Wrong category", "category_id": self.other_category_id}, **options).status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/lists/{self.list_id}/items/{self.other_item_id}/toggle", **options).status_code, 404)

    def test_unshared_and_revoked_members_cannot_read_or_mutate(self):
        with self.app.app_context():
            custom_list = db.session.get(CustomList, self.list_id)
            custom_list.shared_with.remove(db.session.get(User, self.shared_id))
            db.session.commit()
        for user_id in (self.stranger_id, self.shared_id):
            options = {"base_url": "https://localhost", "headers": self._auth_headers(user_id)}
            self.assertEqual(self.client.get(f"/api/v1/lists/{self.list_id}", **options).status_code, 403)
            self.assertEqual(self.client.post(f"/api/v1/lists/{self.list_id}/categories", json={"name": "No access"}, **options).status_code, 403)
            self.assertEqual(self.client.post(f"/api/v1/lists/{self.list_id}/items", json={"name": "No access", "category_id": self.category_id}, **options).status_code, 403)

    def test_owner_display_setting_is_returned_to_shared_member(self):
        for mode in ("inline_bottom", "category_section", "global_section"):
            changed = self.client.patch(f"/api/v1/lists/{self.list_id}/settings", json={"completed_display_mode": mode}, base_url="https://localhost", headers=self._auth_headers())
            self.assertEqual(changed.status_code, 200)
            detail = self.client.get(f"/api/v1/lists/{self.list_id}", base_url="https://localhost", headers=self._auth_headers(self.shared_id)).get_json()["list"]
            self.assertEqual(detail["completed_display_mode"], mode)


if __name__ == "__main__":
    unittest.main()
