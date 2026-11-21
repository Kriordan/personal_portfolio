"""Hub navigation reads the existing progress and owned-session projections."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from flask import g

from project.database import db
from project.models import (ArtifactRevision, ContentRevision, PracticeReceipt, PracticeSession,
                            ReviewLog, ReviewProgress, ReviewReceipt, User)
from project.services import learning_service, practice_service
from tests.learning_hub_fixtures import seed_notes
from tests.test_practice_service import SENTINELS
from tests.test_practice_web import PracticeWebCase


class LearningHubTests(PracticeWebCase):
    def setUp(self):
        super().setUp()
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix="learning-hub-"))
        self.notes = Path(directory)
        seed_notes(self.notes)
        self.enterContext(patch.object(learning_service, "notes_dir_for_root", return_value=self.notes))

    def counts(self):
        return tuple(model.query.count() for model in (PracticeSession, PracticeReceipt, ArtifactRevision,
            ReviewLog, ReviewProgress, ReviewReceipt))

    def test_home_does_not_load_the_note_library_or_write_progress(self):
        before = self.counts()
        with patch.object(learning_service, "load_notes", side_effect=AssertionError("bulk note load")):
            page = self.get("/learning/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Explore the concept", page.data)
        self.assertIn(b"Start learning", page.data)
        self.assertNotIn(b"Review \xc2\xb7 4 due", page.data)
        self.assertNotIn(b"Note 00", page.data)
        self.assertEqual(before, self.counts())

    def test_continue_chooses_the_newest_open_owned_session_without_resuming_it(self):
        now = datetime.now(timezone.utc)
        ids = []
        for user_id, offset in ((1, 0), (1, 1), (2, 2), (1, 3)):
            ids.append(practice_service.start_session(db.session.get(User, user_id),
                exercise_id="idempotent-order-api", request_id=str(uuid4()),
                now=now + timedelta(hours=offset))["session_id"])
        db.session.get(PracticeSession, ids[1]).status = "paused"
        db.session.get(PracticeSession, ids[3]).status = "completed"
        db.session.commit()
        before = self.counts()
        page = self.get("/learning/").get_data(as_text=True)
        self.assertIn(f'href="/learning/practice/{ids[1]}"', page)
        self.assertIn("Paused", page)
        for excluded in (ids[0], ids[2], ids[3]):
            self.assertNotIn(excluded, page)
        self.assertEqual(before, self.counts())
        self.assertEqual(db.session.get(PracticeSession, ids[1]).status, "paused")
        self.assertEqual(self.get(f"/learning/practice/{ids[1]}").status_code, 200)

    def test_pinned_practice_is_reachable_when_its_concept_is_unpublished(self):
        session_id = self.start()
        revision = db.session.get(ContentRevision, ("idempotency", 1))
        revision.published_at = revision.reviewed_by = revision.reviewed_on = None
        db.session.commit()
        page = self.get("/learning/").get_data(as_text=True)
        self.assertIn(f'href="/learning/practice/{session_id}"', page)
        self.assertNotIn('href="/learning/concepts/idempotency', page)

    def test_feature_off_does_not_query_practice_and_keeps_lesson_review_links(self):
        self.app.config["LEARNING_PRACTICE_ENABLED"] = False
        with patch.object(practice_service, "list_sessions", side_effect=AssertionError("practice query")):
            page = self.get("/learning/")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(b"data-learning-continue", page.data)
        self.assertIn(b'href="/learning/concepts/idempotency/review"', page.data)

    def test_private_routes_do_not_leak_answers_or_reference_material(self):
        for path in ("/learning/", "/learning/flashcards", "/learning/references"):
            response = self.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Cache-Control"], "private, no-store")
            for hidden in SENTINELS + ("Private answer", "hotjar", "googletagmanager"):
                self.assertNotIn(hidden, response.get_data(as_text=True))

    def test_signed_out_learning_destinations_all_require_login(self):
        with self.client.session_transaction() as session:
            session.clear()
        g.pop("_login_user", None)
        with patch.object(learning_service, "load_notes", side_effect=AssertionError("private notes read")):
            for path in ("/learning/flashcards", "/learning/references", "/learning/"):
                response = self.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login?next=", response.headers["Location"])
                self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_pagination_and_search_do_not_change_review_scope_or_progress(self):
        before = self.counts()
        first = self.get("/learning/flashcards").get_data(as_text=True)
        self.assertIn("28 cards due", first)
        self.assertEqual(first.count('href="/learning/note/'), 25)
        self.assertNotIn("Note 25", first)
        second = self.get("/learning/flashcards?page=2").get_data(as_text=True)
        self.assertEqual(second.count('href="/learning/note/'), 5)
        self.assertIn("Note 25", second)
        self.assertIn("&lt;script&gt;", second)
        self.assertNotIn('<script>alert("title")', second)
        filtered = self.get("/learning/flashcards?q=nOtE+28&page=2").get_data(as_text=True)
        self.assertIn("28 cards due", filtered)
        self.assertEqual(filtered.count('href="/learning/note/'), 1)
        self.assertIn("Note 28", filtered)
        self.assertIn('href="/learning/review"', filtered)
        self.assertEqual(before, self.counts())

    def test_search_escaping_empty_states_and_invalid_page_numbers(self):
        query = '<img src=x onerror="alert(1)">'
        response = self.get("/learning/flashcards?" + urlencode(dict(q=query)))
        self.assertNotIn(query, response.get_data(as_text=True))
        self.assertIn(b"No matching notes", response.data)
        for page in ("-1", "bad", "9" * 100):
            self.assertEqual(self.get(f"/learning/flashcards?page={page}").status_code, 200)
        self.assertEqual(self.get("/learning/flashcards?q=" + "x" * 201).status_code, 400)
        with patch.object(learning_service, "load_notes", return_value=[]):
            response = self.get("/learning/flashcards")
        self.assertIn(b"No flashcard notes yet", response.data)
        self.assertIn(b"0 cards due", response.data)
        self.assertNotIn(b"Start review", response.data)

    def test_reviewed_card_stays_scheduled_after_hub_navigation_and_another_user_is_isolated(self):
        learning_service.rate_card_for_user(user=db.session.get(User, 1), notes_dir=self.notes,
            card_id="hub-02:q", rating=4, expected_revision=0, request_id=str(uuid4()))
        before = self.counts()
        self.assertEqual(self.get("/learning/").status_code, 200)
        for _ in range(2):
            self.assertIn(b"27 cards due", self.get("/learning/flashcards").data)
        self.assertEqual(self.get("/learning/note/hub-02").status_code, 200)
        self.assertEqual(before, self.counts())
        self.login(2)
        self.assertIn(b"30 cards due", self.get("/learning/flashcards").data)

    def test_no_published_concept_has_an_explicit_empty_state(self):
        for revision in ContentRevision.query.all():
            revision.published_at = revision.reviewed_by = revision.reviewed_on = None
        db.session.commit()
        page = self.get("/learning/")
        self.assertIn(b"Your next concept will appear here", page.data)
        self.assertIn(b'href="/learning/flashcards"', page.data)
        self.assertNotIn(b"data-learning-continue", page.data)
