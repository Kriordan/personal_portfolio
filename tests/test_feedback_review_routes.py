from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from flask import g
from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import PracticeFeedbackAnnotation, ReviewLog, User
from project.services import feedback_service, feedback_review_service as review, practice_service
from tests.curriculum_v2_fixtures import PRIVATE_V2, publish_feedback_catalog
from tests.test_feedback_review import completed_feedback
from tests.test_feedback_routes import enable
from tests.test_practice_api import PracticeApiCase
from tests.test_practice_web import PracticeWebCase, FormFields


class Fixture:
    def setUp(self):
        super().setUp()
        enable(self.app)
        publish_feedback_catalog()
        self.sid, self.seq, self.rid = completed_feedback(db.session.get(User, 1))
        self.path = f"/learning/practice/{self.sid}/submissions/{self.seq}"
        self.api = f"/sessions/{self.sid}/submissions/{self.seq}/feedback/f2"

    def agree(self):
        return review.annotate(db.session.get(User, 1), self.sid, self.seq, "f2", decision="agree", note="Try the race",
                               expected_revision=0, request_id=str(uuid4()))


class FeedbackReviewApiTests(Fixture, PracticeApiCase):
    def test_responses_reveal_and_explicit_rating_with_authoritative_targets(self):
        values = dict(decision="agree", note="My note", expected_revision=0, request_id=str(uuid4()))
        response = self.call("PUT", self.api + "/response", values)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), self.call("PUT", self.api + "/response", values).get_json())
        detail = self.call("GET", self.api + "/review").get_json()
        card = detail["questions"][0]
        self.assertNotIn("answer", card)
        attempt = dict(card_id=card["card_id"], content_version=card["content_version"],
                       expected_revision=card["progress_revision"], request_id=str(uuid4()))
        revealed = self.call("GET", self.api + "/review?" + urlencode(attempt))
        self.assertIn("answer", revealed.get_json())
        self.assertEqual(ReviewLog.query.count(), 0)
        for private in (*PRIVATE_V2, "misconception_ids", "reference_reasoning", "rubric"):
            self.assertNotIn(private, response.get_data(as_text=True) + revealed.get_data(as_text=True))
        rating = dict(attempt, rating=4)
        self.assertEqual(self.call("POST", self.api + "/review", rating).status_code, 200)
        self.assertEqual(self.call("POST", self.api + "/review", rating).status_code, 200)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(self.call("GET", self.api + "/review").get_json()["completed"], 1)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_login_ownership_feature_flag_validation_and_stale_conflicts(self):
        values = dict(decision="agree", note="A", expected_revision=0, request_id=str(uuid4()))
        for method, path, payload in (("PUT", self.api + "/response", values), ("GET", self.api + "/review", None),
                                      ("POST", self.api + "/review", {})):
            self.assertEqual(self.call(method, path, payload, user_id=None).status_code, 401)
            if method != "POST":
                self.assertEqual(self.call(method, path, payload, user_id=2).status_code, 404)
            with patch.dict(self.app.config, LEARNING_PRACTICE_ENABLED=False):
                self.assertEqual(self.call(method, path, payload).status_code, 404)
        self.assertEqual(self.call("PUT", self.api + "/response", dict(values, output={})).status_code, 400)
        self.call("PUT", self.api + "/response", values)
        stale = self.call("PUT", self.api + "/response", dict(values, request_id=str(uuid4()), note="B"))
        self.assertEqual((stale.status_code, stale.get_json()["code"]), (409, "stale_annotation"))
        self.assertEqual(stale.get_json()["annotation"]["note"], "A")
        bad = dict(card_id="idempotency:timeout", content_version=2, expected_revision=0, request_id=str(uuid4()), rating=4)
        self.assertEqual(self.call("POST", self.api + "/review", bad).status_code, 404)
        self.assertEqual(self.call("POST", self.api + "/review", bad, user_id=2).status_code, 404)
        self.assertEqual(self.call("POST", self.api + "/review", dict(bad, question_ids=[])).status_code, 400)
        self.assertEqual(self.call("GET", self.api + "/review?card_id=idempotency:race").status_code, 400)

    def test_unknown_annotation_commit_returns_same_id_recovery_and_no_note_in_receipt(self):
        values = dict(decision="agree", note="SENSITIVE_NOTE", expected_revision=0, request_id=str(uuid4()))
        original = review.annotate
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError("", {}, Exception("lost"))
        with patch.object(review, "annotate", side_effect=lost):
            response = self.call("PUT", self.api + "/response", values)
        self.assertEqual((response.status_code, response.get_json()["retry_same_request"]), (503, True))
        self.assertEqual(self.call("PUT", self.api + "/response", values).status_code, 200)
        receipt = self.call("GET", "/receipts/" + values["request_id"])
        self.assertNotIn("SENSITIVE_NOTE", receipt.get_data(as_text=True))
        self.assertEqual(PracticeFeedbackAnnotation.query.one().revision, 1)


