"""Exercise real website form submissions with JWT-authenticated room listeners."""

import unittest
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import CustomList, ListCategory, ListItem, User
from project.sockets import socketio


class WebsiteListRealtimeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "JWT_SECRET_KEY": "test-jwt-secret-should-be-at-least-32",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        })
        self.web = self.app.test_client()
        self.sockets = []
        with self.app.app_context():
            db.create_all()
            owner = User(email="owner@example.com", username="owner", email_verified=True)
            member = User(email="member@example.com", username="member", email_verified=True)
            outsider = User(email="outside@example.com", username="outside", email_verified=True)
            groceries = CustomList(title="Groceries", owner=owner)
            groceries.shared_with.append(member)
            category = ListCategory(name="Produce", custom_list=groceries, ordering=1)
            other = CustomList(title="Other list", owner=outsider)
            db.session.add_all((owner, member, outsider, groceries, category, other))
            db.session.commit()
            self.owner_id, self.member_id, self.outsider_id = owner.id, member.id, outsider.id
            self.list_id, self.category_id, self.other_id = groceries.id, category.id, other.id
            self.mobile_token = create_access_token(identity=str(member.id))
            outsider_token = create_access_token(identity=str(outsider.id))
        self.mobile = self._listen(self.mobile_token, self.list_id)
        self.other = self._listen(outsider_token, self.other_id)
        self._login(self.owner_id)

    def tearDown(self):
        for client in self.sockets:
            if client.is_connected():
                client.disconnect()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _listen(self, token, list_id):
        client = socketio.test_client(self.app, auth={"token": token})
        self.sockets.append(client)
        self.assertTrue(client.emit("join_list", {"list_id": list_id}, callback=True)["success"])
        client.get_received()
        return client

    def _login(self, user_id):
        with self.web.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def _post(self, path, data):
        response = self.web.post(path, data=data, base_url="https://localhost")
        self.assertEqual(response.status_code, 302)

    def _event(self, name):
        events = self.mobile.get_received()
        self.assertEqual([event["name"] for event in events], [name])
        self.assertEqual(self.other.get_received(), [], "Other list rooms must not receive the event")
        return events[0]["args"][0]

    def _detail(self):
        response = self.web.get(
            f"/api/v1/lists/{self.list_id}",
            base_url="https://localhost",
            headers={"Authorization": f"Bearer {self.mobile_token}"},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["list"]

    def test_website_item_form_broadcasts_saved_payload_for_owner_and_shared_member(self):
        for user_id, username in ((self.owner_id, "owner"), (self.member_id, "member")):
            with self.subTest(username=username):
                self._login(user_id)
                self._post(f"/lists/{self.list_id}/add_item", {
                    "name": "Apples", "quantity": "6", "notes": "For lunches",
                    "category_id": str(self.category_id),
                })
                event = self._event("item_added")
                saved_item = self._detail()["categories"][0]["items"][-1]
                self.assertEqual(event, {
                    "list_id": self.list_id, "category_id": self.category_id,
                    "item": saved_item, "added_by": username,
                })
                self.assertEqual(saved_item["name"], "Apples")
                self.assertFalse(saved_item["completed"])

    def test_website_category_form_broadcasts_saved_payload(self):
        self._post(f"/lists/{self.list_id}", {"name": "Pantry"})
        event = self._event("category_added")
        self.assertEqual(event, {
            "list_id": self.list_id, "category": self._detail()["categories"][-1],
            "added_by": "owner",
        })
        self.assertEqual(event["category"]["items"], [])

    def test_rejected_forms_neither_persist_nor_broadcast(self):
        self._post(f"/lists/{self.list_id}/add_item", {
            "name": "", "category_id": str(self.category_id),
        })
        self._post(f"/lists/{self.list_id}/add_item", {"name": "Invalid", "category_id": "bad"})
        self._login(self.outsider_id)
        self._post(f"/lists/{self.list_id}/add_item", {
            "name": "Unauthorized", "category_id": str(self.category_id),
        })
        self._post(f"/lists/{self.list_id}", {"name": "Unauthorized"})
        self.assertEqual(self.mobile.get_received(), [])
        self.assertEqual(self.other.get_received(), [])
        with self.app.app_context():
            self.assertEqual(ListItem.query.count(), 0)
            self.assertEqual(ListCategory.query.count(), 1)

    def test_broadcast_failure_does_not_report_a_successful_save_as_failed(self):
        with patch("project.lists.views.broadcast_to_list", side_effect=RuntimeError("offline")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                self._post(f"/lists/{self.list_id}/add_item", {
                    "name": "Saved", "category_id": str(self.category_id),
                })
        with self.web.session_transaction() as session:
            self.assertIn(("success", "Item added successfully."), session["_flashes"])
            self.assertNotIn(("danger", "Error adding item."), session["_flashes"])
        self.assertEqual(len(self._detail()["categories"][0]["items"]), 1)
