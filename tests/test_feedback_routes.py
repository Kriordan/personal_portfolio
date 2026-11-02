import json
from unittest.mock import patch
from uuid import uuid4

from flask import g
from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import AIRequest, PracticeFeedback, SessionMessage, User
from project.services import feedback_service as feedback, practice_service as practice, practice_worker
from tests.feedback_fixtures import DISCOVERY, RACE, scripted_feedback
from tests.test_practice_api import PracticeApiCase
from tests.test_practice_web import PracticeWebCase, FormFields
from tests.test_practice_service import SENTINELS
from tests.test_practice_submissions import submission_input


def enable(app):
    app.config.update(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="fixture1@example.test")
    db.session.get(User, 1).email_verified = True
    db.session.commit()


class FeedbackApiTests(PracticeApiCase):
    def fixture(self):
        enable(self.app)
        sid = self.start()
        values = submission_input(self.call("GET", f"/sessions/{sid}").get_json())
        values["edits"][0]["body"] = DISCOVERY + "\n" + RACE
        seq = self.call("POST", f"/sessions/{sid}/submissions", values).get_json()["submission"]["sequence"]
        return sid, f"/sessions/{sid}/submissions/{seq}/feedback"

    def test_queue_poll_receipt_replay_and_learner_safe_results(self):
        sid, path = self.fixture()
        values = {"request_id": str(uuid4())}
        response = self.call("POST", path, values)
        self.assertEqual(response.status_code, 202, response.get_json())
        self.assertEqual(response.get_json(), self.call("POST", path, values).get_json())
        self.assertEqual(response.get_json(), self.call("GET", "/receipts/" + values["request_id"]).get_json()["receipt"]["response"])
        self.assertEqual(self.call("GET", path).get_json()["request"]["status"], "pending")
        practice_worker.run_once(practice_worker.FakeProvider(feedbacks=[scripted_feedback]))
        result = self.call("GET", path)
        self.assertEqual(result.headers["Cache-Control"], "private, no-store")
        self.assertEqual(result.get_json()["feedback"]["findings"][1]["evidence"][0]["quote"], RACE)
        for secret in (*SENTINELS, "reference_reasoning", "rubric", "misconception_ids"):
            self.assertNotIn(secret, result.get_data(as_text=True))
        self.assertEqual(self.call("POST", path, {"request_id": str(uuid4())}).status_code, 200)
        self.assertEqual(AIRequest.query.count(), 1)

    def test_auth_owner_snapshot_and_input_validation(self):
        sid, path = self.fixture()
        values = {"request_id": str(uuid4())}
        for method in ("GET", "POST"):
            self.assertEqual(self.call(method, path, values, user_id=None).status_code, 401)
            self.assertEqual(self.call(method, path, values, user_id=2).status_code, 404)
            self.assertEqual(self.call(method, f"/sessions/{sid}/submissions/1/feedback", values).status_code, 404)
        self.assertEqual(self.call("POST", path, values | {"output": {}}).status_code, 400)
        self.assertEqual(self.call("POST", path, {}).status_code, 400)
        with patch.dict(self.app.config, LEARNING_PRACTICE_ENABLED=False):
            self.assertEqual(self.call("GET", path).status_code, 404)
            self.assertEqual(self.call("POST", path, values).status_code, 404)

    def test_lost_response_replays_and_busy_feedback_has_clear_conflict(self):
        sid, path = self.fixture()
        values = {"request_id": str(uuid4())}
        original = feedback.request_feedback
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError("", {}, Exception("lost"))
        with patch.object(feedback, "request_feedback", side_effect=lost):
            response = self.call("POST", path, values)
        self.assertEqual((response.status_code, response.get_json()["retry_same_request"]), (503, True))
        self.assertEqual(self.call("POST", path, values).status_code, 202)
        data = submission_input(self.call("GET", f"/sessions/{sid}").get_json())
        response = self.call("POST", f"/sessions/{sid}/submissions", data)
        self.assertEqual((response.status_code, response.get_json()["code"]), (409, "feedback_pending"))
        self.assertEqual(AIRequest.query.count(), 1)


