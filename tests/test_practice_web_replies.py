"""The workspace's reply states, polling endpoint, and reply actions, with CSRF on and the scripted provider."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from flask import g

from project.database import db
from project.models import AIRequest, ArtifactRevision, LearningAICharge
from project.services import practice_budget, practice_service, practice_worker
from project.services.practice_worker import FakeProvider
from tests.test_practice_web import FormFields, PracticeWebCase, as_browser

AI_CONFIG = dict(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="fixture1@example.test")


class PracticeWebReplyTests(PracticeWebCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(AI_CONFIG)
        self.user = db.session.get(practice_service.User, 1)
        self.user.email_verified = True
        db.session.commit()

    def act(self, session_id, fields, action, *, message=None, **bodies):
        data = dict(fields, action=action)
        if message is not None:
            data["message"] = message
        for index, name in enumerate(("api", "schema", "algorithm")):
            if name in bodies:
                data[f"artifacts-{index}-body"] = bodies[name]
        return self.post(f"/learning/practice/{session_id}", as_browser(data))

    def page(self, session_id):
        return self.get(f"/learning/practice/{session_id}").get_data(as_text=True)

    def poll(self, session_id, after):
        return self.get(f"/learning/practice/{session_id}/reply?after={after}")

    def work(self, provider=None):
        with self.app.app_context():
            result = practice_worker.run_once(provider or FakeProvider())
        g.pop("_login_user", None)
        return result

    def test_a_sent_message_shows_the_reply_coming_then_the_reply(self):
        session_id = self.start()
        self.assertEqual(self.act(session_id, self.fields(session_id), "send", message="Do keys expire?",
                                  api="POST /orders").status_code, 303)
        html = self.page(session_id)
        self.assertIn("The interviewer is replying", html)
        self.assertIn("data-reply-live", html)
        self.assertIn('value="send" disabled>Send message', html)
        self.assertTrue(self.work(FakeProvider(replies=["What scope does a key have?"])))
        html = self.page(session_id)  # nothing polled meanwhile: the reply was waiting
        self.assertIn("What scope does a key have?", html)
        self.assertIn(f'href="/learning/practice/{session_id}/artifacts/api/1">API contract revision 1</a>', html)
        self.assertIn("Reviewed", html)
        self.assertNotIn("data-reply-live", html)
        self.assertNotIn('value="send" disabled', html)

    def test_polling_returns_the_status_and_every_newer_turn(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="Do keys expire?")
        pending = self.poll(session_id, 1)
        self.assertEqual((pending.status_code, pending.headers["Cache-Control"]), (200, "private, no-store"))
        data = pending.get_json()
        self.assertEqual((data["reply"], data["latest_sequence"]), ({"status": "pending", "live": True}, 2))
        self.assertEqual([turn["sequence"] for turn in data["turns"]], [2])
        self.assertIn("The interviewer is replying", data["status_html"])
        self.work()
        done = self.poll(session_id, 2).get_json()
        self.assertEqual((done["reply"], done["latest_sequence"]), ({"status": "completed", "live": False}, 3))
        self.assertIn('<span class="practice-new">New</span>', done["turns"][0]["html"])
        self.assertIn("The interviewer replied.", done["status_html"])
        self.assertEqual(self.poll(session_id, 3).get_json()["turns"], [])
        for after in ("", "-1", "x", "1.5", "+1", "2147483648"):
            response = self.get(f"/learning/practice/{session_id}/reply?after={after}")
            self.assertEqual((response.status_code, response.is_json), (400, True))
        self.login(2)
        self.assertEqual(self.poll(session_id, 0).status_code, 404)
        self.app.config["LEARNING_PRACTICE_ENABLED"] = False
        self.assertEqual(self.poll(session_id, 0).status_code, 404)

    def test_a_live_reply_refuses_another_send_and_keeps_the_draft(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="first")
        response = self.act(session_id, self.fields(session_id), "send", message="DRAFT_SENTINEL second")
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"The interviewer is still replying", response.data)
        self.assertEqual(FormFields(response.get_data(as_text=True)).values["message"], "DRAFT_SENTINEL second")

    def test_asking_and_retrying_also_save_the_page(self):
        session_id = self.start()
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):
            self.act(session_id, self.fields(session_id), "send", message="sent while AI was off")
            self.assertIn("AI replies are turned off right now.", self.page(session_id))
        html = self.page(session_id)
        self.assertIn('value="reply">Ask for a reply</button>', html)
        asked = self.act(session_id, FormFields(html).values, "reply", api="saved with the request")
        self.assertEqual(asked.status_code, 303)
        self.assertIn("Asked the interviewer for a reply. Saved 1 artifact.", self.page(session_id))
        self.assertEqual(ArtifactRevision.query.one().body, "saved with the request")
        with self.assertLogs("project", "WARNING"):
            self.work(FakeProvider("fail"))
        html = self.page(session_id)
        self.assertIn("The interviewer couldn&#39;t reply.", html)
        self.assertEqual(self.act(session_id, FormFields(html).values, "reply").status_code, 303)
        self.assertEqual(AIRequest.query.filter_by(status="pending").count(), 1)

    def test_the_owner_sees_spending_and_others_see_why_nothing_replies(self):
        session_id = self.start()
        self.app.config.update(LEARNING_AI_MONTHLY_CAP_USD=0.05, LEARNING_AI_WARN_USD=0.01)
        db.session.add(LearningAICharge(
            user_id=1, reply_id=str(uuid4()), purpose="reply", period=practice_budget.period(practice_service._now()),
            provider="fake", model="fake-interviewer", service_tier="default", pricing_version="fake-1",
            state="settled", reserved_microusd=12_000, cost_microusd=12_000, expires_at=practice_service._now(),
            created_at=practice_service._now()))
        db.session.commit()
        self.assertIn("AI spending this month: $0.01 of $0.05.", self.page(session_id))
        with patch.object(practice_service, "_reply_obstacle", return_value=("budget", None)):  # its worst case doesn't fit
            self.act(session_id, self.fields(session_id), "send", message="too costly to answer")
            self.assertIn("This month&#39;s AI budget has no room for another reply, so replies resume next month. "
                          "Your messages are still saved.", self.page(session_id))
        self.app.config["LEARNING_AI_MONTHLY_CAP_USD"] = 0.02  # not even the smallest reply fits
        self.assertIn("This month's AI budget is used up", self.page(session_id))
        self.app.config["LEARNING_AI_WARN_USD"] = 0.015  # used up before the warning line is reached
        self.assertIn("This month's AI budget is used up", self.page(session_id))
        self.login(2)
        other = self.start()
        self.act(other, self.fields(other), "send", message="hello")
        html = self.page(other)
        self.assertIn("AI replies aren&#39;t available for this account.", html)
        self.assertNotIn("AI spending", html)

    def test_the_last_poll_reports_the_newest_turn(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="first")
        self.work()
        done = self.poll(session_id, 3).get_json()  # the page already shows the reply (turn 3)
        self.assertEqual((done["turns"], done["reply"]["live"]), ([], False))
        self.assertIn("The interviewer replied.", done["status_html"])  # still announced
        self.act(session_id, self.fields(session_id), "send", message="from another device")
        with self.assertLogs("project", "WARNING"):
            self.work(FakeProvider("fail"))
        caught_up = self.poll(session_id, 2).get_json()  # a page that saw neither the reply nor turn 4
        self.assertEqual([turn["sequence"] for turn in caught_up["turns"]], [3, 4])
        self.assertNotIn("The interviewer replied.", caught_up["status_html"])
        self.assertIn("The interviewer couldn&#39;t reply.", caught_up["status_html"])
        self.assertIn('value="reply">Retry the reply</button>', caught_up["status_html"])

    def test_retrying_after_the_reply_arrived_saves_and_says_so(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="Do keys expire?")
        with self.assertLogs("project", "WARNING"):
            self.work(FakeProvider("fail"))
        stale = FormFields(self.page(session_id)).values  # this tab offers Retry...
        self.act(session_id, self.fields(session_id), "reply")  # ...while another tab retries
        self.work()
        response = self.act(session_id, stale, "reply", api="saved anyway")
        self.assertEqual(response.status_code, 303)
        html = self.page(session_id)
        self.assertIn("The interviewer has already replied. Saved 1 artifact.", html)
        self.assertEqual(ArtifactRevision.query.one().body, "saved anyway")
        self.assertEqual(AIRequest.query.filter_by(status="completed").count(), 1)

    def test_asking_with_a_typed_message_still_says_it_asked(self):
        session_id = self.start()
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):
            self.act(session_id, self.fields(session_id), "send", message="sent while AI was off")
        fields = self.fields(session_id)
        practice_service.save_work(self.user, session_id, request_id=str(uuid4()), edits=[
            {"artifact_id": "api", "base_revision": 0, "language": "text", "body": "from another device"}])
        response = self.act(session_id, fields, "reply", message="DRAFT_SENTINEL not sent yet")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Asked the interviewer for a reply. Newer work arrived while you were writing",
                      response.get_data(as_text=True))

    def test_each_reply_problem_reads_plainly_with_a_retry(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="Do keys expire?")
        request = AIRequest.query.one()
        for status, code, text in (("interrupted", "not_started", "The reply didn&#39;t start."),
                                   ("interrupted", "lease_expired", "The reply was interrupted."),
                                   ("failed", "timeout", "The interviewer didn&#39;t answer in time."),
                                   ("failed", "invalid_output", "The interviewer&#39;s reply couldn&#39;t be used."),
                                   ("cancelled", "paused", "The reply was cancelled when you paused."),
                                   ("failed", "provider", "The interviewer couldn&#39;t reply.")):
            with self.subTest(code=code):
                request.status, request.error_code = status, code
                db.session.commit()
                html = self.page(session_id)
                self.assertIn(text, html)
                self.assertIn('value="reply">Retry the reply</button>', html)
                self.assertNotIn("data-reply-live", html)

    def test_revealed_requirements_and_hints_show_where_they_came_from(self):
        session_id = self.start()
        self.assertIn("None yet. The interviewer reveals more when you ask", self.page(session_id))
        self.act(session_id, self.fields(session_id), "send", message="Who owns the key?")
        polled = self.poll(session_id, 2).get_json()
        self.assertNotIn("HIDDEN_SENTINEL", polled["revealed_html"])  # nothing revealed until the reply lands
        self.work()
        polled = self.poll(session_id, 2).get_json()
        self.assertIn('HIDDEN_SENTINEL <a class="practice-revealed-source" href="#turn-3">Show the reply</a>',
                      polled["revealed_html"])
        html = self.page(session_id)
        self.assertIn('<h3 id="revealed-heading">Revealed requirements</h3>', html)
        self.assertIn('href="#turn-3">Show the reply</a>', html)
        self.act(session_id, self.fields(session_id), "send", message="Could I have a hint?")
        self.work()
        html = self.page(session_id)
        self.assertIn('Interviewer <span class="practice-hint">Hint</span>', html)
        self.assertEqual(html.count('class="practice-hint"'), 1)

    def long_conversation(self, session_id, *, allowance):
        """Four long exchanges, then a message saved while AI was off, with the allowance set relative to it."""
        for number in range(4):
            self.act(session_id, self.fields(session_id), "send", message=f"EARLY_{number} " + "detail " * 400)
            self.work()
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):
            self.act(session_id, self.fields(session_id), "send", message="LATEST question?")
        session = practice_service._owned_session(1, session_id)
        worst = practice_service._worst_case(session, practice_service._latest_learner_turn(session_id), 1)
        full = practice_worker.interviewer.prompt_bytes(worst["reply"])
        latest = practice_worker.interviewer.prompt_bytes(
            practice_service._narrowed(worst, len(worst["context"]["transcript"]) - 1))
        self.app.config["LEARNING_AI_CONTEXT_BYTES"] = allowance(latest, full)

    def test_continuing_with_recent_messages_from_the_page(self):
        session_id = self.start()
        self.long_conversation(session_id, allowance=lambda latest, full: (latest + full) // 2)
        html = self.page(session_id)
        self.assertIn("This conversation is now longer than the interviewer can read at once.", html)
        self.assertIn('value="recent">Continue with recent messages</button>', html)
        self.assertNotIn('value="reply">', html)
        self.assertEqual(self.act(session_id, FormFields(html).values, "recent").status_code, 303)
        html = self.page(session_id)
        self.assertIn("The interviewer now reads from a recent message on, marked in the conversation. "
                      "Nothing was deleted. Asked the interviewer for a reply.", html)
        marker = html.index('id="reads-from"')
        self.assertLess(html.index("EARLY_0"), marker)  # earlier messages stay in the record
        self.assertLess(marker, html.index("LATEST question?"))
        self.assertIn("The interviewer is replying", html)

    def test_work_too_long_to_read_names_what_to_shorten(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "save", api="contract " * 3000)
        with patch.dict(self.app.config, LEARNING_AI_ENABLED=False):
            self.act(session_id, self.fields(session_id), "send", message="Is this right?")
        self.app.config["LEARNING_AI_CONTEXT_BYTES"] = 2_000
        html = self.page(session_id)
        self.assertIn("The interviewer can't read your work at once: “API contract” is too long. Shorten it and save, "
                      "then send a new message: a reply reads the work your message was sent with.", html)
        self.assertNotIn('value="recent">', html)
        self.assertNotIn('value="reply">', html)

    def test_a_check_in_after_many_messages_never_stops_the_conversation(self):
        session_id = self.start()
        self.app.config.update(LEARNING_AI_CHECK_IN_TURNS=2, LEARNING_AI_ENABLED=False)
        self.act(session_id, self.fields(session_id), "send", message="one")
        self.assertNotIn("practice-checkin", self.page(session_id))
        self.act(session_id, self.fields(session_id), "send", message="two")
        self.assertIn("You've sent 2 messages in this session. Keep going while it helps", self.page(session_id))
        self.assertEqual(self.act(session_id, self.fields(session_id), "send", message="three").status_code, 303)

    def test_a_reply_containing_markup_is_shown_as_text(self):
        session_id = self.start()
        self.act(session_id, self.fields(session_id), "send", message="hi")
        self.work(FakeProvider(replies=["<script>alert(1)</script> & more"]))
        html = self.page(session_id)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; more", html)
        self.assertNotIn("<script>alert(1)", html)
        polled = json.dumps(self.poll(session_id, 2).get_json())
        self.assertNotIn("<script>alert(1)", polled)


if __name__ == "__main__":
    unittest.main()
