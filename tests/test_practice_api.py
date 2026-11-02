"""The JWT practice API: explicit response fields, replay, conflicts, limits, and ownership."""
import json
import unittest
from uuid import uuid4

from flask import g
from flask_jwt_extended import create_access_token
from sqlalchemy import event

from project import create_app
from project.database import db
from project.models import ArtifactRevision, PracticeSession, User
from tests.test_practice_service import EXERCISE, SENTINELS, enable_sqlite_foreign_keys, seed_catalog
from tests.test_practice_web import FormFields, as_browser

BASE = "/api/v1/learning/practice"
SESSION_KEYS = {"id", "exercise_id", "exercise_version", "exercise_title", "concept_id", "interaction_style",
                "status", "created_at", "updated_at"}
ARTIFACT_KEYS = {"artifact_id", "title", "format", "instructions", "languages", "revision", "language", "body",
                 "saved_at"}
MESSAGE_KEYS = {"sequence", "role", "kind", "body", "created_at", "artifact_revisions", "brief_revision", "hint"}
SESSION_BRIEF_KEYS = {"revision", "entries", "saved_at"}
ENTRY_KEYS = {"id", "type", "basis", "text", "pinned", "sources"}
BRIEF_KEYS = {"scenario", "learning_objectives", "functional_requirements", "nonfunctional_requirements",
              "prerequisite_concept_ids", "expected_artifacts", "assessment_dimensions"}


