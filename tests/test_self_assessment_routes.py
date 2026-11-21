"""Private native forms and JWT history share ownership and recovery behavior."""
from unittest.mock import patch

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.models import ConceptSelfAssessment, ContentRevision, UserConceptProgress
from project.services import self_assessment_service as service
from tests.test_concept_progress_routes import form_fields
from tests.test_practice_service import SENTINELS
from tests.test_practice_web import PracticeWebCase
from tests.test_self_assessment import checkin, clear

PATH = "/learning/concepts/idempotency/self-assessment"
API = "/api/v1/learning/concepts/idempotency/self-assessments"


class SelfAssessmentRouteTests(PracticeWebCase):
    def api(self, method="GET", payload=None, *, user=1, query=""):
        return self.client.open(API + query, method=method, json=payload, base_url="https://localhost",
            headers={"Authorization": "Bearer " + create_access_token(identity=str(user))})

    def fields(self, response=None):
        return form_fields(response or self.get(PATH), "data-self-assessment-form")

    def test_private_reads_skip_writes_and_require_login_or_jwt(self):
        page = self.get(PATH)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "private, no-store")
        self.assertIn(b"learning-self-assessment.js", page.data)
        self.assertNotIn(b"googletagmanager", page.data)
        self.assertNotIn(b"hotjar", page.data)
        self.assertEqual((ConceptSelfAssessment.query.count(), UserConceptProgress.query.count()), (0, 0))
        self.assertEqual(self.api().json["revision"], 0)
        self.assertEqual(self.api().headers["Cache-Control"], "private, no-store")
        self.assertEqual(self.api(user=999).status_code, 401)
        self.assertEqual(self.client.get(API, base_url="https://localhost").status_code, 401)
        self.login(999)
        self.assertEqual(self.get(PATH).status_code, 302)

    def test_native_save_reload_selected_session_and_csrf(self):
        session_id = self.start()
        page = self.get(PATH + "?practice_session=" + session_id)
        fields = self.fields(page)
        self.assertEqual(fields["practice_session"], session_id)
        for csrf in ("", "wrong"):
            bad = self.post(PATH, dict(fields, csrf_token=csrf))
            self.assertEqual(bad.status_code, 400)
            self.assertIn(b"Your choices", bad.data)
        self.assertEqual(ConceptSelfAssessment.query.count(), 0)
        fields["recognition"] = "without_help"
        response = self.post(PATH, fields)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, PATH + "?practice_session=" + session_id)
        self.assertEqual(self.fields(self.get(response.location))["recognition"], "without_help")
        self.assertEqual(self.post(PATH, fields).status_code, 303)
        self.assertEqual(ConceptSelfAssessment.query.count(), 1)
        self.login(2)
        other = self.fields()
        self.assertEqual(other["recognition"], "not_assessed")
        self.assertEqual(self.get(PATH + "?practice_session=" + session_id).status_code, 404)
        self.assertEqual(self.post(PATH, dict(other, practice_session=session_id)).status_code, 404)
        self.assertEqual(service.history(2, "idempotency")["revision"], 0)

    def test_stale_form_keeps_choices_and_requires_explicit_new_checkin(self):
        fields = self.fields()
        fields["judgment"] = "with_help"
        service.save(1, "idempotency", **checkin(recognition="without_help"))
        response = self.post(PATH, fields)
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"Latest saved check-in", response.data)
        self.assertIn(b"Save as a new check-in", response.data)
        retry = self.fields(response)
        self.assertEqual(retry["judgment"], "with_help")
        self.assertEqual(retry["expected_revision"], "1")
        self.assertNotEqual(retry["request_id"], fields["request_id"])
        self.assertEqual(ConceptSelfAssessment.query.count(), 1)
        self.assertEqual(self.post(PATH, retry).status_code, 303)
        self.assertEqual(len(service.history(1, "idempotency")["entries"]), 2)

    def test_unknown_save_outcome_replays_original_even_after_newer_save(self):
        fields = self.fields()
        fields["understanding"] = "not_yet"
        real_save = service.save
        def lost(*args, **kwargs):
            real_save(*args, **kwargs)
            raise SQLAlchemyError("fixture response lost")
        with patch.object(service, "save", side_effect=lost), self.assertLogs("project", "WARNING"):
            failed = self.post(PATH, fields)
        self.assertEqual(failed.status_code, 503)
        retry = self.fields(failed)
        for key in ("request_id", "expected_revision", *service.FIELDS):
            self.assertEqual(retry[key], fields[key])
        service.save(1, "idempotency", **checkin(1, judgment="without_help"))
        self.assertEqual(self.post(PATH, retry).status_code, 303)
        self.assertEqual(ConceptSelfAssessment.query.count(), 2)
        self.assertEqual(service.history(1, "idempotency")["current"]["ratings"]["judgment"], "without_help")

    def test_delete_confirmation_csrf_conflict_and_lost_response_retry(self):
        service.save(1, "idempotency", **checkin())
        fields = form_fields(self.get(PATH + "/delete"), "data-assessment-delete")
        self.assertEqual(self.post(PATH + "/delete", dict(fields, csrf_token="")).status_code, 400)
        service.save(1, "idempotency", **checkin(1))
        failed = self.post(PATH + "/delete", fields)
        self.assertEqual(failed.status_code, 409)
        self.assertNotIn(b"Retry deletion", failed.data)
        self.assertIn(b"Review deletion again", failed.data)
        fields = form_fields(self.get(PATH + "/delete"), "data-assessment-delete")
        real_clear = service.clear_history
        def lost(*args, **kwargs):
            real_clear(*args, **kwargs)
            raise SQLAlchemyError("fixture response lost")
        with patch.object(service, "clear_history", side_effect=lost), self.assertLogs("project", "WARNING"):
            failed = self.post(PATH + "/delete", fields)
        self.assertEqual(failed.status_code, 503)
        service.save(1, "idempotency", **checkin(3, application="with_help"))
        self.assertEqual(self.post(PATH + "/delete", fields).status_code, 303)
        self.assertEqual(len(service.history(1, "idempotency")["entries"]), 1)

    def test_api_is_allowlisted_owned_versioned_and_has_bounded_history(self):
        payload = checkin(recognition="without_help")
        saved = self.api("POST", payload)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json, self.api("POST", payload).json)
        self.assertEqual(set(saved.json["checkin"]), {"revision", "ratings", "created_at", "content_version", "scale_version"})
        self.assertEqual(self.api(user=2).json["entries"], [])
        conflict = self.api("POST", checkin())
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json["current"], saved.json["checkin"])
        for invalid in (None, [], {}, dict(payload, user_id=2), dict(payload, expected_revision=True),
                        dict(payload, ratings=dict(payload["ratings"], recognition="<script>"))):
            self.assertEqual(self.api("POST", invalid).status_code, 400)
        for query in ("?before=0", "?before=-1", "?before=bad", "?before=" + "1" * 400):
            self.assertEqual(self.api(query=query).status_code, 400)
            self.assertEqual(self.get(PATH + query).status_code, 400)
        for secret in SENTINELS:
            self.assertNotIn(secret, saved.get_data(as_text=True) + self.get(PATH).get_data(as_text=True))
        self.assertEqual(self.api("DELETE", clear(1)).status_code, 200)
        self.assertIsNone(self.api().json["current"])
        self.assertEqual(self.api("POST", payload).status_code, 409)

    def test_api_failure_is_retryable_without_leaking_error_or_data(self):
        with patch.object(service, "save", side_effect=SQLAlchemyError("secret fixture")), self.assertLogs("project", "WARNING") as logs:
            failed = self.api("POST", checkin())
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn("secret fixture", failed.get_data(as_text=True) + str(logs.output))

    def test_validation_and_conflict_details_stay_private_across_api_and_web(self):
        current = service.save(1, "idempotency", **checkin(recognition="with_help"))
        fields = self.fields()
        private_detail = "internal assessment fixture detail"
        stale = service.AssessmentConflict(current["revision"], current)
        stale.args = (private_detail,)
        for error, status in ((service.ValidationError(private_detail), 400),
                              (service.ConflictError(private_detail), 409), (stale, 409)):
            with self.subTest(error=type(error)), patch.object(service, "save", side_effect=error):
                api = self.api("POST", checkin(1))
                page = self.post(PATH, fields)
                self.assertEqual((api.status_code, page.status_code), (status, status))
                self.assertTrue(api.json["error"])
                self.assertNotIn(private_detail, api.get_data(as_text=True) + page.get_data(as_text=True))
                self.assertEqual(self.fields(page)["recognition"], "with_help")
                if error is stale:
                    self.assertEqual((api.json["revision"], api.json["current"]), (current["revision"], current))

    def test_withdrawn_lesson_shows_only_owned_history_and_deletion(self):
        service.save(1, "idempotency", **checkin())
        row = db.session.get(ContentRevision, ("idempotency", 1))
        row.published_at = row.reviewed_by = row.reviewed_on = None
        db.session.commit()
        page = self.get(PATH)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"currently unavailable", page.data)
        self.assertNotIn(b"data-self-assessment-form", page.data)
        self.assertEqual(self.api().status_code, 200)
        self.assertEqual(self.api("POST", checkin(1)).status_code, 404)
        self.assertEqual(self.api("DELETE", clear(1)).status_code, 200)
        self.login(2)
        self.assertEqual(self.get(PATH).status_code, 404)

    def test_older_pages_keep_latest_choices_and_open_history(self):
        for rev in range(12):
            service.save(1, "idempotency", **checkin(rev, recognition="with_help" if rev == 11 else "not_yet"))
        page = self.get(PATH)
        self.assertEqual(page.data.count(b"data-assessment-entry"), 10)
        older = self.get(PATH + "?before=3")
        self.assertEqual(older.data.count(b"data-assessment-entry"), 2)
        self.assertIn(b'id="assessment-history" open', older.data)
        self.assertEqual(self.fields(older)["recognition"], "with_help")
        self.assertEqual(self.fields(older)["expected_revision"], "12")
