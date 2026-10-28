"""The real lesson/review routes, with CSRF and disposable published fixtures."""
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from flask_jwt_extended import create_access_token
from flask import g
from sqlalchemy.exc import SQLAlchemyError

from project import create_app
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import ContentRevision, CurriculumItem, ReviewLog, ReviewProgress, ReviewReceipt, User
from project.services import curriculum_service, learning_service

ROOT = Path(__file__).resolve().parents[1]
LESSON = "/learning/concepts/idempotency"
REVIEW = LESSON + "/review"


class FormInputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name"):
            self.values[attrs["name"]] = attrs.get("value", "")


class ConceptWebTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture",
            JWT_SECRET_KEY="fixture-jwt-secret-at-least-32-characters", SQLALCHEMY_DATABASE_URI="sqlite://",
            WTF_CSRF_ENABLED=True))
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([User(id=i, username=f"fixture{i}", email=f"fixture{i}@example.test", is_admin=True)
                            for i in (1, 2)])
        self.catalog = load_catalog(ROOT / "curriculum/idempotency/catalog.json")
        self.catalog["items"][-1]["content"]["assessment"]["reference_reasoning"] = ["EVALUATOR_SECRET"]
        self.catalog["items"][-1]["content"]["facilitator"]["hidden_constraints"][0]["fact"] = "HIDDEN_SECRET"
        for item in self.catalog["items"]:
            db.session.add(CurriculumItem(id=item["id"], kind=item["kind"]))
        db.session.flush()
        for item in self.catalog["items"]:
            self.add_revision(item)
        db.session.commit()
        self.client = self.app.test_client()
        self.login(1)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def add_revision(self, item):
        now = datetime.now(timezone.utc)
        db.session.add(ContentRevision(item_id=item["id"], version=item["version"], schema_version=1,
            payload=item, checksum=curriculum_service.content_checksum(item), imported_at=now,
            published_at=now, reviewed_by="Test fixture", reviewed_on=now.date()))

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        # This fixture keeps an outer app context for DB assertions; real HTTP
        # requests get fresh g objects and do not retain Flask-Login's cache.
        g.pop("_login_user", None)

    def get(self, path, **kwargs):
        return self.client.get(path, base_url="https://localhost", **kwargs)

    def post(self, data):
        return self.client.post(REVIEW, data=data, base_url="https://localhost")

    def reveal(self):
        question = self.get(REVIEW)
        self.assertEqual(question.status_code, 200)
        inputs = FormInputs(question.get_data(as_text=True)).values
        self.assertIn("card_id", inputs)
        self.assertNotIn("csrf_token", inputs)
        answer = self.get(REVIEW + "?" + urlencode(inputs))
        self.assertEqual(answer.status_code, 200)
        return inputs, FormInputs(answer.get_data(as_text=True)).values

    def test_authenticated_lesson_and_explicit_reveal_do_not_change_progress(self):
        page = self.get(LESSON)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "private, no-store")
        self.assertIn(b"4 questions due", page.data)
        self.assertIn(b"data-retry-lab", page.data)
        for hidden in (b"EVALUATOR_SECRET", b"HIDDEN_SECRET", b"googletagmanager.com", b"hotjar"):
            self.assertNotIn(hidden, page.data)
        question = self.get(REVIEW)
        inputs = FormInputs(question.get_data(as_text=True)).values
        answer_text = curriculum_service.published_review_question("idempotency", inputs["card_id"], reveal_answer=True)["answer"]
        self.assertNotIn(answer_text, question.get_data(as_text=True))
        self.assertNotIn(b'name="rating"', question.data)
        for _ in range(2):
            answer = self.get(REVIEW + "?" + urlencode(inputs))
            self.assertIn(b"Compare your answer", answer.data)
            self.assertIn(b'name="csrf_token"', answer.data)
        self.assertEqual(ReviewProgress.query.count(), 0)
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assertEqual(ReviewReceipt.query.count(), 0)

    def test_authentication_drafts_and_wrong_content_types_are_hidden(self):
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.get(LESSON).status_code, 302)
        self.assertEqual(self.get(REVIEW).status_code, 302)
        self.login(1)
        self.assertEqual(self.get("/learning/concepts/idempotent-order-api").status_code, 404)
        revision = db.session.get(ContentRevision, ("idempotency", 1))
        revision.published_at = revision.reviewed_by = revision.reviewed_on = None
        db.session.commit()
        self.assertEqual(self.get(LESSON).status_code, 404)
        self.assertEqual(self.get(REVIEW).status_code, 404)
        self.assertNotIn(b"/learning/concepts/idempotency", self.get("/learning").data)

    def test_rating_replay_stale_tabs_and_user_isolation(self):
        reveal_query, values = self.reveal()
        values["rating"] = "4"
        self.assertEqual(self.post(values).status_code, 303)
        self.assertEqual(self.post(values).status_code, 303)  # lost-response retry
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewLog.query.one().content_version, 1)
        self.assertEqual(ReviewReceipt.query.one().payload["content_version"], 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)
        self.assertEqual(self.get(REVIEW + "?" + urlencode(reveal_query)).status_code, 409)
        stale = dict(values, request_id=str(uuid4()))
        self.assertEqual(self.post(stale).status_code, 409)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertIn(b"3 questions due", self.get(LESSON).data)
        self.login(2)
        self.assertIn(b"4 questions due", self.get(LESSON).data)
        receipt = self.get("/learning/ratings/" + values["request_id"]).get_json()
        self.assertIsNone(receipt["receipt"])

    def test_old_question_version_can_finish_without_resetting_progress(self):
        query, values = self.reveal()
        item = deepcopy(next(item for item in self.catalog["items"] if item["id"] == values["card_id"]))
        item["version"] = 2
        item["content"]["prompt"] = "A revised question"
        self.add_revision(item)
        db.session.commit()
        old = self.get(REVIEW + "?" + urlencode(query))
        self.assertNotIn(b"A revised question", old.data)
        values["rating"] = "4"
        self.assertEqual(self.post(values).status_code, 303)
        self.assertEqual(ReviewLog.query.one().content_version, 1)
        self.assertEqual(self.post(dict(values, content_version="2")).status_code, 409)
        self.assertEqual(ReviewProgress.query.one().revision, 1)

    def test_csrf_bad_inputs_and_cross_concept_questions_are_rejected(self):
        query, values = self.reveal()
        self.assertEqual(self.post(dict(values, csrf_token="", rating="4")).status_code, 400)
        self.assertEqual(self.post(dict(values, rating="2")).status_code, 400)
        self.assertEqual(self.post(dict(values, rating="4", request_id="x" * 36)).status_code, 400)
        for key, value, status in (("content_version", "1.0", 400), ("expected_revision", "-1", 400),
                                   ("card_id", "idempotent-order-api", 404)):
            with self.subTest(key=key):
                self.assertEqual(self.get(REVIEW + "?" + urlencode(dict(query, **{key: value}))).status_code, status)
        self.assertEqual(ReviewLog.query.count(), 0)

    def test_failed_save_keeps_identical_attempt_and_rolls_back(self):
        _, values = self.reveal()
        values["rating"] = "4"
        apply = learning_service._apply_rating

        def fail_after_writes(**kwargs):
            apply(**kwargs)
            db.session.flush()
            raise SQLAlchemyError("fixture interruption")

        with patch.object(learning_service, "_apply_rating", side_effect=fail_after_writes), self.assertLogs("project", level="ERROR"):
            response = self.post(values)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"fixture interruption", response.data)
        retry = FormInputs(response.get_data(as_text=True)).values
        self.assertEqual(retry["request_id"], values["request_id"])
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assertEqual(ReviewProgress.query.count(), 0)
        self.assertEqual(ReviewReceipt.query.count(), 0)
        self.assertEqual(self.post(dict(retry, rating="4")).status_code, 303)
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_four_reviews_complete_and_existing_api_remains_legacy_only(self):
        for _ in range(4):
            _, values = self.reveal()
            self.assertEqual(self.post(dict(values, rating="4")).status_code, 303)
        done = self.get(REVIEW)
        self.assertIn(b"No questions due right now", done.data)
        self.assertIn(b"Review saved", done.data)
        self.assertEqual(ReviewLog.query.count(), 4)
        token = create_access_token(identity="1")
        headers = {"Authorization": "Bearer " + token}
        notes = self.get("/api/v1/learning/notes", headers=headers).get_json()
        self.assertEqual(len(notes["notes"]), 4)
        self.assertEqual(notes["total_due"], 37)
        queue = self.get("/api/v1/learning/review", headers=headers).get_json()
        self.assertEqual(queue["total_due"], 37)
        self.assertNotIn("idempotency", {card["note_id"] for card in queue["cards"]})

    def test_markdown_is_escaped_in_html_and_namespace_cannot_be_reused(self):
        revision = db.session.get(ContentRevision, ("idempotency", 1))
        payload = deepcopy(revision.payload)
        payload["content"]["sections"][0]["markdown"] = '<script>alert("unsafe")</script>'
        revision.payload = payload
        db.session.commit()
        response = self.get(LESSON)
        self.assertNotIn(b'<script>alert(', response.data)
        self.assertIn(b'&lt;script&gt;', response.data)
        response = self.client.post("/learning/api/incident", json={"note_id": "idempotency",
            "title": "conflict", "symptom": "a", "root_cause": "b", "fix": "c"}, base_url="https://localhost")
        self.assertEqual(response.status_code, 409)

    def test_suspended_questions_are_not_due(self):
        db.session.add(ReviewProgress(user_id=1, card_id="idempotency:timeout", is_suspended=True))
        db.session.commit()
        self.assertIn(b"3 questions due", self.get(LESSON).data)

    def test_import_rejects_legacy_namespace_collision_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "idempotency.json").write_text('{"id":"idempotency","title":"Legacy","flashcards":[]}')
            with patch.object(learning_service, "notes_dir_for_root", return_value=Path(directory)):
                from marshmallow import ValidationError
                with self.assertRaisesRegex(ValidationError, "reserved by a legacy note"):
                    curriculum_service.import_catalog(self.catalog)