class FeedbackWebTests(PracticeWebCase):
    def fixture(self):
        enable(self.app)
        sid = self.start()
        fields = self.fields(sid)
        fields.update(action="submit", **{"artifacts-0-body": DISCOVERY + "\n" + RACE})
        self.assertEqual(self.post(f"/learning/practice/{sid}", fields).status_code, 303)
        seq = SessionMessage.query.filter_by(kind="submission").one().sequence
        return sid, f"/learning/practice/{sid}/submissions/{seq}"

    def test_native_feedback_result_citations_and_escaped_output(self):
        sid, path = self.fixture()
        fields = FormFields(self.get(path).get_data(as_text=True)).values
        response = self.post(path + '/feedback', fields)
        self.assertEqual(response.status_code, 303)
        self.assertIn("Feedback is being prepared", self.get(path).get_data(as_text=True))
        def output(body):
            result = scripted_feedback(body)
            result["summary"] = '<script>alert("injection")</script>'
            return result
        practice_worker.run_once(practice_worker.FakeProvider(feedbacks=[output]))
        page = self.get(path).get_data(as_text=True)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('<script>alert', page)
        self.assertIn(f'/practice/{sid}/artifacts/api/1', page)
        self.assertIn("Concern to review", page)
        self.assertIn("Strength", page)
        self.assertIn("Not observed", page)
        self.assertNotIn('data-feedback-form', page)
        polled = self.get(path + '/feedback')
        self.assertFalse(polled.get_json()["live"])
        self.assertIn("Concern to review", polled.get_json()["html"])
        self.assertEqual(polled.headers["Cache-Control"], "private, no-store")
        for secret in SENTINELS:
            self.assertNotIn(secret, page + json.dumps(polled.get_json()))

    def test_csrf_owner_and_login_boundaries(self):
        sid, path = self.fixture()
        fields = FormFields(self.get(path).get_data(as_text=True)).values
        self.assertEqual(self.post(path + '/feedback', fields | {"csrf_token": "wrong"}).status_code, 400)
        self.login(2)
        other_csrf = FormFields(self.get('/learning/concepts/idempotency/practice').get_data(as_text=True)).values.get('csrf_token')
        self.assertEqual(self.get(path).status_code, 404)
        self.assertEqual(self.get(path + '/feedback').status_code, 404)
        self.assertEqual(self.post(path + '/feedback', fields | {"csrf_token": other_csrf}).status_code, 404)
        with self.client.session_transaction() as session:
            session.clear()
        g.pop('_login_user', None)
        self.assertEqual(self.get(path + '/feedback').status_code, 302)
        self.assertEqual(AIRequest.query.count(), 0)

    def test_ambiguous_commit_uses_standalone_retry_with_same_request_id(self):
        sid, path = self.fixture()
        fields = FormFields(self.get(path).get_data(as_text=True)).values
        original = feedback.request_feedback
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError("", {}, Exception("lost"))
        with patch.object(feedback, "request_feedback", side_effect=lost), \
                patch.object(feedback, "detail", side_effect=AssertionError("read after unknown commit")):
            response = self.post(path + '/feedback', fields)
        self.assertEqual(response.status_code, 503)
        retry = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(retry['request_id'], fields['request_id'])
        self.assertEqual(self.post(path + '/feedback', retry).status_code, 303)
        self.assertEqual(AIRequest.query.count(), 1)

    def test_oversized_snapshot_notice_and_worker_failure_are_visible(self):
        sid, path = self.fixture()
        fields = FormFields(self.get(path).get_data(as_text=True)).values
        with patch.dict(self.app.config, LEARNING_AI_CONTEXT_BYTES=100):
            self.assertEqual(self.post(path + '/feedback', fields).status_code, 303)
            self.assertIn("too large to assess in one call", self.get(path).get_data(as_text=True))
        fields = FormFields(self.get(path).get_data(as_text=True)).values
        self.post(path + '/feedback', fields)
        practice_worker.run_once(practice_worker.FakeProvider('invalid'))
        page = self.get(path).get_data(as_text=True)
        self.assertIn("did not pass the evidence checks", page)
        self.assertIn("Request feedback again", page)
        self.assertEqual(PracticeFeedback.query.count(), 0)