class PracticeApiCase(unittest.TestCase):
    """Shared fixtures for the practice API suites; no tests of its own."""

    def setUp(self):
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI="sqlite://",
            JWT_SECRET_KEY="fixture-jwt-secret-at-least-32-characters", WTF_CSRF_ENABLED=True,
            LEARNING_PRACTICE_ENABLED=True))
        self.context = self.app.app_context()
        self.context.push()
        event.listen(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()
        db.create_all()
        db.session.add_all([User(id=i, username=f"fixture{i}", email=f"fixture{i}@example.test") for i in (1, 2)])
        db.session.commit()
        seed_catalog(self)
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        event.remove(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()
        self.context.pop()

    def call(self, method, path, payload=None, *, user_id=1, raw=None):
        headers = {"Authorization": "Bearer " + create_access_token(identity=str(user_id))} if user_id else {}
        kwargs = {"data": raw, "content_type": "application/json"} if raw is not None else {"json": payload}
        return self.client.open(BASE + path, method=method, headers=headers, base_url="https://localhost", **kwargs)

    def start(self, user_id=1, request_id=None):
        response = self.call("POST", "/sessions", {"exercise_id": EXERCISE, "concept_id": "idempotency",
                                                   "request_id": request_id or str(uuid4())}, user_id=user_id)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["session_id"]

    def put(self, session_id, body, *, base=0, request_id=None, user_id=1, language="text", artifact_id="api"):
        return self.call("PUT", f"/sessions/{session_id}/artifacts/{artifact_id}", {
            "request_id": request_id or str(uuid4()), "base_revision": base, "language": language, "body": body,
        }, user_id=user_id)


class PracticeApiTests(PracticeApiCase):
    def test_authentication_and_the_feature_flag_are_required(self):
        self.assertEqual(self.call("GET", "/sessions", user_id=None).status_code, 401)
        self.app.config["LEARNING_PRACTICE_ENABLED"] = False
        response = self.call("GET", "/sessions")
        self.assertEqual((response.status_code, response.get_json()["error"]), (404, "Not found."))

    def test_responses_use_explicit_fields_and_never_private_content(self):
        request_id = str(uuid4())
        session_id = self.start(request_id=request_id)
        replay = self.call("POST", "/sessions", {"exercise_id": EXERCISE, "concept_id": "idempotency",
                                                 "request_id": request_id})
        self.assertEqual((replay.status_code, replay.get_json()["session_id"]), (201, session_id))
        self.assertEqual(PracticeSession.query.count(), 1)
        detail = self.call("GET", f"/sessions/{session_id}")
        self.assertEqual(detail.headers["Cache-Control"], "private, no-store")
        body = detail.get_json()
        self.assertEqual(set(body), {"session", "brief", "session_brief", "artifacts", "messages", "reply", "ai_budget",
                                     "revealed_requirements", "context_choices", "learner_turns", "check_in_due", "submissions"})
        self.assertEqual(body["reply"], {"id": None, "status": "none", "error": None, "turn_sequence": None,
                                         "answered": False, "can_request": False, "can_continue_recent": False,
                                         "unavailable": "disabled", "too_large_part": None})
        self.assertEqual((body["revealed_requirements"], body["context_choices"], body["learner_turns"],
                          body["check_in_due"]), ([], [], 0, False))
        self.assertIsNone(body["ai_budget"])
        self.assertEqual(set(body["session"]), SESSION_KEYS)
        self.assertEqual(set(body["brief"]), BRIEF_KEYS)
        self.assertEqual(set(body["session_brief"]), SESSION_BRIEF_KEYS)
        self.assertTrue(all(set(artifact) == ARTIFACT_KEYS for artifact in body["artifacts"]))
        self.assertEqual([set(message) for message in body["messages"]], [MESSAGE_KEYS])
        self.assertEqual(set(self.call("GET", "/sessions").get_json()["sessions"][0]), SESSION_KEYS)
        for secret in SENTINELS:
            self.assertNotIn(secret, detail.get_data(as_text=True))

    def test_save_replay_unchanged_conflict_and_receipt_recovery(self):
        session_id = self.start()
        request_id = str(uuid4())
        first = self.put(session_id, "POST /orders", request_id=request_id)
        self.assertEqual(first.get_json(), {"session_id": session_id, "status": "active",
                                            "artifacts": {"api": {"revision": 1, "changed": True}}})
        replay = self.put(session_id, "POST /orders", request_id=request_id)
        self.assertEqual((replay.status_code, replay.get_json()), (200, first.get_json()))
        unchanged = self.put(session_id, "POST /orders", base=1)
        self.assertEqual(unchanged.get_json()["artifacts"]["api"], {"revision": 1, "changed": False})
        stale = self.put(session_id, "a different design", base=0)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["code"], "stale_artifact")
        self.assertEqual(stale.get_json()["conflicts"][0]["body"], "POST /orders")
        reused = self.put(session_id, "changed payload", request_id=request_id)
        self.assertEqual((reused.status_code, reused.get_json()["code"]), (409, "request_conflict"))
        receipt = self.call("GET", f"/receipts/{request_id}").get_json()["receipt"]
        self.assertEqual(receipt, {"operation": "save", "response": first.get_json()})
        self.assertIsNone(self.call("GET", f"/receipts/{request_id}", user_id=2).get_json()["receipt"])
        self.assertEqual(self.call("GET", "/receipts/not-a-uuid").status_code, 400)
        history = self.call("GET", f"/sessions/{session_id}/artifacts/api/revisions").get_json()
        self.assertEqual([entry["revision"] for entry in history["revisions"]], [1])
        revision = self.call("GET", f"/sessions/{session_id}/artifacts/api/revisions/1").get_json()
        self.assertEqual((revision["revision"]["body"], revision["current_revision"]), ("POST /orders", 1))
        self.assertEqual(ArtifactRevision.query.count(), 1)

    def test_invalid_requests_are_rejected_with_reasons(self):
        session_id = self.start()
        cases = [
            ({"request_id": str(uuid4()), "base_revision": 0, "language": "text"}, 400, "invalid_request"),
            ({"request_id": str(uuid4()), "base_revision": 0, "language": "text", "body": "x", "extra": 1}, 400,
             "invalid_request"),
            ({"request_id": "nope", "base_revision": 0, "language": "text", "body": "x"}, 400, "invalid_request"),
            ({"request_id": str(uuid4()), "base_revision": "0", "language": "text", "body": "x"}, 400,
             "invalid_request"),
        ]
        for payload, status, code in cases:
            with self.subTest(payload=payload):
                response = self.call("PUT", f"/sessions/{session_id}/artifacts/api", payload)
                self.assertEqual((response.status_code, response.get_json()["code"]), (status, code))
        wrong_notation = self.put(session_id, "x", artifact_id="schema", language="json")
        self.assertEqual(wrong_notation.get_json()["field"], "schema")
        self.assertEqual(self.call("PUT", f"/sessions/{session_id}/artifacts/api", raw="[]").status_code, 400)
        self.assertEqual(self.put(session_id, "x" * (64 * 1024 + 1)).status_code, 400)
        huge = json.dumps({"request_id": str(uuid4()), "base_revision": 0, "language": "text",
                           "body": "x" * (2 * 1024 * 1024)})
        too_large = self.call("PUT", f"/sessions/{session_id}/artifacts/api", raw=huge)
        self.assertEqual((too_large.status_code, too_large.get_json()["code"]), (413, "too_large"))
        self.assertEqual(self.put(session_id, "x", artifact_id="unknown").status_code, 400)
        self.assertEqual(ArtifactRevision.query.count(), 0)

    def test_other_accounts_get_not_found(self):
        session_id = self.start()
        self.put(session_id, "private design")
        for method, path in (("GET", f"/sessions/{session_id}"), ("GET", f"/sessions/{session_id}/artifacts/api/revisions"),
                             ("GET", f"/sessions/{session_id}/artifacts/api/revisions/1"), ("GET", f"/sessions/{uuid4()}")):
            with self.subTest(path=path):
                self.assertEqual(self.call(method, path, user_id=2).status_code, 404)
        self.assertEqual(self.put(session_id, "intrusion", base=1, user_id=2).status_code, 404)
        self.assertEqual(self.call("GET", "/sessions", user_id=2).get_json(), {"sessions": []})
        self.assertEqual(ArtifactRevision.query.count(), 1)

    def test_the_website_and_api_behave_as_two_devices(self):
        session_id = self.start()
        web = self.app.test_client()
        with web.session_transaction() as session:
            session["_user_id"], session["_fresh"] = "1", True
        g.pop("_login_user", None)
        page = web.get(f"/learning/practice/{session_id}", base_url="https://localhost")
        fields = FormFields(page.get_data(as_text=True)).values
        self.assertEqual(self.put(session_id, "saved from the API").status_code, 200)
        fields["artifacts-0-body"] = "edited in the browser"
        conflict = web.post(f"/learning/practice/{session_id}", data=as_browser(fields), base_url="https://localhost")
        self.assertEqual(conflict.status_code, 409)
        self.assertIn("saved from the API</pre>", conflict.get_data(as_text=True))
        rerendered = FormFields(conflict.get_data(as_text=True)).values
        saved = web.post(f"/learning/practice/{session_id}", data=as_browser(rerendered), base_url="https://localhost")
        self.assertEqual(saved.status_code, 303)
        artifacts = self.call("GET", f"/sessions/{session_id}").get_json()["artifacts"]
        self.assertEqual((artifacts[0]["revision"], artifacts[0]["body"]), (2, "edited in the browser"))


if __name__ == "__main__":
    unittest.main()
