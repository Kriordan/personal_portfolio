"""Cookie/CSRF and JWT adapters share the same owner-scoped progress contract."""
import re
from unittest.mock import patch

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.models import ContentRevision, UserConceptProgress
from project.services import concept_progress_service as service
from tests.test_concept_progress import position
from tests.test_practice_service import SENTINELS
from tests.test_practice_web import FormFields, PracticeWebCase

LESSON = "/learning/concepts/idempotency"
API = "/api/v1/learning/concepts/idempotency"


def form_fields(response, marker):
    html = re.search(r'<form\b[^>]*' + marker + r'[^>]*>.*?</form>', response.get_data(as_text=True), re.S).group()
    return FormFields(html).values


class ConceptProgressRouteTests(PracticeWebCase):
    def api(self, method, path, payload=None, user=1):
        return self.client.open(API + path, method=method, json=payload, base_url="https://localhost",
            headers={"Authorization": "Bearer " + create_access_token(identity=str(user))})

    def test_jwt_enrollment_and_position_are_private_and_owned(self):
        self.assertIsNone(self.api("GET", "/progress").json["progress"])
        first = self.api("POST", "/enrollment", {})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json, self.api("POST", "/enrollment", {}).json)
        payload = position()
        saved = self.api("PUT", "/reading-position", payload)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json, self.api("PUT", "/reading-position", payload).json)
        self.assertEqual(self.api("GET", "/progress").headers["Cache-Control"], "private, no-store")
        self.assertIsNone(self.api("GET", "/progress", user=2).json["progress"])
        self.assertEqual(self.api("PUT", "/reading-position", payload, user=2).status_code, 409)
        for secret in SENTINELS:
            self.assertNotIn(secret, saved.get_data(as_text=True))
        self.assertEqual(self.client.get(API + "/progress", base_url="https://localhost").status_code, 401)
        self.assertEqual(self.api("GET", "/progress", user=999).status_code, 401)

    def test_payload_validation_drafts_and_conflicts(self):
        for payload in (None, [], {"user_id": 2}):
            self.assertEqual(self.api("POST", "/enrollment", payload).status_code, 400)
        self.api("POST", "/enrollment", {})
        for payload in ({}, dict(position(), section_id="missing"), dict(position(), expected_revision=True),
                        dict(position(), user_id=2)):
            self.assertEqual(self.api("PUT", "/reading-position", payload).status_code, 400)
        self.api("PUT", "/reading-position", position())
        self.assertEqual(self.api("PUT", "/reading-position", position()).status_code, 409)
        row = db.session.get(ContentRevision, ("idempotency", 1))
        row.published_at = row.reviewed_by = row.reviewed_on = None
        db.session.commit()
        self.assertEqual(self.api("GET", "/progress").status_code, 404)

    def test_web_enrollment_requires_csrf_and_keeps_selected_session_and_section(self):
        session_id = self.start()
        form = form_fields(self.get(LESSON + "?practice_session=" + session_id), "data-concept-enrollment")
        self.assertEqual(self.post(LESSON + "/enrollment", dict(form, csrf_token="")).status_code, 400)
        self.assertEqual(UserConceptProgress.query.count(), 0)
        form["section_id"] = "design"
        result = self.post(LESSON + "/enrollment", form)
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.location, LESSON + "?practice_session=" + session_id + "#design")
        self.assertEqual(self.post(LESSON + "/enrollment", form).status_code, 303)
        self.assertEqual(UserConceptProgress.query.count(), 1)
        self.login(2)
        foreign = dict(form, csrf_token=form_fields(self.get(LESSON), "data-concept-enrollment")["csrf_token"])
        self.assertEqual(self.post(LESSON + "/enrollment", foreign).status_code, 404)
        self.assertIsNone(service.progress(2, "idempotency"))

    def test_native_position_form_resume_home_and_conflict_recovery(self):
        service.enroll(1, "idempotency")
        fields = form_fields(self.get(LESSON), "data-reading-position")
        fields["section_id"] = "design"
        result = self.post(LESSON + "/reading-position", fields)
        self.assertEqual((result.status_code, result.location), (303, LESSON + "#design"))
        self.assertEqual(self.post(LESSON + "/reading-position", fields).status_code, 303)
        self.assertIn(b'data-resume-section="design"', self.get(LESSON).data)
        home = self.get("/learning/")
        self.assertIn(b'Continue lesson', home.data)
        self.assertIn((LESSON + "#design").encode(), home.data)
        newer = form_fields(self.get(LESSON), "data-reading-position")
        self.post(LESSON + "/reading-position", dict(newer, section_id="overview"))
        stale = self.post(LESSON + "/reading-position", fields)
        self.assertEqual(stale.status_code, 409)
        self.assertIn(b"Reload the lesson", stale.data)
        self.assertNotIn(b"Retry save", stale.data)

    def test_failure_responses_preserve_retry_fields_and_never_claim_success(self):
        fields = form_fields(self.get(LESSON), "data-concept-enrollment")
        with patch.object(service, "enroll", side_effect=SQLAlchemyError("fixture")), self.assertLogs("project", "ERROR"):
            failed = self.post(LESSON + "/enrollment", fields)
        self.assertEqual(failed.status_code, 503)
        self.assertIn(b"Retry Start learning", failed.data)
        self.assertIsNone(service.progress(1, "idempotency"))
        self.post(LESSON + "/enrollment", fields)
        fields = form_fields(self.get(LESSON), "data-reading-position")
        with patch.object(service, "save_position", side_effect=SQLAlchemyError("fixture")), self.assertLogs("project", "ERROR"):
            failed = self.post(LESSON + "/reading-position", fields)
        self.assertEqual(failed.status_code, 503)
        retry = FormFields(failed.get_data(as_text=True)).values
        self.assertEqual(retry["request_id"], fields["request_id"])
        self.assertEqual(retry["expected_revision"], fields["expected_revision"])
        self.assertEqual(self.post(LESSON + "/reading-position", retry).status_code, 303)

    def test_json_web_save_and_api_database_failure(self):
        service.enroll(1, "idempotency")
        fields = form_fields(self.get(LESSON), "data-reading-position")
        response = self.client.post(LESSON + "/reading-position", data=fields,
            headers={"Accept": "application/json"}, base_url="https://localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["progress"]["revision"], 2)
        with patch.object(service, "save_position", side_effect=SQLAlchemyError("fixture")), self.assertLogs("project", "ERROR"):
            failed = self.api("PUT", "/reading-position", position(2))
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn("progress", failed.json)
