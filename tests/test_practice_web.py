"""The practice workspace website routes, with CSRF on and foreign keys enforced on SQLite."""
from html.parser import HTMLParser
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from flask import g
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, OperationalError

from project import create_app
from project.database import db
from project.learning.forms import PracticeWorkspaceForm
from project.models import ArtifactRevision, PracticeSession, User
from project.services import practice_service
from tests.test_practice_service import EXERCISE, SENTINELS, enable_sqlite_foreign_keys, seed_catalog

LESSON = "/learning/concepts/idempotency"


class FormFields(HTMLParser):
    """Collect the values a browser would submit, including textarea text and selections."""

    def __init__(self, html):
        super().__init__()
        self.values, self._textarea, self._select = {}, None, None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        name = attrs.get("name")
        if tag == "input" and name:
            self.values[name] = attrs.get("value", "")
        elif tag == "textarea" and name:
            self._textarea, self.values[name] = name, ""
        elif tag == "select" and name:
            self._select = name
        elif tag == "option" and self._select and (self._select not in self.values or "selected" in attrs):
            self.values[self._select] = attrs.get("value", "")

    def handle_data(self, data):
        if self._textarea:
            self.values[self._textarea] += data

    def handle_endtag(self, tag):
        if tag == "textarea" and self._textarea:
            value = self.values[self._textarea]
            # Browsers drop one newline directly after <textarea>; WTForms writes one for that reason.
            if value.startswith("\r\n"):
                value = value[2:]
            elif value.startswith("\n"):
                value = value[1:]
            self.values[self._textarea] = value
            self._textarea = None
        elif tag == "select":
            self._select = None


def as_browser(values):
    """Browsers submit textarea line breaks as CRLF."""
    return {name: value.replace("\r\n", "\n").replace("\n", "\r\n") if name.endswith("-body") else value
            for name, value in values.items()}


