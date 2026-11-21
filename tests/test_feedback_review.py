"""Learner decisions are separate from immutable feedback and explicit recall ratings."""
from copy import deepcopy
from datetime import timedelta
import json
from uuid import uuid4

from project.database import db
from project.models import ContentRevision, LearningAICharge, PracticeFeedback, PracticeFeedbackAnnotation, PracticeReceipt, ReviewLog, ReviewProgress, ReviewReceipt, User
from project.services import feedback_service as feedback, feedback_review_service as review, learning_service, practice_service as practice, practice_worker
from tests.curriculum_v2_fixtures import PRIVATE_V2, publish_feedback_catalog
from tests.feedback_fixtures import DISCOVERY, RACE, scripted_feedback
from tests.test_practice_replies import PracticeReplyCase
from tests.test_practice_submissions import submission_input


def completed_feedback(user):
    sid = practice.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
    seq = practice.save_and_submit(user, sid, **submission_input(practice.session_detail(user.id, sid),
        DISCOVERY + "\n" + RACE))["submission"]["sequence"]
    request_id = feedback.request_feedback(user, sid, seq, request_id=str(uuid4()))["request"]["id"]
    practice_worker.run_once(practice_worker.FakeProvider(feedbacks=[scripted_feedback]))
    assert feedback.detail(user.id, sid, seq)["feedback"] is not None
    return sid, seq, request_id


