"""The JWT practice API's brief, turns, pause/resume, and delete endpoints."""
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from project.models import ArtifactRevision, PracticeReceipt, PracticeSession, SessionMessage
from project.services import practice_service
from tests.test_practice_api import ENTRY_KEYS, MESSAGE_KEYS, PracticeApiCase
from tests.test_practice_service import SENTINELS

ENTRY = {"id": "e1", "type": "decision", "text": "Scope keys per account", "pinned": True}
CURRENT = {"api": 0, "schema": 0, "algorithm": 0}


class PracticeApiDiscussionTests(PracticeApiCase):
    def put_brief(self, session_id, entries, *, base=0, request_id=None, user_id=1):
        return self.call("PUT", f"/sessions/{session_id}/brief", {
            "request_id": request_id or str(uuid4()), "base_revision": base, "entries": entries}, user_id=user_id)

    def turn(self, session_id, revisions, *, expected=1, brief_revision=0, body="A question", request_id=None,
             user_id=1):
        return self.call("POST", f"/sessions/{session_id}/turns", {
            "request_id": request_id or str(uuid4()), "body": body, "expected_sequence": expected,
            "artifact_revisions": revisions, "brief_revision": brief_revision}, user_id=user_id)

    def test_the_brief_saves_replays_and_reports_conflicts(self):
        session_id = self.start()
        request_id = str(uuid4())
        first = self.put_brief(session_id, [ENTRY], request_id=request_id)
        self.assertEqual((first.status_code, first.get_json()), (200, {
            "session_id": session_id, "brief": {"revision": 1, "changed": True}, "status": "active"}))
        self.assertEqual(self.put_brief(session_id, [ENTRY], request_id=request_id).get_json(), first.get_json())
        self.assertFalse(self.put_brief(session_id, [ENTRY], base=1).get_json()["brief"]["changed"])
        stale = self.put_brief(session_id, [dict(ENTRY, text="Scope keys per device")], base=0)
        self.assertEqual((stale.status_code, stale.get_json()["code"]), (409, "stale_brief"))
        self.assertEqual(stale.get_json()["brief"]["entries"][0]["text"], "Scope keys per account")
        detail = self.call("GET", f"/sessions/{session_id}")
        entries = detail.get_json()["session_brief"]["entries"]
        self.assertEqual([set(entry) for entry in entries], [ENTRY_KEYS])
        self.assertEqual(entries[0], dict(ENTRY, basis="learner", sources=[]))
        for secret in SENTINELS:
            self.assertNotIn(secret, detail.get_data(as_text=True))
        for payload, field in (({"request_id": str(uuid4()), "base_revision": 1}, None),
                               ({"request_id": str(uuid4()), "base_revision": 1, "entries": [], "extra": 1}, None),
                               ({"request_id": str(uuid4()), "base_revision": 1,
                                 "entries": [dict(ENTRY, type="requirement")]}, "e1")):
            with self.subTest(payload=payload):
                response = self.call("PUT", f"/sessions/{session_id}/brief", payload)
                self.assertEqual((response.status_code, response.get_json()["code"]), (400, "invalid_request"))
                self.assertEqual(response.get_json().get("field"), field)
        self.assertEqual(SessionMessage.query.filter_by(kind="brief").count(), 1)

    def test_turns_cite_saved_revisions_and_name_each_stale_part(self):
        session_id = self.start()
        self.put(session_id, "v1")
        request_id = str(uuid4())
        sent = self.turn(session_id, dict(CURRENT, api=1), request_id=request_id)
        self.assertEqual((sent.status_code, sent.get_json()), (201, {
            "session_id": session_id, "sequence": 2, "artifact_revisions": [{"artifact_id": "api", "revision": 1}],
            "brief_revision": 0, "status": "active", "latest_sequence": 2,
            "reply": {"id": None, "status": "unavailable", "reason": "disabled"}}))
        self.assertEqual(self.turn(session_id, dict(CURRENT, api=1), request_id=request_id).get_json(), sent.get_json())
        self.put(session_id, "v2", base=1)
        stale = self.turn(session_id, dict(CURRENT, api=1), expected=2)
        self.assertEqual((stale.status_code, stale.get_json()["code"]), (409, "stale_artifact"))
        self.assertEqual(stale.get_json()["conflicts"][0]["body"], "v2")
        self.put_brief(session_id, [ENTRY])
        stale = self.turn(session_id, dict(CURRENT, api=2), expected=2)
        self.assertEqual((stale.get_json()["code"], stale.get_json()["brief"]["revision"]), ("stale_brief", 1))
        stale = self.turn(session_id, dict(CURRENT, api=2), expected=1, brief_revision=1)
        self.assertEqual((stale.get_json()["code"], stale.get_json()["latest_sequence"]), ("stale_transcript", 2))
        missing = self.turn(session_id, {"api": 2}, expected=2, brief_revision=1)
        self.assertEqual((missing.status_code, missing.get_json()["part"]), (400, "turn"))
        extra = self.call("POST", f"/sessions/{session_id}/turns", {"request_id": str(uuid4()), "body": "x"})
        self.assertEqual(extra.status_code, 400)
        messages = self.call("GET", f"/sessions/{session_id}").get_json()["messages"]
        self.assertEqual([set(message) for message in messages], [MESSAGE_KEYS, MESSAGE_KEYS])
        self.assertEqual((messages[1]["body"], messages[1]["artifact_revisions"], messages[1]["brief_revision"]),
                         ("A question", [{"artifact_id": "api", "revision": 1}], 0))

    def test_pause_resume_and_delete(self):
        session_id = self.start()
        self.put(session_id, "work")
        request_id = str(uuid4())
        paused = self.call("POST", f"/sessions/{session_id}/pause", {"request_id": request_id})
        self.assertEqual((paused.status_code, paused.get_json()),
                         (200, {"session_id": session_id, "status": "paused", "changed": True}))
        self.assertEqual(self.call("POST", f"/sessions/{session_id}/pause", {"request_id": request_id}).get_json(),
                         paused.get_json())
        self.assertEqual(self.call("GET", "/sessions").get_json()["sessions"][0]["status"], "paused")
        resumed = self.call("POST", f"/sessions/{session_id}/resume", {"request_id": str(uuid4())})
        self.assertEqual(resumed.get_json()["status"], "active")
        for payload in ({}, {"request_id": str(uuid4()), "status": "paused"}):
            self.assertEqual(self.call("POST", f"/sessions/{session_id}/pause", payload).status_code, 400)
        self.assertEqual(self.call("DELETE", f"/sessions/{session_id}", user_id=2).status_code, 404)
        deleted = self.call("DELETE", f"/sessions/{session_id}")
        self.assertEqual((deleted.status_code, deleted.get_data(), deleted.headers["Cache-Control"]),
                         (204, b"", "private, no-store"))
        repeated = self.call("DELETE", f"/sessions/{session_id}")
        self.assertEqual((repeated.status_code, repeated.get_json()["code"]), (404, "not_found"))
        self.assertEqual(self.call("GET", f"/sessions/{session_id}").status_code, 404)
        self.assertIsNone(self.call("GET", f"/receipts/{request_id}").get_json()["receipt"])
        for model in (PracticeSession, ArtifactRevision, SessionMessage, PracticeReceipt):
            self.assertEqual(model.query.count(), 0, model.__tablename__)

    def test_unavailable_responses_say_how_to_retry(self):
        session_id = self.start()
        lost = OperationalError("SELECT", {}, sqlite3.OperationalError("fixture: database unavailable"))
        cases = (("get", "session_detail", lambda: self.call("GET", f"/sessions/{session_id}"), "Try again."),
                 ("put", "save_work", lambda: self.put_brief(session_id, [ENTRY]), "same request_id"),
                 ("delete", "delete_session", lambda: self.call("DELETE", f"/sessions/{session_id}"), "a 404 then"))
        for method, operation, call, advice in cases:
            with self.subTest(method=method):
                with patch.object(practice_service, operation, side_effect=lost), self.assertLogs("project", "ERROR"):
                    response = call()
                self.assertEqual((response.status_code, response.get_json()["code"]), (503, "unavailable"))
                self.assertIn(advice, response.get_json()["error"])
                if method != "put":  # only POST and PUT carry a request_id
                    self.assertNotIn("request_id", response.get_json()["error"])

    def test_other_accounts_get_not_found(self):
        session_id = self.start()
        for response in (self.put_brief(session_id, [ENTRY], user_id=2),
                         self.turn(session_id, CURRENT, user_id=2),
                         self.call("POST", f"/sessions/{session_id}/pause", {"request_id": str(uuid4())}, user_id=2),
                         self.call("POST", f"/sessions/{session_id}/resume", {"request_id": str(uuid4())}, user_id=2),
                         self.call("DELETE", f"/sessions/{session_id}", user_id=2)):
            self.assertEqual((response.status_code, response.get_json()["code"]), (404, "not_found"))
        self.assertEqual((SessionMessage.query.count(), PracticeSession.query.one().status), (1, "active"))


if __name__ == "__main__":
    unittest.main()
