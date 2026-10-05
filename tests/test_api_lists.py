import unittest
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import CustomList, ListCategory, ListInvitation, ListItem, User, list_shares
from project.services import lists_service
from project.sockets import socketio


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

    def _editing_item(self):
        with self.app.app_context():
            # Enforce actual FK behavior so deletion tests catch orphan/null-FK bugs.
            db.session.execute(db.text("PRAGMA foreign_keys=ON"))
            item = ListItem(name="Apples", quantity="2", notes="Keep chilled", category_id=self.category_id, completed=True, ordering=1)
            db.session.add(item)
            db.session.commit()
            return item.id

    def _edit_request(self, method, path, *, user_id=None, payload=None):
        return self.client.open(
            f"/api/v1/lists/{self.list_id}{path}", method=method,
            json=payload, base_url="https://localhost", headers=self._auth_headers(user_id),
        )

    def test_editing_moves_item_and_preserves_completion_and_siblings(self):
        item_id = self._editing_item()
        with self.app.app_context():
            destination = ListCategory(name="Pantry", custom_list_id=self.list_id, ordering=2)
            sibling = ListItem(name="Pears", category=destination, ordering=4)
            db.session.add_all((destination, sibling))
            db.session.commit()
            destination_id = destination.id
        response = self._edit_request("PATCH", f"/items/{item_id}", user_id=self.shared_id, payload={
            "name": "Green apples", "quantity": "6", "notes": "", "category_id": destination_id,
        })
        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        self.assertEqual((item["name"], item["quantity"], item["notes"], item["completed"], item["ordering"], item["category_id"]),
                         ("Green apples", "6", None, True, 5, destination_id))
        with self.app.app_context():
            self.assertEqual(ListItem.query.filter_by(name="Pears").count(), 1)
        response = self._edit_request("PATCH", f"/items/{item_id}", payload={"quantity": None})
        self.assertEqual(response.get_json()["item"]["name"], "Green apples")
        self.assertIsNone(response.get_json()["item"]["quantity"])

    def test_shared_member_can_rename_category_and_delete_single_duplicate(self):
        item_id = self._editing_item()
        other_duplicate = self._editing_item()
        response = self._edit_request("PATCH", f"/categories/{self.category_id}", user_id=self.shared_id, payload={"name": "Fresh produce"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["category"]["name"], "Fresh produce")
        self.assertEqual(self._edit_request("DELETE", f"/items/{item_id}", user_id=self.shared_id).status_code, 204)
        self.assertEqual(self._edit_request("DELETE", f"/items/{item_id}").status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(ListItem, other_duplicate))
            self.assertIsNotNone(db.session.get(ListItem, self.other_item_id))

    def test_delete_category_removes_its_items_but_preserves_other_categories_and_list(self):
        item_id = self._editing_item()
        self.assertEqual(self._edit_request("DELETE", f"/categories/{self.category_id}", user_id=self.shared_id).status_code, 204)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ListItem, item_id))
            self.assertIsNone(db.session.get(ListCategory, self.category_id))
            self.assertIsNotNone(db.session.get(CustomList, self.list_id))
            self.assertIsNotNone(db.session.get(ListCategory, self.other_category_id))

    def test_owner_can_rename_and_delete_entire_shared_list_with_invitations(self):
        item_id = self._editing_item()
        with self.app.app_context():
            db.session.add(ListInvitation.create_invitation(email="invited@example.com", list_id=self.list_id))
            db.session.commit()
        response = self._edit_request("PATCH", "", payload={"title": "New title"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["list"]["title"], "New title")
        self.assertEqual(self._edit_request("DELETE", "").status_code, 204)
        with self.app.app_context():
            self.assertIsNone(db.session.get(CustomList, self.list_id))
            self.assertIsNone(db.session.get(ListCategory, self.category_id))
            self.assertIsNone(db.session.get(ListItem, item_id))
            self.assertEqual(ListInvitation.query.filter_by(list_id=self.list_id).count(), 0)
            self.assertEqual(db.session.execute(db.select(list_shares).where(list_shares.c.list_id == self.list_id)).all(), [])
            self.assertIsNotNone(db.session.get(ListItem, self.other_item_id))

    def test_edit_delete_permissions_and_cross_list_ids(self):
        item_id = self._editing_item()
        paths = [("", {"title": "Forbidden"}), (f"/categories/{self.category_id}", {"name": "Forbidden"}), (f"/items/{item_id}", {"name": "Forbidden"})]
        for method in ("PATCH", "DELETE"):
            for path, payload in paths:
                with self.subTest(method=method, path=path):
                    self.assertEqual(self._edit_request(method, path, user_id=self.stranger_id, payload=payload).status_code, 403)
                    response = self.client.open(f"/api/v1/lists/{self.list_id}{path}", method=method, json=payload, base_url="https://localhost")
                    self.assertEqual(response.status_code, 401)
            self.assertEqual(self._edit_request(method, "", user_id=self.shared_id, payload={"title": "Forbidden"}).status_code, 403)
            self.assertEqual(self._edit_request(method, f"/items/{self.other_item_id}", payload={"name": "Forbidden"}).status_code, 404)
            self.assertEqual(self._edit_request(method, f"/categories/{self.other_category_id}", payload={"name": "Forbidden"}).status_code, 404)
        response = self._edit_request("PATCH", f"/items/{item_id}", payload={"name": "Must not save", "category_id": self.other_category_id})
        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertEqual(db.session.get(ListItem, item_id).name, "Apples")
            custom_list = db.session.get(CustomList, self.list_id)
            custom_list.shared_with.remove(db.session.get(User, self.shared_id))
            db.session.commit()
        self.assertEqual(self._edit_request("DELETE", f"/items/{item_id}", user_id=self.shared_id).status_code, 403)

    def test_invalid_edit_payloads_leave_saved_state_unchanged(self):
        item_id = self._editing_item()
        for payload in ([], "wrong", {}, {"name": " "}, {"name": 3}, {"quantity": "x" * 33}, {"name": "x" * 129}, {"notes": []}, {"category_id": True}, {"completed": False}):
            with self.subTest(payload=payload):
                self.assertEqual(self._edit_request("PATCH", f"/items/{item_id}", payload=payload).status_code, 400)
        for path, payload in (("", {"title": " "}), ("", {"title": "x" * 129}), (f"/categories/{self.category_id}", {"name": "x" * 65})):
            self.assertEqual(self._edit_request("PATCH", path, payload=payload).status_code, 400)
        with self.app.app_context():
            item = db.session.get(ListItem, item_id)
            self.assertEqual((item.name, item.quantity, item.completed), ("Apples", "2", True))

    def test_edit_validation_returns_specific_safe_messages(self):
        item_id = self._editing_item()
        category_path = f"/categories/{self.category_id}"
        item_path = f"/items/{item_id}"
        cases = (
            ("", [], "A JSON object is required."),
            (category_path, "wrong", "A JSON object is required."),
            (item_path, [], "A JSON object is required."),
            ("", {"title": 3}, "Title must be text."),
            ("", {"title": " "}, "Title is required."),
            ("", {"title": "x" * 129}, "Title must be 128 characters or fewer."),
            (category_path, {"name": []}, "Category name must be text."),
            (category_path, {"name": " "}, "Category name is required."),
            (category_path, {"name": "x" * 65}, "Category name must be 64 characters or fewer."),
            (item_path, {}, "Supply item name, quantity, notes, or category_id."),
            (item_path, {"completed": False}, "Supply item name, quantity, notes, or category_id."),
            (item_path, {"name": 3}, "Item name must be text."),
            (item_path, {"name": " "}, "Item name is required."),
            (item_path, {"name": "x" * 129}, "Item name must be 128 characters or fewer."),
            (item_path, {"quantity": []}, "Quantity must be text."),
            (item_path, {"quantity": "x" * 33}, "Quantity must be 32 characters or fewer."),
            (item_path, {"notes": []}, "Notes must be text."),
            (item_path, {"category_id": True}, "Invalid category ID."),
        )
        for path, payload, message in cases:
            with self.subTest(path=path, payload=payload):
                response = self._edit_request("PATCH", path, payload=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": message})

    def test_edit_commit_failures_hide_details_and_roll_back_changes(self):
        item_id = self._editing_item()
        sensitive_detail = "database credentials: should-not-leak"
        cases = (
            ("", {"title": "Must not persist"}),
            (f"/categories/{self.category_id}", {"name": "Must not persist"}),
            (f"/items/{item_id}", {"name": "Must not persist"}),
        )
        for method in ("PATCH", "DELETE"):
            for path, payload in cases:
                with self.subTest(method=method, path=path):
                    with patch("project.services.lists_service.db.session.commit", side_effect=ValueError(sensitive_detail)):
                        with patch("project.api.lists.broadcast_to_list") as broadcast:
                            with self.assertLogs(self.app.logger, level="ERROR") as logs:
                                response = self._edit_request(method, path, payload=payload)
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(response.get_json(), {"error": "Couldn't save this change. Please try again."})
                    self.assertNotIn(sensitive_detail, response.get_data(as_text=True))
                    self.assertIn(sensitive_detail, "\n".join(logs.output))
                    broadcast.assert_not_called()
                    with self.app.app_context():
                        self.assertEqual(db.session.get(CustomList, self.list_id).title, "Groceries")
                        self.assertEqual(db.session.get(ListCategory, self.category_id).name, "Produce")
                        self.assertEqual(db.session.get(ListItem, item_id).name, "Apples")

    def test_edit_validation_codes_cannot_reflect_exception_details(self):
        item_id = self._editing_item()
        sensitive_detail = "storage credentials: should-not-leak"
        cases = (
            ("rename_list", "", {"title": "New title"}, "title_required", "Title is required."),
            ("rename_category", f"/categories/{self.category_id}", {"name": "Fresh"}, "category_name_required", "Category name is required."),
            ("update_item", f"/items/{item_id}", {"name": "Pears"}, "name_required", "Item name is required."),
        )
        for service, path, payload, code, message in cases:
            for actual_code, expected in ((code, message), (sensitive_detail, "Invalid edit request.")):
                with self.subTest(service=service, code=actual_code):
                    error = lists_service.EditValidationError(actual_code)
                    error.args = (sensitive_detail,)
                    with patch(f"project.api.lists.lists_service.{service}", side_effect=error):
                        with patch("project.api.lists.broadcast_to_list") as broadcast:
                            response = self._edit_request("PATCH", path, payload=payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json(), {"error": expected})
                    self.assertNotIn(sensitive_detail, response.get_data(as_text=True))
                    broadcast.assert_not_called()

    def test_edits_and_deletes_broadcast_only_after_persistence_to_the_list_room(self):
        item_id = self._editing_item()
        with self.app.app_context():
            token = create_access_token(identity=str(self.shared_id))
            outsider_token = create_access_token(identity=str(self.stranger_id))
        mobile = socketio.test_client(self.app, auth={"token": token})
        outsider = socketio.test_client(self.app, auth={"token": outsider_token})
        self.addCleanup(lambda: mobile.disconnect() if mobile.is_connected() else None)
        self.addCleanup(lambda: outsider.disconnect() if outsider.is_connected() else None)
        self.assertTrue(mobile.emit("join_list", {"list_id": self.list_id}, callback=True)["success"])
        self.assertFalse(outsider.emit("join_list", {"list_id": self.list_id}, callback=True)["success"])
        mobile.get_received()
        for method, path, payload, event in (
            ("PATCH", f"/items/{item_id}", {"name": "Pears"}, "item_updated"),
            ("PATCH", f"/categories/{self.category_id}", {"name": "Fresh"}, "category_updated"),
            ("PATCH", "", {"title": "Shopping"}, "list_updated"),
            ("DELETE", f"/items/{item_id}", None, "item_deleted"),
            ("DELETE", f"/categories/{self.category_id}", None, "category_deleted"),
            ("DELETE", "", None, "list_deleted"),
        ):
            response = self._edit_request(method, path, payload=payload)
            self.assertIn(response.status_code, (200, 204))
            events = mobile.get_received()
            self.assertEqual([entry["name"] for entry in events], [event])
            self.assertEqual(events[0]["args"][0]["list_id"], self.list_id)
            self.assertEqual(outsider.get_received(), [])
        self.assertEqual(self._edit_request("DELETE", "").status_code, 404)
        self.assertEqual(mobile.get_received(), [])

    def test_edit_transport_failure_does_not_change_rest_success(self):
        item_id = self._editing_item()
        with patch("project.api.lists.broadcast_to_list", side_effect=RuntimeError("offline")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self._edit_request("PATCH", f"/items/{item_id}", payload={"name": "Pears"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["name"], "Pears")


if __name__ == "__main__":
    unittest.main()
