"""Native form/CSRF recovery and JWT snapshot boundaries."""
import json
from unittest.mock import patch
from uuid import uuid4

from flask import g
from sqlalchemy.exc import OperationalError

from project.models import SessionMessage
from project.services import practice_service as service
from tests.test_practice_api import PracticeApiCase
from tests.test_practice_web import PracticeWebCase, FormFields, as_browser
from tests.test_practice_service import SENTINELS
from tests.test_practice_submissions import submission_input


class SubmissionApiTests(PracticeApiCase):
    def test_save_read_replay_and_receipt_recovery(self):
        sid = self.start()
        path = f"/sessions/{sid}/submissions"
        values = submission_input(self.call("GET", f"/sessions/{sid}").get_json(), '{"order":1}')
        response = self.call("POST", path, values)
        self.assertEqual(response.status_code, 201, response.get_json())
        result = response.get_json()
        seq = result["submission"]["sequence"]
        self.assertEqual(result["submission"]["checks"][0]["status"], "passed")
        self.assertEqual(self.call("POST", path, values).get_json(), result)
        self.assertEqual(self.call("GET", f"/receipts/{values['request_id']}").get_json()["receipt"]["response"], result)
        detail = self.call("GET", f"{path}/{seq}")
        self.assertEqual(detail.headers["Cache-Control"], "private, no-store")
        self.assertEqual(detail.get_json()["submission"], result["submission"])
        self.assertEqual(self.call("GET", f"/sessions/{sid}").get_json()["submissions"], [result["submission"]])
        for secret in SENTINELS:
            self.assertNotIn(secret, detail.get_data(as_text=True) + json.dumps(result))

    def test_authentication_owner_scope_feature_flag_and_input_contract(self):
        sid = self.start()
        path = f"/sessions/{sid}/submissions"
        values = submission_input(self.call("GET", f"/sessions/{sid}").get_json(), '{}')
        self.assertEqual(self.call("POST", path, values, user_id=None).status_code, 401)
        self.assertEqual(self.call("POST", path, values, user_id=2).status_code, 404)
        self.assertEqual(self.call("POST", path, values | {"private_solution": "x"}).status_code, 400)
        result = self.call("POST", path, values).get_json()
        read_path = path + '/' + str(result["submission"]["sequence"])
        self.assertEqual(self.call("GET", read_path, user_id=2).status_code, 404)
        self.assertEqual(self.call("GET", path + '/1').status_code, 404)
        self.app.config["LEARNING_PRACTICE_ENABLED"] = False
        self.assertEqual(self.call("POST", path, values).status_code, 404)
        self.assertEqual(self.call("GET", read_path).status_code, 404)

    def test_stale_snapshot_and_ambiguous_commit_follow_existing_api_contract(self):
        sid = self.start()
        path = f"/sessions/{sid}/submissions"
        values = submission_input(self.call("GET", f"/sessions/{sid}").get_json(), '{}')
        self.put(sid, 'other tab')
        refused = self.call("POST", path, values)
        self.assertEqual((refused.status_code, refused.get_json()["code"]), (409, "stale_artifact"))
        values = submission_input(self.call("GET", f"/sessions/{sid}").get_json(), '{}')
        real = service.save_and_submit

        def lost(*args, **kwargs):
            real(*args, **kwargs)
            raise OperationalError("fixture", {}, Exception("lost"))

        with patch.object(service, "save_and_submit", lost):
            response = self.call("POST", path, values)
        self.assertEqual((response.status_code, response.get_json()["retry_same_request"]), (503, True))
        self.assertEqual(self.call("POST", path, values).status_code, 201)
        self.assertEqual(SessionMessage.query.filter_by(kind="submission").count(), 1)


