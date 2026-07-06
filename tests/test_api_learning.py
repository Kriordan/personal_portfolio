import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import ReviewLog, ReviewProgress, User

NOTE_ID = "flask-basics"
CARD_ID = f"{NOTE_ID}:q1"


class ApiLearningTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "JWT_SECRET_KEY": "test-jwt-secret-should-be-at-least-32",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

        self._notes_tempdir = tempfile.TemporaryDirectory()
        self.notes_dir = Path(self._notes_tempdir.name)
        self._write_note(
            {
                "id": NOTE_ID,
                "title": "Flask Basics",
                "tags": ["flask"],
                "summary": "Core Flask concepts.",
                "flashcards": [
                    {
                        "id": "q1",
                        "type": "qa",
                        "question": "What does Flask use for routing?",
                        "answer": "Werkzeug URL maps.",
                    }
                ],
            }
        )

        self._notes_dir_patcher = patch(
            "project.services.learning_service.notes_dir_for_root",
            return_value=self.notes_dir,
        )
        self._notes_dir_patcher.start()

    def tearDown(self):
        self._notes_dir_patcher.stop()
        self._notes_tempdir.cleanup()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _write_note(self, note: dict) -> None:
        note_path = self.notes_dir / f"{note['id']}.json"
        note_path.write_text(json.dumps(note), encoding="utf-8")

    def _create_user(self, *, email: str, username: str) -> int:
        with self.app.app_context():
            user = User(email=email, username=username, email_verified=True)
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            return user.id

    def _token_for(self, user_id: int) -> str:
        with self.app.app_context():
            return create_access_token(identity=str(user_id))

    def _auth_headers(self, user_id: int) -> dict:
        return {"Authorization": f"Bearer {self._token_for(user_id)}"}

    def _get(self, path: str, **kwargs):
        return self.client.get(path, base_url="https://localhost", **kwargs)

    def _post(self, path: str, **kwargs):
        return self.client.post(path, base_url="https://localhost", **kwargs)

    def test_learning_endpoints_require_jwt(self):
        unauthenticated_requests = [
            self._get("/api/v1/learning/notes"),
            self._get(f"/api/v1/learning/notes/{NOTE_ID}"),
            self._get("/api/v1/learning/review"),
            self._post("/api/v1/learning/rate", json={"card_id": CARD_ID, "rating": 4}),
        ]

        for response in unauthenticated_requests:
            self.assertEqual(response.status_code, 401)

    def test_get_notes_returns_summaries_and_total_due(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._get("/api/v1/learning/notes", headers=self._auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total_due"], 1)
        self.assertEqual(len(payload["notes"]), 1)
        note = payload["notes"][0]
        self.assertEqual(note["id"], NOTE_ID)
        self.assertEqual(note["title"], "Flask Basics")
        self.assertEqual(note["flashcard_count"], 1)
        self.assertEqual(note["due_count"], 1)

    def test_get_note_returns_rendered_cards(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._get(
            f"/api/v1/learning/notes/{NOTE_ID}", headers=self._auth_headers(user_id)
        )

        self.assertEqual(response.status_code, 200)
        note = response.get_json()["note"]
        self.assertEqual(note["id"], NOTE_ID)
        self.assertEqual(len(note["flashcards"]), 1)
        card = note["flashcards"][0]
        self.assertEqual(card["card_id"], CARD_ID)
        self.assertEqual(card["note_id"], NOTE_ID)
        self.assertEqual(card["type"], "qa")
        self.assertEqual(card["prompt"], "What does Flask use for routing?")
        self.assertEqual(card["response"], "Werkzeug URL maps.")
        self.assertEqual(card["tags"], ["flask"])

    def test_get_note_returns_404_for_unknown_note(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._get(
            "/api/v1/learning/notes/does-not-exist", headers=self._auth_headers(user_id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Note not found.")

    def test_review_returns_due_cards(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._get("/api/v1/learning/review", headers=self._auth_headers(user_id))

        self.assertEqual(response.status_code, 200)
        cards = response.get_json()["cards"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["card_id"], CARD_ID)

    def test_rate_requires_card_id_and_rating(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(user_id),
            json={"card_id": CARD_ID},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "card_id and rating are required")

    def test_rate_rejects_non_integer_rating(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(user_id),
            json={"card_id": CARD_ID, "rating": "great"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "rating must be an integer")

    def test_rate_rejects_out_of_range_rating(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(user_id),
            json={"card_id": CARD_ID, "rating": 6},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "rating must be between 0 and 5")

    def test_rate_rejects_malformed_card_id(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(user_id),
            json={"card_id": "no-colon-here", "rating": 4},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid card_id format")

    def test_rate_returns_404_for_unknown_card(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(user_id),
            json={"card_id": f"{NOTE_ID}:missing-card", "rating": 4},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "card not found")

    def test_rate_persists_progress_and_log(self):
        user_id = self._create_user(email="learner@example.com", username="learner")

        response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(user_id),
            json={"card_id": CARD_ID, "rating": 4, "response_ms": 1200, "session_id": "s1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["card_id"], CARD_ID)
        for key in (
            "learning_state",
            "interval",
            "repetitions",
            "easiness",
            "next_review",
            "next_review_display",
            "scheduler_version",
        ):
            self.assertIn(key, payload)

        with self.app.app_context():
            progress = ReviewProgress.query.filter_by(
                user_id=user_id, card_id=CARD_ID
            ).one()
            self.assertEqual(progress.last_rating, 4)
            log = ReviewLog.query.filter_by(user_id=user_id, card_id=CARD_ID).one()
            self.assertEqual(log.rating, 4)
            self.assertEqual(log.response_ms, 1200)
            self.assertEqual(log.session_id, "s1")

    def test_review_progress_is_scoped_per_user(self):
        rater_id = self._create_user(email="rater@example.com", username="rater")
        other_id = self._create_user(email="other@example.com", username="other")

        rate_response = self._post(
            "/api/v1/learning/rate",
            headers=self._auth_headers(rater_id),
            json={"card_id": CARD_ID, "rating": 4},
        )
        self.assertEqual(rate_response.status_code, 200)

        rater_review = self._get(
            "/api/v1/learning/review", headers=self._auth_headers(rater_id)
        )
        self.assertEqual(rater_review.get_json()["cards"], [])

        other_review = self._get(
            "/api/v1/learning/review", headers=self._auth_headers(other_id)
        )
        other_cards = other_review.get_json()["cards"]
        self.assertEqual(len(other_cards), 1)
        self.assertEqual(other_cards[0]["card_id"], CARD_ID)