class FeedbackReviewTests(PracticeReplyCase):
    def setUp(self):
        super().setUp()
        publish_feedback_catalog()
        self.sid, self.seq, self.rid = completed_feedback(self.user)

    def annotate(self, **kwargs):
        return review.annotate(self.user, self.sid, self.seq, "f2", **{
            "decision": "agree", "note": "I should test the two first attempts.",
            "expected_revision": 0, "request_id": str(uuid4()), **kwargs})

    def detail(self):
        return review.review_detail(self.user.id, self.sid, self.seq, "f2")

    def attempt(self):
        card = self.detail()["questions"][0]
        return dict(card_id=card["card_id"], content_version=card["content_version"],
                    expected_revision=card["progress_revision"], request_id=str(uuid4()))

    def rate(self, attempt, **kwargs):
        return review.rate_review(self.user, self.sid, self.seq, "f2", **dict(attempt, rating=4, **kwargs))

    def test_response_and_note_never_mutate_assessment_work_scheduling_or_ai_usage(self):
        original = deepcopy(PracticeFeedback.query.one().data)
        inputs = feedback.context(self.rid)
        self.app.config["LEARNING_AI_ENABLED"] = False
        self.annotate(note="\nA <script>note</script>\r\nSecond line")
        result = feedback.detail(self.user.id, self.sid, self.seq)["feedback"]["findings"][1]
        self.assertEqual(result["annotation"]["note"], "\nA <script>note</script>\nSecond line")
        self.assertTrue(result["practice_available"])
        self.assertEqual(PracticeFeedback.query.one().data, original)
        self.assertEqual(feedback.context(self.rid), inputs)
        self.assertEqual((ReviewProgress.query.count(), ReviewLog.query.count(), ReviewReceipt.query.count()), (0, 0, 0))
        self.assertEqual(LearningAICharge.query.count(), 1)
        receipt = PracticeReceipt.query.filter_by(operation="annotate").one()
        self.assertNotIn("<script>", json.dumps(receipt.response))
        for private in (*PRIVATE_V2, "misconception_ids", "check-then-insert-is-safe"):
            self.assertNotIn(private, json.dumps(result))

    def test_replays_noops_and_stale_updates_preserve_the_latest_note(self):
        request_id = str(uuid4())
        first = self.annotate(request_id=request_id)
        self.assertEqual(self.annotate(request_id=request_id), first)
        self.assertFalse(self.annotate(expected_revision=1)["changed"])
        self.annotate(expected_revision=1, decision="disagree", note="My newer explanation")
        self.assertEqual(self.annotate(request_id=request_id), first)
        with self.assertRaises(review.AnnotationConflict) as exc:
            self.annotate(note="stale overwrite")
        self.assertEqual(exc.exception.current["note"], "My newer explanation")
        with self.assertRaises(practice.RequestConflictError):
            self.annotate(request_id=request_id, note="different payload")
        self.assertEqual(PracticeFeedbackAnnotation.query.one().revision, 2)
        self.annotate(expected_revision=2, decision="unreviewed", note="Not sure yet")
        self.assertEqual(self.detail()["questions"], [])

    def test_ownership_finding_and_validation_boundaries(self):
        for sid, fid, user in ((self.sid, "unknown", self.user), (str(uuid4()), "f2", self.user),
                               (self.sid, "f2", db.session.get(User, 2))):
            with self.assertRaises(learning_service.NotFoundError):
                review.annotate(user, sid, self.seq, fid, decision="agree", note="private", expected_revision=0, request_id=str(uuid4()))
        for values in ({"decision": "mastered"}, {"expected_revision": True}, {"note": "x" * 2001},
                       {"note": "\x00"}, {"note": "\ud800"}, {"note": None}):
            with self.subTest(values=repr(values)[:50]), self.assertRaises(learning_service.ValidationError):
                self.annotate(**values)
        self.assertEqual(PracticeFeedbackAnnotation.query.count(), 0)

    def test_explicit_extra_review_includes_not_due_cards_and_uses_the_existing_scheduler(self):
        self.annotate()
        first = self.attempt()
        learning_service.rate_card_for_user(user=self.user, notes_dir=learning_service.notes_dir_for_root(self.app.root_path),
            **dict(first, rating=5))
        progress = ReviewProgress.query.one()
        progress.next_review = self.clock() + timedelta(days=30)
        db.session.commit()
        before = progress.next_review
        attempt = self.attempt()
        self.assertEqual(attempt["expected_revision"], 1)
        revealed = review.review_card(self.user.id, self.sid, self.seq, "f2", **attempt)
        self.assertIn("answer", revealed)
        self.assertEqual(ReviewProgress.query.one().next_review, before)
        result = self.rate(attempt)
        self.assertEqual(self.rate(attempt), result)
        self.assertEqual(ReviewProgress.query.one().revision, 2)
        self.assertEqual(ReviewLog.query.count(), 2)
        self.assertEqual(self.detail()["completed"], 1)
        self.assertEqual(self.detail()["questions"], [])
        with self.assertRaises(learning_service.StaleReviewError):
            self.rate(dict(attempt, request_id=str(uuid4()), expected_revision=2))
        db.session.remove()
        self.assertEqual(review.review_detail(1, self.sid, self.seq, "f2")["completed"], 1)

    def test_reversing_agreement_blocks_new_ratings_but_keeps_committed_replays(self):
        self.annotate()
        attempt = self.attempt()
        self.annotate(expected_revision=1, decision="disagree")
        with self.assertRaises(review.DecisionRequired):
            self.rate(attempt)
        self.annotate(expected_revision=2)
        result = self.rate(attempt)
        self.annotate(expected_revision=3, decision="disagree")
        self.assertEqual(self.rate(attempt), result)
        self.assertEqual(ReviewLog.query.count(), 1)

    def test_only_authored_questions_and_published_versions_can_be_rated(self):
        self.annotate()
        attempt = self.attempt()
        for values in ({"card_id": "idempotency:timeout"}, {"content_version": 999}):
            with self.assertRaises(learning_service.NotFoundError):
                self.rate(dict(attempt, **values))
        newer = deepcopy(db.session.get(ContentRevision, (attempt["card_id"], 2)).payload)
        newer["version"] = 3
        newer["content"]["answer"] = "A changed answer for version three."
        now = self.clock()
        db.session.add(ContentRevision(item_id=attempt["card_id"], version=3, schema_version=2, payload=newer,
            checksum="fixture", imported_at=now, published_at=now, reviewed_by="Fixture", reviewed_on=now.date()))
        db.session.commit()
        revealed = review.review_card(self.user.id, self.sid, self.seq, "f2", **attempt)
        self.assertNotEqual(revealed["answer"], newer["content"]["answer"])
        self.rate(attempt)
        self.assertEqual(ReviewLog.query.one().content_version, 2)

    def test_suspended_questions_are_never_unsuspended_or_rated(self):
        self.annotate()
        attempt = self.attempt()
        learning_service.rate_card_for_user(user=self.user, notes_dir=learning_service.notes_dir_for_root(self.app.root_path),
            **dict(attempt, rating=4))
        progress = ReviewProgress.query.one()
        progress.is_suspended = True
        db.session.commit()
        self.assertEqual(self.detail()["unavailable"], 1)
        self.assertEqual(self.detail()["questions"], [])
        with self.assertRaises(learning_service.StaleReviewError):
            self.rate(dict(attempt, expected_revision=1, request_id=str(uuid4())))
        self.assertTrue(ReviewProgress.query.one().is_suspended)

    def test_delete_removes_responses_and_feedback_but_preserves_explicit_review_history(self):
        self.annotate()
        self.rate(self.attempt())
        practice.delete_session(self.user, self.sid)
        self.assertEqual(PracticeFeedbackAnnotation.query.count(), 0)
        self.assertEqual(PracticeFeedback.query.count(), 0)
        self.assertEqual(PracticeReceipt.query.count(), 0)
        self.assertEqual((ReviewProgress.query.count(), ReviewLog.query.count(), ReviewReceipt.query.count()), (1, 1, 1))
        self.assertEqual(LearningAICharge.query.count(), 1)

    def test_v1_and_unmapped_findings_allow_notes_without_inventing_practice(self):
        # The completed v2 snapshot also has an unmapped missing-evidence finding.
        review.annotate(self.user, self.sid, self.seq, "f3", decision="agree", note="Need more detail",
                        expected_revision=0, request_id=str(uuid4()))
        self.assertEqual(review.review_detail(self.user.id, self.sid, self.seq, "f3")["total"], 0)
        from project.models import PracticeSession
        # Build a real v1 session before feedback rather than changing a completed snapshot.
        for row in ContentRevision.query.filter_by(version=2):
            row.published_at = row.reviewed_by = row.reviewed_on = None
        db.session.commit()
        sid, seq, _ = completed_feedback(self.user)
        self.assertEqual(db.session.get(PracticeSession, sid).exercise_version, 1)
        review.annotate(self.user, sid, seq, "f2", decision="agree", note="A v1 concern", expected_revision=0, request_id=str(uuid4()))
        self.assertEqual(review.review_detail(self.user.id, sid, seq, "f2")["total"], 0)