class SubmissionWebTests(PracticeWebCase):
    def test_native_form_saves_checks_keeps_unsent_message_and_shows_exact_old_revision(self):
        sid = self.start()
        path = f"/learning/practice/{sid}"
        fields = self.fields(sid)
        fields.update(action="submit", message="Draft question", **{"artifacts-0-language": "json",
                      "artifacts-0-body": '{"path":"/orders",}'})
        response = self.post(path, as_browser(fields))
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual(FormFields(html).values["message"], "Draft question")
        self.assertIn("Snapshot saved with syntax check results", html)
        self.assertIn("Syntax issue", html)
        self.assertIn("Your message hasn&#39;t been sent", html)
        row = SessionMessage.query.filter_by(kind="submission").one()
        self.assertEqual(SessionMessage.query.filter_by(kind="turn").count(), 1)
        self.save(sid, self.fields(sid), api='{"path":"/orders"}')
        old = self.get(f"{path}/submissions/{row.sequence}")
        self.assertIn("Older work: current saved revision is 2", old.get_data(as_text=True))
        self.assertIn("Syntax issue", old.get_data(as_text=True))
        self.assertIn(f'/artifacts/api/1', old.get_data(as_text=True))
        for secret in SENTINELS:
            self.assertNotIn(secret, old.get_data(as_text=True) + html)

    def test_csrf_and_foreign_owner_cannot_create_or_read_snapshots(self):
        sid = self.start()
        fields = self.fields(sid)
        fields.update(action="submit", **{"artifacts-0-language": "json", "artifacts-0-body": '{}'})
        bad = self.post(f"/learning/practice/{sid}", fields | {"csrf_token": "invalid"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(SessionMessage.query.filter_by(kind="submission").count(), 0)
        result = self.post(f"/learning/practice/{sid}", fields)
        self.assertEqual(result.status_code, 303)
        self.assertIn('work=work-checks', result.headers["Location"])
        seq = SessionMessage.query.filter_by(kind="submission").one().sequence
        self.login(2)
        self.assertEqual(self.get(f"/learning/practice/{sid}/submissions/{seq}").status_code, 404)
        with self.client.session_transaction() as session:
            session.clear()
        g.pop("_login_user", None)
        self.assertEqual(self.get(f"/learning/practice/{sid}/submissions/{seq}").status_code, 302)

    def test_lost_response_rescue_retries_identical_request_without_duplicate_snapshot(self):
        sid = self.start()
        path = f"/learning/practice/{sid}"
        fields = self.fields(sid)
        fields.update(action="submit", message="Unsent draft", **{"artifacts-0-language": "yaml",
                      "artifacts-0-body": 'path: /orders'})
        real = service.save_and_submit

        def lost(*args, **kwargs):
            real(*args, **kwargs)
            raise OperationalError("fixture", {}, Exception("lost"))

        with patch.object(service, "save_and_submit", lost), \
                patch.object(service, "session_detail", side_effect=AssertionError("rescue must not read DB")):
            response = self.post(path, as_browser(fields))
        self.assertEqual(response.status_code, 503)
        rescued = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(rescued["request_id"], fields["request_id"])
        self.assertEqual(rescued["message"], fields["message"])
        self.assertIn('value="submit"', response.get_data(as_text=True))
        self.assertEqual(self.post(path, as_browser(rescued | {"action": "submit"})).status_code, 200)
        self.assertEqual(SessionMessage.query.filter_by(kind="submission").count(), 1)

    def test_stale_form_keeps_draft_and_explains_no_snapshot_was_saved(self):
        sid = self.start()
        fields = self.fields(sid)
        self.save(sid, fields, api="Other tab")
        response = self.post(f"/learning/practice/{sid}", fields | {
            "action": "submit", "message": "Draft", "request_id": str(uuid4())})
        self.assertEqual(response.status_code, 409)
        self.assertIn("No snapshot was saved", response.get_data(as_text=True))
        self.assertEqual(FormFields(response.get_data(as_text=True)).values["message"], "Draft")
        self.assertEqual(SessionMessage.query.filter_by(kind="submission").count(), 0)