class PracticeWebTests(unittest.TestCase):
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
        self.login(1)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        event.remove(db.engine, "connect", enable_sqlite_foreign_keys)
        db.engine.dispose()
        self.context.pop()

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        g.pop("_login_user", None)

    def get(self, path):
        return self.client.get(path, base_url="https://localhost")

    def post(self, path, data):
        return self.client.post(path, data=data, base_url="https://localhost")

    def start(self):
        form = FormFields(self.get(LESSON).get_data(as_text=True)).values
        response = self.post("/learning/practice", {key: form[key] for key in
                                                    ("csrf_token", "exercise_id", "concept_id", "request_id")})
        self.assertEqual(response.status_code, 303)
        return response.headers["Location"].rsplit("/", 1)[-1]

    def fields(self, session_id):
        response = self.get(f"/learning/practice/{session_id}")
        self.assertEqual(response.status_code, 200)
        return FormFields(response.get_data(as_text=True)).values

    def save(self, session_id, fields, **bodies):
        data = dict(fields)
        for index, name in enumerate(("api", "schema", "algorithm")):
            if name in bodies:
                data[f"artifacts-{index}-body"] = bodies[name]
        return self.post(f"/learning/practice/{session_id}", as_browser(data))

    def test_practice_is_absent_when_the_flag_is_off(self):
        session_id = self.start()
        self.app.config["LEARNING_PRACTICE_ENABLED"] = False
        with patch.object(practice_service, "list_sessions", side_effect=AssertionError("queried")), \
                patch.object(practice_service, "concept_exercises", side_effect=AssertionError("queried")):
            self.assertNotIn(b"Apply it", self.get(LESSON).data)
            self.assertNotIn(b"Continue practising", self.get("/learning/").data)
        self.assertEqual(self.get(f"/learning/practice/{session_id}").status_code, 404)
        self.assertEqual(self.post("/learning/practice", {}).status_code, 404)
        self.assertEqual(self.get(f"/api/v1/learning/practice/sessions/{session_id}").status_code, 404)

    def test_anonymous_visitors_are_sent_to_sign_in(self):
        session_id = self.start()
        with self.client.session_transaction() as session:
            session.clear()
        g.pop("_login_user", None)  # the outer app context would otherwise keep the signed-in user
        for response in (self.get(f"/learning/practice/{session_id}"), self.post("/learning/practice", {})):
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.headers["Location"])

    def test_start_from_the_lesson_then_resume_from_learning(self):
        lesson = self.get(LESSON)
        self.assertIn(b"Apply it", lesson.data)
        start = FormFields(lesson.get_data(as_text=True)).values
        start_fields = {key: start[key] for key in ("csrf_token", "exercise_id", "concept_id", "request_id")}
        first = self.post("/learning/practice", start_fields)
        self.assertEqual(self.post("/learning/practice", start_fields).headers["Location"], first.headers["Location"])
        self.assertEqual(PracticeSession.query.count(), 1)
        session_id = first.headers["Location"].rsplit("/", 1)[-1]
        page = self.get(f"/learning/practice/{session_id}")
        self.assertEqual(page.headers["Cache-Control"], "private, no-store")
        html = page.get_data(as_text=True)
        self.assertIn("How would you begin scoping this API?", html)
        self.assertIn("Design a retry-safe order API", html)
        for hidden in SENTINELS + ("googletagmanager.com", "hotjar", "marked.umd.js"):
            self.assertNotIn(hidden, html)
        self.assertIn(f"/learning/practice/{session_id}", self.get("/learning/").get_data(as_text=True))
        self.assertIn(b"Resume the session", self.get(LESSON).data)

    def test_saves_unchanged_saves_and_history(self):
        session_id = self.start()
        saved = self.save(session_id, self.fields(session_id), api="POST /orders\nIdempotency-Key: required")
        self.assertEqual(saved.status_code, 303)
        page = self.get(f"/learning/practice/{session_id}").get_data(as_text=True)
        self.assertIn("Saved 1 artifact.", page)
        self.assertIn("Saved revision 1", page)
        again = self.save(session_id, self.fields(session_id))
        self.assertEqual(again.status_code, 303)
        self.assertIn("No changes to save", self.get(f"/learning/practice/{session_id}").get_data(as_text=True))
        self.assertEqual(ArtifactRevision.query.count(), 1)
        history = self.get(f"/learning/practice/{session_id}/artifacts/api").get_data(as_text=True)
        self.assertIn("Revision 1", history)
        revision = self.get(f"/learning/practice/{session_id}/artifacts/api/1").get_data(as_text=True)
        self.assertIn("Idempotency-Key: required", revision)
        self.assertIn("(current)", revision)
        for path in ("artifacts/api/2", "artifacts/unknown", "artifacts/api/0"):
            self.assertEqual(self.get(f"/learning/practice/{session_id}/{path}").status_code, 404)

    def test_a_repeated_post_after_a_lost_response_saves_once(self):
        session_id = self.start()
        fields = self.fields(session_id)
        self.assertEqual(self.save(session_id, fields, api="first attempt").status_code, 303)
        self.assertEqual(self.save(session_id, fields, api="first attempt").status_code, 303)
        self.assertEqual(ArtifactRevision.query.count(), 1)

    def test_two_tabs_conflict_without_losing_either_text(self):
        session_id = self.start()
        tab_a, tab_b = self.fields(session_id), self.fields(session_id)
        self.assertEqual(self.save(session_id, tab_a, api="TAB_A text").status_code, 303)
        conflict = self.save(session_id, tab_b, api="TAB_B text", schema="TAB_B schema")
        self.assertEqual(conflict.status_code, 409)
        html = conflict.get_data(as_text=True)
        self.assertIn("Saved elsewhere: revision 1", html)
        rerendered = FormFields(html).values
        self.assertEqual(rerendered["artifacts-0-body"], "TAB_B text")
        self.assertEqual(rerendered["artifacts-1-body"], "TAB_B schema")
        self.assertEqual(rerendered["artifacts-0-base_revision"], "1")
        self.assertIn("TAB_A text</pre>", html)
        self.assertEqual(ArtifactRevision.query.count(), 1)
        self.assertEqual(self.post(f"/learning/practice/{session_id}", as_browser(rerendered)).status_code, 303)
        bodies = {(row.artifact_id, row.revision): row.body for row in ArtifactRevision.query.all()}
        self.assertEqual(bodies, {("api", 1): "TAB_A text", ("api", 2): "TAB_B text", ("schema", 1): "TAB_B schema"})

    def test_an_untouched_artifact_refreshes_instead_of_conflicting(self):
        session_id = self.start()
        tab_a, tab_b = self.fields(session_id), self.fields(session_id)
        self.save(session_id, tab_a, api="tab A api", schema="tab A schema")
        conflict = self.save(session_id, tab_b, api="tab B api")  # tab B never touched the schema
        rerendered = FormFields(conflict.get_data(as_text=True)).values
        self.assertEqual((rerendered["artifacts-1-body"], rerendered["artifacts-1-base_revision"]), ("tab A schema", "1"))
        self.assertEqual(rerendered["artifacts-0-body"], "tab B api")

    def test_rejected_csrf_keeps_the_learners_text(self):
        self.assertEqual(PracticeWorkspaceForm.Meta.csrf_time_limit, 86400)
        session_id = self.start()
        fields = dict(self.fields(session_id), csrf_token="expired-or-forged")
        response = self.save(session_id, fields, api="UNSAVED_SENTINEL draft")
        self.assertEqual(response.status_code, 400)
        rerendered = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(rerendered["artifacts-0-body"], "UNSAVED_SENTINEL draft")
        self.assertNotEqual(rerendered["csrf_token"], "expired-or-forged")
        self.assertIn(b"open too long", response.data)
        self.assertEqual(ArtifactRevision.query.count(), 0)
        self.assertEqual(self.post(f"/learning/practice/{session_id}", as_browser(rerendered)).status_code, 303)

    def test_invalid_text_is_explained_and_kept(self):
        session_id = self.start()
        too_big = "x" * (practice_service.ARTIFACT_MAX_BYTES + 10)
        for body, message in ((too_big, b"the limit is 64 KiB"), ("a\x00b", b"NUL character")):
            with self.subTest(message=message):
                response = self.save(session_id, self.fields(session_id), schema=body)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.data)
                # Returned exactly as submitted (a browser displays a NUL as U+FFFD).
                self.assertEqual(FormFields(response.get_data(as_text=True)).values["artifacts-1-body"], body)
        tampered = dict(self.fields(session_id), **{"artifacts-1-language": "json"})
        self.assertEqual(self.save(session_id, tampered, schema="x").status_code, 400)
        self.assertEqual(ArtifactRevision.query.count(), 0)

    def test_line_endings_and_a_leading_newline_round_trip_unchanged(self):
        session_id = self.start()
        self.save(session_id, self.fields(session_id), algorithm="\nfirst line\nsecond line\n")
        self.assertEqual(ArtifactRevision.query.one().body, "\nfirst line\nsecond line\n")
        fields = self.fields(session_id)
        self.assertEqual(fields["artifacts-2-body"], "\nfirst line\nsecond line\n")
        self.save(session_id, fields)
        self.assertIn("No changes to save", self.get(f"/learning/practice/{session_id}").get_data(as_text=True))
        self.assertEqual(ArtifactRevision.query.count(), 1)

    def test_database_failure_shows_the_text_without_touching_the_database(self):
        session_id = self.start()
        fields = self.fields(session_id)
        blocked = {"on": False}

        def refuse(*_args):
            if blocked["on"]:
                raise sqlite3.OperationalError("fixture: database unavailable")

        def fail(*_args, **_kwargs):
            blocked["on"] = True
            raise OperationalError("UPDATE user", {}, sqlite3.OperationalError("fixture: database unavailable"))

        event.listen(db.engine, "before_cursor_execute", refuse)
        try:
            with patch.object(practice_service, "save_work", side_effect=fail), \
                    self.assertLogs("project", level="ERROR") as logs:
                response = self.save(session_id, fields, api="RESCUE_SENTINEL text")
        finally:
            blocked["on"] = False
            event.remove(db.engine, "before_cursor_execute", refuse)
        self.assertEqual(response.status_code, 503)
        rescued = FormFields(response.get_data(as_text=True)).values
        self.assertEqual(rescued["artifacts-0-body"], "RESCUE_SENTINEL text")
        self.assertEqual(rescued["request_id"], fields["request_id"])  # unknown outcome: retry the same ID
        self.assertNotIn("RESCUE_SENTINEL", "\n".join(logs.output))
        self.assertIn("OperationalError", "\n".join(logs.output))
        self.assertEqual(self.post(f"/learning/practice/{session_id}", as_browser(rescued)).status_code, 303)
        self.assertEqual(ArtifactRevision.query.one().body, "RESCUE_SENTINEL text")

    def test_a_definite_database_error_gets_a_new_request_id(self):
        session_id = self.start()
        fields = self.fields(session_id)
        error = IntegrityError("INSERT", {}, sqlite3.IntegrityError("fixture"))
        with patch.object(practice_service, "save_work", side_effect=error), self.assertLogs("project", "ERROR"):
            response = self.save(session_id, fields, api="kept text")
        rescued = FormFields(response.get_data(as_text=True)).values
        self.assertEqual((response.status_code, rescued["artifacts-0-body"]), (503, "kept text"))
        self.assertNotEqual(rescued["request_id"], fields["request_id"])

    def test_other_accounts_get_not_found(self):
        session_id = self.start()
        fields = self.fields(session_id)
        self.save(session_id, fields, api="private")
        self.login(2)
        for response in (self.get(f"/learning/practice/{session_id}"),
                         self.get(f"/learning/practice/{session_id}/artifacts/api"),
                         self.get(f"/learning/practice/{session_id}/artifacts/api/1"),
                         self.get(f"/learning/practice/{uuid4()}"),
                         self.get("/learning/practice/not-a-session")):
            self.assertEqual(response.status_code, 404)
        lesson = FormFields(self.get(LESSON).get_data(as_text=True)).values
        stolen = dict(fields, csrf_token=lesson["csrf_token"])
        self.assertEqual(self.save(session_id, stolen, api="intrusion").status_code, 404)
        self.assertNotIn(b"Continue practising", self.get("/learning/").data)
        self.assertEqual(ArtifactRevision.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
