"""V1 and v2 coexist without exposing evaluation-only material to learners or the interviewer."""
import json

from project.database import db
from project.learning.content_schema import evaluator_view
from project.models import ContentRevision
from project.services import practice_service
from tests.curriculum_v2_fixtures import PRIVATE_V2, publish_feedback_catalog
from tests.test_practice_api import PracticeApiCase
from tests.test_practice_replies import PracticeReplyCase
from tests.test_practice_web import PracticeWebCase


class FeedbackFoundationWebTests(PracticeWebCase):
    def test_both_session_versions_render_without_private_mappings(self):
        old = self.start()
        publish_feedback_catalog()
        new = self.start()
        for session_id, version in ((old, 1), (new, 2)):
            for path in (f"/learning/practice/{session_id}",
                         f"/learning/concepts/idempotency?practice_session={session_id}",
                         f"/learning/concepts/idempotency/review?practice_session={session_id}"):
                page = self.get(path)
                self.assertEqual(page.status_code, 200)
                for secret in (*PRIVATE_V2, "evidence_guidance"):
                    self.assertNotIn(secret, page.get_data(as_text=True))
            self.assertEqual(practice_service.session_summary(1, session_id)["exercise_version"], version)


class FeedbackFoundationApiTests(PracticeApiCase):
    def test_v2_is_usable_through_existing_api_without_extending_learner_responses(self):
        old = self.start()
        before = self.call("GET", f"/sessions/{old}").get_json()
        publish_feedback_catalog()
        new = self.start()
        self.assertEqual(self.call("GET", f"/sessions/{old}").get_json(), before)
        self.assertEqual(self.put(new, "POST /orders").status_code, 200)
        detail = self.call("GET", f"/sessions/{new}").get_json()
        self.assertEqual(set(detail), set(before))
        self.assertEqual(detail["session"]["exercise_version"], 2)
        self.assertEqual(detail["artifacts"][0]["body"], "POST /orders")
        for path in ("/sessions", f"/sessions/{old}", f"/sessions/{new}"):
            response = self.call("GET", path)
            for secret in (*PRIVATE_V2, "misconceptions", "evidence_guidance"):
                self.assertNotIn(secret, response.get_data(as_text=True))


class FeedbackFoundationInterviewerTests(PracticeReplyCase):
    def test_old_and_new_interviews_complete_without_evaluator_material_in_prompts(self):
        old = self.start()
        publish_feedback_catalog()
        new = self.start()
        for session_id, version in ((old, 1), (new, 2)):
            self.send(session_id, "Who owns the key?")
            self.assertTrue(self.work())
            self.assertEqual(self.reply_state(session_id)["status"], "completed")
            detail = practice_service.session_detail(1, session_id, now=self.clock())
            self.assertEqual(detail["session"]["exercise_version"], version)
            self.assertEqual([fact["id"] for fact in detail["revealed_requirements"]], ["scope"])
        self.assertEqual(len(self.provider.calls), 4)  # selector and reply per session
        for secret in (*PRIVATE_V2, "misconceptions", "evidence_guidance"):
            self.assertNotIn(secret, json.dumps(self.provider.calls))
        # The private material exists in the pinned v2 snapshot; absence above is not an empty-fixture pass.
        packet = evaluator_view(db.session.get(ContentRevision, ("idempotent-order-api", 2)).payload)
        self.assertIn(PRIVATE_V2[1], json.dumps(packet))