class FeedbackReviewWebTests(Fixture, PracticeWebCase):
    def fields_for_response(self):
        return {k: v for k, v in FormFields(self.get(self.path).get_data(as_text=True)).values.items()
                if k.startswith("annotation-f2-")}

    def annotation(self, fields):
        return self.post(self.path + "/feedback/f2/response", fields)

    def review_attempt(self):
        path = self.path + "/feedback/f2/review"
        question = self.get(path)
        self.assertEqual(question.status_code, 200)
        fields = FormFields(question.get_data(as_text=True)).values
        revealed = self.get(path + "?" + urlencode(fields))
        self.assertEqual(revealed.status_code, 200, revealed.get_data(as_text=True))
        return path, FormFields(revealed.get_data(as_text=True)).values

    def test_native_response_extra_practice_and_return_keep_the_exact_session(self):
        fields = self.fields_for_response()
        fields.update({"annotation-f2-decision": "agree", "annotation-f2-note": "\nA <script>note</script>"})
        self.assertEqual(self.annotation(fields).status_code, 303)
        page = self.get(self.path).get_data(as_text=True)
        self.assertIn("&lt;script&gt;note", page)
        self.assertNotIn("<script>note", page)
        self.assertIn("Practise this", page)
        self.assertEqual(ReviewLog.query.count(), 0)
        practice_service.start_session(db.session.get(User, 1), exercise_id="idempotent-order-api", request_id=str(uuid4()))
        path, attempt = self.review_attempt()
        page = self.get(path).get_data(as_text=True)
        self.assertIn(f'/practice/{self.sid}?view=build', page)
        self.assertIn("Extra practice from feedback", page)
        for _ in range(2):
            self.assertEqual(self.post(path, dict(attempt, rating="4")).status_code, 303)
        self.assertIn("Extra practice saved", self.get(path).get_data(as_text=True))
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_stale_note_compares_saved_and_draft_before_an_explicit_overwrite(self):
        fields = self.fields_for_response()
        self.annotation(dict(fields, **{"annotation-f2-note": "First tab"}))
        second = dict(fields, **{"annotation-f2-request_id": str(uuid4()), "annotation-f2-note": "Second tab"})
        response = self.annotation(second)
        self.assertEqual(response.status_code, 409)
        self.assertIn("First tab", response.get_data(as_text=True))
        retry = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(retry["annotation-f2-note"], "Second tab")
        self.assertEqual(retry["annotation-f2-expected_revision"], "1")
        self.assertEqual(self.annotation(retry).status_code, 303)
        self.assertEqual(PracticeFeedbackAnnotation.query.one().note, "Second tab")

    def test_response_failure_preserves_note_and_request_without_reading_the_database_again(self):
        fields = dict(self.fields_for_response(), **{"annotation-f2-note": "Draft survives\n\n"})
        original = review.annotate
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError("", {}, Exception("lost"))
        with patch.object(review, "annotate", side_effect=lost), \
                patch.object(feedback_service, "detail", side_effect=AssertionError("read after commit")):
            response = self.annotation(fields)
        self.assertEqual(response.status_code, 503)
        retry = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(retry, fields)
        self.assertEqual(self.annotation(retry).status_code, 303)
        self.assertEqual(PracticeFeedbackAnnotation.query.one().revision, 1)

    def test_csrf_validation_and_ownership_preserve_drafts(self):
        fields = dict(self.fields_for_response(), **{"annotation-f2-note": "Keep my note"})
        bad = dict(fields, **{"annotation-f2-csrf_token": "wrong"})
        response = self.annotation(bad)
        self.assertEqual(response.status_code, 400)
        retry = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(retry["annotation-f2-note"], "Keep my note")
        self.assertEqual(self.annotation(retry).status_code, 303)
        fields = self.fields_for_response()
        too_long = self.annotation(dict(fields, **{"annotation-f2-note": "x" * 2001}))
        self.assertEqual(too_long.status_code, 400)
        self.assertIn("x" * 2001, too_long.get_data(as_text=True))
        self.login(2)
        token = FormFields(self.get('/learning/concepts/idempotency/practice').get_data(as_text=True)).values['csrf_token']
        self.assertEqual(self.annotation(dict(fields, **{"annotation-f2-csrf_token": token})).status_code, 404)
        self.assertEqual(self.get(self.path + '/feedback/f2/review').status_code, 404)
        with self.client.session_transaction() as session:
            session.clear()
        g.pop('_login_user', None)
        self.assertEqual(self.get(self.path + '/feedback/f2/review').status_code, 302)

    def test_rating_recovery_and_stale_forms_do_not_duplicate_history(self):
        self.agree()
        path, attempt = self.review_attempt()
        original = review.rate_review
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError("", {}, Exception("lost"))
        with patch.object(review, "rate_review", side_effect=lost), \
                patch.object(review, "review_detail", side_effect=AssertionError("read after commit")):
            response = self.post(path, dict(attempt, rating="4"))
        self.assertEqual(response.status_code, 503)
        retry = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(retry["request_id"], attempt["request_id"])
        self.assertEqual(self.post(path, dict(retry, rating="4")).status_code, 303)
        stale = self.post(path, dict(attempt, rating="4", request_id=str(uuid4())))
        self.assertEqual(stale.status_code, 409)
        self.assertIn("Load remaining practice", stale.get_data(as_text=True))
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_read_failure_has_a_standalone_reload_without_shared_layout_queries(self):
        self.agree()
        with patch.object(review, "review_detail", side_effect=OperationalError("", {}, Exception("fixture"))):
            response = self.get(self.path + '/feedback/f2/review')
        self.assertEqual(response.status_code, 503)
        self.assertIn("Reload extra practice", response.get_data(as_text=True))
