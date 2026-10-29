"""The JWT API's reply endpoints: 202 for a queued reply, polling, asking again, and 409 while a reply is live."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from project.database import db
from project.models import AIRequest, PracticeReceipt, User
from project.services import practice_worker
from project.services.practice_worker import FakeProvider
from tests.test_practice_api import MESSAGE_KEYS, PracticeApiCase

AI_CONFIG = dict(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="fixture1@example.test")
CURRENT = {"api": 0, "schema": 0, "algorithm": 0}
REPLY_KEYS = {"id", "status", "error", "turn_sequence", "answered", "can_request", "unavailable"}


class PracticeApiReplyTests(PracticeApiCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(AI_CONFIG)
        db.session.get(User, 1).email_verified = True
        db.session.commit()

    def turn(self, session_id, *, expected=1, user_id=1):
        return self.call("POST", f"/sessions/{session_id}/turns", {
            "request_id": str(uuid4()), "body": "Do keys expire?", "expected_sequence": expected,
            "artifact_revisions": CURRENT, "brief_revision": 0}, user_id=user_id)

    def ask(self, session_id, request_id=None, user_id=1):
        return self.call("POST", f"/sessions/{session_id}/reply", {"request_id": request_id or str(uuid4())},
                         user_id=user_id)

    def work(self, provider=None):
        return practice_worker.run_once(provider or FakeProvider())

    def test_a_turn_queues_a_reply_that_can_be_polled(self):
        session_id = self.start()
        sent = self.turn(session_id)
        self.assertEqual((sent.status_code, sent.get_json()["reply"]["status"], sent.get_json()["latest_sequence"]),
                         (202, "pending", 2))
        busy = self.turn(session_id, expected=2)
        self.assertEqual((busy.status_code, busy.get_json()["code"]), (409, "reply_pending"))
        polled = self.call("GET", f"/sessions/{session_id}/reply?after=2")
        self.assertEqual((polled.headers["Cache-Control"], polled.get_json()["turns"]), ("private, no-store", []))
        self.assertEqual(set(polled.get_json()["reply"]), REPLY_KEYS)
        self.assertTrue(self.work())
        polled = self.call("GET", f"/sessions/{session_id}/reply?after=2").get_json()
        self.assertEqual([(turn["role"], set(turn)) for turn in polled["turns"]], [("interviewer", MESSAGE_KEYS)])
        self.assertEqual((polled["reply"]["status"], polled["latest_sequence"]), ("completed", 3))
        detail = self.call("GET", f"/sessions/{session_id}").get_json()
        self.assertEqual((detail["messages"][-1]["role"], detail["reply"]["answered"]), ("interviewer", True))
        self.assertEqual(self.call("GET", f"/sessions/{session_id}/reply", user_id=2).status_code, 404)

    def test_asking_for_a_reply_again(self):
        session_id = self.start()
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):
            sent = self.turn(session_id)
        self.assertEqual((sent.status_code, sent.get_json()["reply"]),
                         (201, {"id": None, "status": "unavailable", "reason": "disabled"}))
        request_id = str(uuid4())
        asked = self.ask(session_id, request_id)
        self.assertEqual((asked.status_code, asked.get_json()["reply"]["status"]), (202, "pending"))
        replayed = self.ask(session_id, request_id)
        self.assertEqual((replayed.status_code, replayed.get_json()), (202, asked.get_json()))
        busy = self.ask(session_id)
        self.assertEqual((busy.status_code, busy.get_json()["code"]), (409, "reply_pending"))
        with self.assertLogs("project", "WARNING"):
            self.work(FakeProvider("fail"))
        self.assertEqual(self.ask(session_id).status_code, 202)
        self.assertTrue(self.work())
        answered = self.ask(session_id)  # it already has a reply: nothing to queue
        self.assertEqual((answered.status_code, answered.get_json()["reply"]["status"]), (200, "answered"))
        self.assertEqual(self.ask(session_id, user_id=2).status_code, 404)
        extra = self.call("POST", f"/sessions/{session_id}/reply", {"request_id": str(uuid4()), "context": "recent"})
        self.assertEqual(extra.status_code, 400)
        self.assertEqual(AIRequest.query.filter_by(status="completed").count(), 1)

    def test_polling_needs_a_whole_number_and_old_receipts_still_replay(self):
        session_id = self.start()
        for after in ("abc", "", "1.5", "-1", "2147483648"):
            with self.subTest(after=after):
                response = self.call("GET", f"/sessions/{session_id}/reply?after={after}")
                self.assertEqual((response.status_code, response.get_json()["code"]), (400, "invalid_request"))
        self.assertEqual(self.call("GET", f"/sessions/{session_id}/reply").status_code, 200)  # absent means 0
        payload = {"request_id": str(uuid4()), "body": "Do keys expire?", "expected_sequence": 1,
                   "artifact_revisions": CURRENT, "brief_revision": 0}
        self.assertEqual(self.call("POST", f"/sessions/{session_id}/turns", payload).status_code, 202)
        receipt = PracticeReceipt.query.filter_by(request_id=payload["request_id"]).one()
        # A send recorded before replies existed (checkpoint 3b) has no "reply" or "latest_sequence".
        receipt.response = {key: value for key, value in receipt.response.items()
                            if key not in ("reply", "latest_sequence")}
        db.session.commit()
        replayed = self.call("POST", f"/sessions/{session_id}/turns", payload)
        self.assertEqual((replayed.status_code, "reply" in replayed.get_json()), (201, False))


if __name__ == "__main__":
    unittest.main()
