"""Read-only mode navigation and review attempts retain an owned practice session."""
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.models import ArtifactRevision, PracticeReceipt, PracticeSession, ReviewLog, ReviewReceipt, User
from project.services import concept_progress_service, learning_service, practice_service
from tests.test_concept_web import FormInputs
from tests.test_practice_service import SENTINELS
from tests.test_practice_web import PracticeWebCase

LESSON = "/learning/concepts/idempotency"
REVIEW = LESSON + "/review"


class ModeLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.active, self.link, self.links = False, None, {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "Concept views":
            self.active = True
        if self.active and tag == "a":
            self.link = dict(attrs, text="")

    def handle_data(self, data):
        if self.link is not None:
            self.link["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.link is not None:
            self.links[self.link.pop("text").strip()] = self.link
            self.link = None
        if tag == "nav":
            self.active = False


class ConceptWorkspaceTests(PracticeWebCase):
    def setUp(self):
        super().setUp()
        concept_progress_service.enroll(1, "idempotency")

    def counts(self):
        return tuple(model.query.count() for model in
            (PracticeSession, PracticeReceipt, ArtifactRevision, ReviewLog, ReviewReceipt))

    def review_attempt(self, session_id):
        path = REVIEW + "?" + urlencode(dict(practice_session=session_id))
        question = self.get(path)
        self.assertEqual(question.status_code, 200)
        fields = FormInputs(question.get_data(as_text=True)).values
        revealed = self.get(REVIEW + "?" + urlencode(fields))
        self.assertEqual(revealed.status_code, 200)
        return FormInputs(revealed.get_data(as_text=True)).values

    def test_all_modes_share_navigation_without_starting_practice_on_get(self):
        before = self.counts()
        for path, mode in ((LESSON, "Learn"), (REVIEW, "Review"),
            (LESSON + "/practice?view=discuss", "Discuss"), (LESSON + "/practice?view=build", "Build")):
            page = self.get(path)
            self.assertEqual(page.status_code, 200)
            links = ModeLinks(page.get_data(as_text=True)).links
            self.assertEqual(set(links), {"Learn", "Review", "Discuss", "Build"})
            self.assertEqual(links[mode]["aria-current"], "page")
            self.assertIn(b'class="learning-shell-header concept-shell-header"', page.data)
            for private in SENTINELS:
                self.assertNotIn(private.encode(), page.data)
        self.assertEqual(before, self.counts())

    def test_explicit_older_session_survives_learn_review_and_practice_links(self):
        older, newer = self.start(), self.start()
        before = self.counts()
        for path in (LESSON, REVIEW):
            with patch.object(practice_service, "session_detail", side_effect=AssertionError("loaded transcript")):
                page = self.get(path + "?practice_session=" + older)
            links = ModeLinks(page.get_data(as_text=True)).links
            for mode in ("Learn", "Review"):
                self.assertEqual(parse_qs(urlsplit(links[mode]["href"]).query)["practice_session"], [older])
            for mode in ("Discuss", "Build"):
                self.assertEqual(urlsplit(links[mode]["href"]).path, "/learning/practice/" + older)
            self.assertNotIn(newer, str(links))
        page = self.get("/learning/practice/" + older)
        self.assertIn("practice_session=" + older, ModeLinks(page.get_data(as_text=True)).links["Learn"]["href"])
        self.assertEqual(before, self.counts())

    def test_default_navigation_selects_latest_open_session_and_does_not_resume_it(self):
        self.start()
        newest = self.start()
        practice_service.set_status(db.session.get(User, 1),
            newest, status="paused", request_id=str(uuid4()))
        links = ModeLinks(self.get(LESSON).get_data(as_text=True)).links
        self.assertEqual(urlsplit(links["Discuss"]["href"]).path, "/learning/practice/" + newest)
        response = self.get(LESSON + "/practice?view=build")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], links["Build"]["href"])
        self.assertEqual(db.session.get(PracticeSession, newest).status, "paused")

    def test_foreign_missing_malformed_and_mismatched_sessions_are_rejected(self):
        owned = self.start()
        self.login(2)
        foreign = self.start()
        self.login(1)
        for session_id in (foreign, str(uuid4()), "not-a-uuid", ""):
            for path in (LESSON, REVIEW, LESSON + "/practice"):
                self.assertEqual(self.get(path + "?practice_session=" + session_id).status_code, 404)
        summary = practice_service.session_summary(1, owned)
        with patch.object(practice_service, "session_summary", return_value=dict(summary, concept_id="other-concept")):
            self.assertEqual(self.get(LESSON + "?practice_session=" + owned).status_code, 404)
        values = self.review_attempt(owned)
        before = self.counts()
        response = self.post(REVIEW, dict(values, rating="4", practice_session=foreign))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(before, self.counts())

    def test_review_reveal_rating_replay_and_stale_attempt_keep_session_context(self):
        session_id = self.start()
        self.start()
        values = self.review_attempt(session_id)
        self.assertEqual(values["practice_session"], session_id)
        self.assertEqual(ReviewLog.query.count(), 0)
        for _ in range(2):
            response = self.post(REVIEW, dict(values, rating="4"))
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["Location"], REVIEW + "?practice_session=" + session_id)
        self.assertEqual(ReviewLog.query.count(), 1)
        stale = self.post(REVIEW, dict(values, rating="4", request_id=str(uuid4())))
        self.assertEqual(stale.status_code, 409)
        self.assertIn(session_id, ModeLinks(stale.get_data(as_text=True)).links["Build"]["href"])

    def test_failed_rating_retains_attempt_and_session_for_retry(self):
        session_id = self.start()
        values = self.review_attempt(session_id)
        saved = concept_progress_service.progress(1, "idempotency")
        with patch.object(learning_service, "rate_card_for_user", side_effect=SQLAlchemyError("fixture")), \
                patch.object(concept_progress_service, "progress", side_effect=[saved, AssertionError("read after save failure")]), \
                self.assertLogs("project", level="ERROR"):
            response = self.post(REVIEW, dict(values, rating="4"))
        self.assertEqual(response.status_code, 503)
        retry = FormInputs(response.get_data(as_text=True)).values
        self.assertEqual(retry["practice_session"], session_id)
        self.assertEqual(retry["request_id"], values["request_id"])
        self.assertEqual(self.post(REVIEW, dict(retry, rating="4")).status_code, 303)
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_practice_entry_start_requires_csrf_and_preserves_requested_view(self):
        page = self.get(LESSON + "/practice?view=build")
        fields = FormInputs(page.get_data(as_text=True)).values
        self.assertEqual(self.post("/learning/practice?view=build", dict(fields, csrf_token="")).status_code, 400)
        self.assertEqual(self.post("/learning/practice?view=other", fields).status_code, 400)
        self.assertEqual(PracticeSession.query.count(), 0)
        first = self.post("/learning/practice?view=build", fields)
        replay = self.post("/learning/practice?view=build", fields)
        self.assertEqual(first.status_code, 303)
        self.assertEqual(first.headers["Location"], replay.headers["Location"])
        self.assertEqual(parse_qs(urlsplit(first.headers["Location"]).query), {"view": ["build"]})
        self.assertEqual(PracticeSession.query.count(), 1)

    def test_feature_off_navigation_never_queries_practice(self):
        self.app.config["LEARNING_PRACTICE_ENABLED"] = False
        with patch.object(practice_service, "list_sessions", side_effect=AssertionError("practice query")), \
             patch.object(practice_service, "session_summary", side_effect=AssertionError("practice query")):
            for path in (LESSON, REVIEW):
                page = self.get(path + "?practice_session=" + str(uuid4()))
                self.assertEqual(page.status_code, 200)
                self.assertEqual(set(ModeLinks(page.get_data(as_text=True)).links), {"Learn", "Review"})
            self.assertEqual(self.get(LESSON + "/practice").status_code, 404)
