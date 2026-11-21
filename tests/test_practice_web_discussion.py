"""The workspace's Send, brief, pause/resume, and delete, with CSRF on and foreign keys enforced on SQLite."""
import sqlite3
import unittest
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from project.database import db
from project.learning.forms import BRIEF_ROWS
from project.models import ArtifactRevision, PracticeReceipt, PracticeSession, SessionMessage, SessionMessageArtifact
from project.services import practice_service
from tests.test_practice_service import SENTINELS
from tests.test_practice_web import LESSON, FormFields, PracticeWebCase, as_browser

ARTIFACT_INDEX = {"api": 0, "schema": 1, "algorithm": 2}


class PracticeWorkspaceDiscussionTests(PracticeWebCase):
    def act(self, session_id, fields, action, *, message=None, **bodies):
        data = dict(fields, action=action)
        if message is not None:
            data["message"] = message
        for name, body in bodies.items():
            data[f"artifacts-{ARTIFACT_INDEX[name]}-body"] = body
        return self.post(f"/learning/practice/{session_id}", as_browser(data))

    def page(self, session_id):
        return self.get(f"/learning/practice/{session_id}").get_data(as_text=True)

    def learner_turns(self):
        return [message.body for message in
                SessionMessage.query.filter_by(role="learner", kind="turn").order_by(SessionMessage.sequence)]

    def entries(self, session_id):
        return practice_service.session_detail(1, session_id)["session_brief"]["entries"]

    def test_send_saves_edits_and_shows_the_turn_with_the_revisions_it_cites(self):
        session_id = self.start()
        response = self.act(session_id, self.fields(session_id), "send", message="Should a retry reuse the key?",
                            api="POST /orders")
        self.assertEqual(response.status_code, 303)
        html = self.page(session_id)
        self.assertIn("Message sent. Saved 1 artifact.", html)
        self.assertIn("Should a retry reuse the key?", html)
        self.assertIn(f'href="/learning/practice/{session_id}/artifacts/api/1">API contract revision 1</a>', html)
        citation = SessionMessageArtifact.query.one()
        self.assertEqual(db.session.get(ArtifactRevision, citation.artifact_revision_id).body, "POST /orders")
        fields = FormFields(html).values
        self.assertEqual((fields["message"], fields["expected_sequence"]), ("", "2"))
        # Enter in a field presses the form's first button, which must save rather than send.
        self.assertLess(html.index('name="action" value="save"'), html.index('name="action" value="send"'))
        for hidden in SENTINELS + ("googletagmanager.com", "hotjar"):
            self.assertNotIn(hidden, html)

    def test_saving_with_a_typed_message_keeps_the_draft_unsent(self):
        session_id = self.start()
        response = self.act(session_id, self.fields(session_id), "save", message="DRAFT not sent yet\nsecond line",
                            api="saved text")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Saved 1 artifact. Your message hasn&#39;t been sent.", html)
        fields = FormFields(html).values
        self.assertEqual(fields["message"], "DRAFT not sent yet\nsecond line")
        self.assertEqual(fields["artifacts-0-base_revision"], "1")
        self.assertEqual(self.learner_turns(), [])
        self.assertEqual(self.act(session_id, fields, "send").status_code, 303)
        self.assertEqual(self.learner_turns(), ["DRAFT not sent yet\nsecond line"])

    def test_saving_with_a_message_flags_work_that_arrived_while_writing(self):
        session_id = self.start()
        tab_a, tab_b = self.fields(session_id), self.fields(session_id)
        self.assertEqual(self.act(session_id, tab_a, "save", schema="tab A schema").status_code, 303)
        self.assertEqual(self.act(session_id, self.fields(session_id), "send", message="tab A turn").status_code, 303)
        response = self.act(session_id, tab_b, "save", message="tab B draft", api="tab B api")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Newer work arrived while you were writing", html)
        self.assertIn('<a href="#conversation">New messages arrived</a>', html)
        self.assertIn("Database design was updated elsewhere and is now shown", html)
        self.assertEqual(html.count('<span class="practice-new">New</span>'), 1)
        values = FormFields(html).values
        self.assertEqual((values["message"], values["artifacts-1-body"]), ("tab B draft", "tab A schema"))
        # Having been shown what changed, the learner can send.
        self.assertEqual(self.act(session_id, values, "send").status_code, 303)
        self.assertEqual(self.learner_turns(), ["tab A turn", "tab B draft"])

    def test_a_resent_page_is_based_on_the_saved_work_it_matches(self):
        session_id = self.start()
        fields = dict(self.fields(session_id), **{"brief-0-text": "Keys expire after 24 hours"})
        self.assertEqual(self.act(session_id, fields, "send", message="first", api="v1").status_code, 303)
        # The response was lost; the learner rewords the message and sends the same page again.
        response = self.act(session_id, fields, "send", message="first, reworded", api="v1")
        self.assertEqual(response.status_code, 409)  # that request ID already sent something else
        values = FormFields(response.get_data(as_text=True)).values
        self.assertEqual((values["artifacts-0-base_revision"], values["brief_revision"]), ("1", "1"))
        # So editing the learner's own saved work is not a conflict with it.
        values.update({"artifacts-0-body": "v2", "brief-0-text": "Keys expire after 48 hours", "message": ""})
        saved = self.post(f"/learning/practice/{session_id}", as_browser(dict(values, action="save")))
        self.assertEqual(saved.status_code, 303)
        self.assertEqual([item["text"] for item in self.entries(session_id)], ["Keys expire after 48 hours"])

    def test_an_out_of_date_send_shows_newer_work_and_keeps_edits_and_the_draft(self):
        session_id = self.start()
        tab_a, tab_b = self.fields(session_id), self.fields(session_id)
        self.assertEqual(self.act(session_id, tab_a, "save", schema="tab A schema").status_code, 303)
        response = self.act(session_id, tab_b, "send", message="tab B message", api="tab B api")
        self.assertEqual(response.status_code, 409)
        html = response.get_data(as_text=True)
        self.assertIn("Nothing was sent: this page was out of date.", html)
        self.assertIn("Updated elsewhere: this box now shows saved revision 1.", html)
        values = FormFields(html).values
        self.assertEqual((values["artifacts-1-body"], values["artifacts-1-base_revision"]), ("tab A schema", "1"))
        self.assertEqual((values["artifacts-0-body"], values["message"]), ("tab B api", "tab B message"))
        self.assertEqual((ArtifactRevision.query.count(), self.learner_turns()), (1, []))
        self.assertEqual(self.post(f"/learning/practice/{session_id}",
                                   as_browser(dict(values, action="send"))).status_code, 303)
        detail = practice_service.session_detail(1, session_id)
        self.assertEqual(detail["messages"][-1]["artifact_revisions"],
                         [{"artifact_id": "api", "revision": 1}, {"artifact_id": "schema", "revision": 1}])

    def test_a_send_after_new_turns_shows_them_and_keeps_the_draft(self):
        session_id = self.start()
        tab_a, tab_b = self.fields(session_id), self.fields(session_id)
        self.assertEqual(self.act(session_id, tab_a, "send", message="from tab A").status_code, 303)
        response = self.act(session_id, tab_b, "send", message="from tab B")
        self.assertEqual(response.status_code, 409)
        html = response.get_data(as_text=True)
        self.assertIn('<a href="#conversation">New messages arrived</a>', html)
        self.assertEqual(html.count('<span class="practice-new">New</span>'), 1)
        self.assertLess(html.index("practice-new"), html.index("from tab A"))
        values = FormFields(html).values
        self.assertEqual((values["expected_sequence"], values["message"]), ("2", "from tab B"))
        self.assertEqual(self.post(f"/learning/practice/{session_id}",
                                   as_browser(dict(values, action="send"))).status_code, 303)
        self.assertEqual(self.learner_turns(), ["from tab A", "from tab B"])

    def test_brief_entries_are_added_edited_pinned_and_removed(self):
        self.assertEqual(BRIEF_ROWS, practice_service.BRIEF_MAX_ENTRIES + 3)
        session_id = self.start()
        fields = self.fields(session_id)
        self.assertIn("brief-2-entry_id", fields)
        self.assertNotIn("brief-3-entry_id", fields)  # an empty brief offers three blank rows
        fields.update({"brief-0-kind": "assumption", "brief-0-text": "Keys expire after 24 hours",
                       "brief-1-kind": "question", "brief-1-text": "Which status does a replay return?",
                       "brief-1-pinned": "y"})
        self.assertEqual(self.act(session_id, fields, "save").status_code, 303)
        self.assertIn("Saved your brief.", self.page(session_id))
        self.assertEqual([(item["type"], item["text"], item["pinned"]) for item in self.entries(session_id)],
                         [("assumption", "Keys expire after 24 hours", False),
                          ("question", "Which status does a replay return?", True)])
        fields = self.fields(session_id)
        self.assertNotIn("brief-5-entry_id", fields)  # two saved entries and three blank rows
        fields.update({"brief-0-text": "Keys expire after 48 hours", "brief-1-remove": "y"})
        self.assertEqual(self.act(session_id, fields, "save").status_code, 303)
        self.assertEqual([item["text"] for item in self.entries(session_id)], ["Keys expire after 48 hours"])
        fields = dict(self.fields(session_id), **{"brief-0-text": ""})  # clearing the text drops the entry
        self.assertEqual(self.act(session_id, fields, "save").status_code, 303)
        self.assertEqual(self.entries(session_id), [])
        self.assertEqual(SessionMessage.query.filter_by(kind="brief").count(), 3)

    def test_brief_conflicts_show_both_versions_and_untouched_briefs_refresh(self):
        session_id = self.start()
        tab_a, tab_b, tab_c = self.fields(session_id), self.fields(session_id), self.fields(session_id)
        tab_a["brief-0-text"] = "TAB_A entry"
        self.assertEqual(self.act(session_id, tab_a, "save").status_code, 303)
        tab_b["brief-0-text"] = "TAB_B entry"
        response = self.act(session_id, tab_b, "save")
        self.assertEqual(response.status_code, 409)
        html = response.get_data(as_text=True)
        self.assertIn("Saved elsewhere: brief revision 1", html)
        self.assertIn("TAB_A entry</li>", html)
        values = FormFields(html).values
        self.assertEqual((values["brief-0-text"], values["brief_revision"]), ("TAB_B entry", "1"))
        self.assertEqual(self.post(f"/learning/practice/{session_id}",
                                   as_browser(dict(values, action="save"))).status_code, 303)
        self.assertEqual([item["text"] for item in self.entries(session_id)], ["TAB_B entry"])
        # A tab that never touched its brief saves an artifact and keeps the newer brief.
        self.assertEqual(self.act(session_id, tab_c, "save", api="tab C api").status_code, 303)
        self.assertEqual([item["text"] for item in self.entries(session_id)], ["TAB_B entry"])
        self.assertEqual(SessionMessage.query.filter_by(kind="brief").count(), 2)

    def test_invalid_input_is_explained_beside_the_message_or_brief_and_kept(self):
        session_id = self.start()
        empty = self.act(session_id, self.fields(session_id), "send", message="   ")
        self.assertEqual(empty.status_code, 400)
        self.assertIn('<a href="#message">Your message: Write a message before sending.</a>', empty.get_data(as_text=True))
        attributes = FormFields(empty.get_data(as_text=True)).attributes
        self.assertIn("message-error", attributes["message"]["aria-describedby"].split())
        self.assertIn("message-error", attributes)
        fields = self.fields(session_id)
        fields["brief-0-text"] = "x" * (practice_service.BRIEF_ENTRY_MAX_BYTES + 1)
        long_entry = self.act(session_id, fields, "send", message="KEPT message")
        html = long_entry.get_data(as_text=True)
        self.assertEqual(long_entry.status_code, 400)
        self.assertIn("This brief entry is 2.0 KiB; the limit is 2 KiB.", html)
        self.assertIn('aria-invalid="true"', html)
        attributes = FormFields(html).attributes
        self.assertIn("brief-error", attributes["brief-0-text"]["aria-describedby"].split())
        self.assertIn("brief-error", attributes)
        values = FormFields(html).values
        self.assertEqual((values["message"], len(values["brief-0-text"])), ("KEPT message", 2049))
        expired = self.act(session_id, dict(values, csrf_token="expired"), "send", message="KEPT message")
        self.assertEqual(expired.status_code, 400)
        self.assertIn(b"open too long", expired.data)
        self.assertEqual(FormFields(expired.get_data(as_text=True)).values["message"], "KEPT message")
        self.assertEqual((self.learner_turns(), SessionMessage.query.filter_by(kind="brief").count()), ([], 0))

    def test_pause_and_resume_from_the_workspace(self):
        session_id = self.start()
        self.assertEqual(self.act(session_id, self.fields(session_id), "pause", api="paused work").status_code, 303)
        html = self.page(session_id)
        self.assertIn("Saved 1 artifact. Session paused: resume it from Learning on any device.", html)
        self.assertIn("Practice · Paused", html)
        self.assertIn('value="resume">Resume session</button>', html)
        self.assertNotIn('value="pause"', html)
        home = self.get("/learning/").get_data(as_text=True)
        self.assertIn("Paused", home)
        self.assertIn(f'href="/learning/practice/{session_id}"', home)
        self.assertEqual(self.act(session_id, self.fields(session_id), "resume").status_code, 303)
        html = self.page(session_id)
        self.assertIn("Session resumed.", html)
        self.assertIn("Practice · In progress", html)
        self.act(session_id, self.fields(session_id), "pause")
        self.assertEqual(self.act(session_id, self.fields(session_id), "save", api="saving resumes").status_code, 303)
        self.assertEqual(db.session.get(PracticeSession, session_id).status, "active")
        self.assertEqual(PracticeReceipt.query.filter_by(operation="pause").count(), 2)

    def test_delete_asks_first_then_removes_the_session(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="a message", api="some work")
        path = f"/learning/practice/{session_id}/delete"
        page = self.get(path)
        html = page.get_data(as_text=True)
        self.assertEqual((page.status_code, page.headers["Cache-Control"]), (200, "private, no-store"))
        for text in ("There is no undo.", "2 messages", "0 saved versions", "1 saved revision", "backups"):
            self.assertIn(text, html)
        self.assertIn('href="#learning-main"', html)
        self.assertIn('id="learning-main" tabindex="-1"', html)
        self.assertIn('class="learning-shell-header', html)
        self.assertNotIn('class="Header', html)
        self.assertNotIn("googletagmanager.com", html)
        token = FormFields(html).values["csrf_token"]
        expired = self.post(path, {"csrf_token": "forged"})
        self.assertEqual(expired.status_code, 400)
        self.assertIn(b"Nothing was deleted", expired.data)
        self.assertEqual(PracticeSession.query.count(), 1)
        deleted = self.post(path, {"csrf_token": token})
        self.assertEqual((deleted.status_code, deleted.headers["Location"]), (303, LESSON))
        lesson = self.get(LESSON).get_data(as_text=True)
        self.assertIn("Practice session deleted.", lesson)
        self.assertNotIn("Resume the session", lesson)
        for model in (PracticeSession, ArtifactRevision, SessionMessage, SessionMessageArtifact, PracticeReceipt):
            self.assertEqual(model.query.count(), 0, model.__tablename__)
        repeated = self.post(path, {"csrf_token": token})
        self.assertEqual((repeated.status_code, repeated.headers["Location"]), (303, "/learning/"))
        self.assertIn("doesn&#39;t exist or was already deleted", self.get("/learning/").get_data(as_text=True))
        self.assertEqual((self.get(path).status_code, self.get(f"/learning/practice/{session_id}").status_code),
                         (404, 404))

    def test_other_accounts_cannot_send_pause_or_delete(self):
        session_id = self.start()
        fields = self.fields(session_id)
        self.login(2)
        token = FormFields(self.get(LESSON).get_data(as_text=True)).values["csrf_token"]
        self.assertEqual(self.get(f"/learning/practice/{session_id}/delete").status_code, 404)
        refused = self.post(f"/learning/practice/{session_id}/delete", {"csrf_token": token})
        self.assertEqual(refused.headers["Location"], "/learning/")  # the same answer as a missing session
        for action in ("send", "pause"):
            response = self.act(session_id, dict(fields, csrf_token=token), action, message="intrusion")
            self.assertEqual(response.status_code, 404)
        self.assertEqual((PracticeSession.query.one().status, self.learner_turns()), ("active", []))

    def database_failure(self, operation, *, commit_first=False):
        """Make `operation` fail like a lost connection: before saving, or after committing."""
        blocked = {"on": False}
        real = getattr(practice_service, operation)

        def refuse(*_args):
            if blocked["on"]:
                raise sqlite3.OperationalError("fixture: database unavailable")

        def fail(*args, **kwargs):
            if commit_first:
                real(*args, **kwargs)
            blocked["on"] = True
            raise OperationalError("UPDATE user", {}, sqlite3.OperationalError("fixture: database unavailable"))
        return blocked, refuse, fail

    def test_a_failed_send_keeps_the_message_and_brief_for_a_retry(self):
        for commit_first in (False, True):
            with self.subTest(commit_first=commit_first):
                session_id = self.start()
                fields = dict(self.fields(session_id), **{"brief-0-text": "RESCUE_BRIEF entry", "brief-0-pinned": "y"})
                blocked, refuse, fail = self.database_failure("save_and_send", commit_first=commit_first)
                event.listen(db.engine, "before_cursor_execute", refuse)
                try:
                    with patch.object(practice_service, "save_and_send", side_effect=fail), \
                            self.assertLogs("project", level="ERROR") as logs:
                        response = self.act(session_id, fields, "send", message="RESCUE_MESSAGE", api="RESCUE_API")
                finally:
                    blocked["on"] = False
                    event.remove(db.engine, "before_cursor_execute", refuse)
                self.assertEqual(response.status_code, 503)
                html = response.get_data(as_text=True)
                self.assertIn('name="action" value="send">Try sending again</button>', html)
                rescued = FormFields(html).values
                self.assertEqual((rescued["message"], rescued["brief-0-text"], rescued["brief-0-pinned"],
                                  rescued["artifacts-0-body"], rescued["request_id"]),
                                 ("RESCUE_MESSAGE", "RESCUE_BRIEF entry", "y", "RESCUE_API", fields["request_id"]))
                self.assertFalse(any(sentinel in "\n".join(logs.output)
                                     for sentinel in ("RESCUE_MESSAGE", "RESCUE_BRIEF", "RESCUE_API")))
                retry = self.post(f"/learning/practice/{session_id}", as_browser(dict(rescued, action="send")))
                self.assertEqual(retry.status_code, 303)
                detail = practice_service.session_detail(1, session_id)
                self.assertEqual([turn["body"] for turn in detail["messages"][1:]], ["RESCUE_MESSAGE"])
                self.assertEqual([(item["text"], item["pinned"]) for item in detail["session_brief"]["entries"]],
                                 [("RESCUE_BRIEF entry", True)])


if __name__ == "__main__":
    unittest.main()
