"""Disposable Learning fixture on localhost:5057; never uses production data.

POST /fixture/state with reads=success|failure|empty, rating=success|failure|lost,
receipts=success|failure, delay=seconds. GET /fixture/results reports saved counts.
The 10-second access token also exercises the real refresh flow. All notes and
database files live in a temporary directory and are removed when stopped.
"""
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import email_validator  # noqa: E402
from flask import jsonify, make_response, request  # noqa: E402
from project import create_app  # noqa: E402
from project.database import db  # noqa: E402
from project.extensions import talisman  # noqa: E402
from project.models import Gift, Playlist, ReviewLog, ReviewProgress, ReviewReceipt, User  # noqa: E402


def main():
    email_validator.TEST_ENVIRONMENT = True
    with tempfile.TemporaryDirectory(prefix="learning-preview-") as directory:
        notes_dir = Path(directory) / "notes"
        shutil.copytree(ROOT / "notes", notes_dir)
        examples = [
            {"id": "qa", "type": "qa", "question": "What makes a review save reliable?", "answer": "A **committed receipt** identifies the attempt. A retry uses the same `request_id`."},
            {"id": "cloze", "type": "cloze", "text": "A retry keeps the {{c1::same attempt ID}}."},
            {"id": "command", "type": "command", "prompt": "Show a command with a long argument.", "answer": "python -m unittest discover --start-directory tests --pattern 'test_learning*.py'\n# This is selectable code, not an executable action."},
            {"id": "diff", "type": "code_diff", "prompt": "Prevent a duplicate review.", "before": "save_rating(card, rating)\nsave_rating(card, rating)", "after": "save_rating(card, rating, request_id=attempt_id)\n# A repeated attempt returns its original receipt."},
            {"id": "incident", "type": "incident", "symptom": "The phone loses the response after the server commits.", "root_cause": "The network interrupted confirmation.", "fix": "Read the durable receipt.", "prevention": "Reuse the original attempt ID and expected revision."},
        ]
        def note(note_id, title, cards, tags=None):
            (notes_dir / f"{note_id}.json").write_text(json.dumps({
                "id": note_id, "title": title, "summary": "Disposable practice notes for browsing and review. **Your progress is personal.**",
                "tags": tags or ["preview", "reliability"], "created_at": "2026-10-14", "flashcards": cards,
            }))
        note("all-types", "A tour of all five card types", examples)
        note("empty-note", "An empty note", [])
        for index in range(200):
            note(f"practice-{index:03}", f"Practice {index + 1:03}: a long title for a smaller screen and larger text", [
                {"id": f"card-{card}", "type": "qa", "question": f"Practice {index + 1}, question {card + 1}", "answer": "Read, reflect, and review."}
                for card in range(3)
            ], ["practice", "searchable"])
        app = create_app({
            "TESTING": True, "SECRET_KEY": "disposable-learning-only",
            "JWT_SECRET_KEY": "disposable-learning-jwt-secret-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(directory) / 'preview.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(seconds=10), "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=1),
            "WTF_CSRF_ENABLED": False, "SESSION_COOKIE_SECURE": False, "RATELIMIT_ENABLED": False,
        })
        talisman.force_https = False
        mode = {"reads": "success", "rating": "success", "receipts": "success", "delay": 0}
        now = datetime.now(timezone.utc)
        with app.app_context():
            db.create_all()
            for number in (1, 2):
                user = User(email=f"learning{number}@example.test", username=f"Learning Preview {number}", email_verified=True)
                user.set_password("LearningPreview123!")
                db.session.add(user)
                db.session.flush()
                db.session.add(Gift(user_id=user.id, title="Learning regression gift", body="Disposable text-only gift."))
                db.session.add(ReviewProgress(user_id=user.id, card_id="practice-000:card-0", is_suspended=True, next_review=now - timedelta(days=1)))
                db.session.add(ReviewProgress(user_id=user.id, card_id="practice-000:card-1", next_review=now + timedelta(days=1)))
            db.session.add(Playlist(id="learning-regression", title="A saved playlist for Library regression", description="Sort and pin this disposable playlist.", published_at=now, updated_at=now))
            db.session.commit()

        @app.post("/fixture/state")
        def state():
            values = request.get_json()
            mode.update({key: values[key] for key in mode if key in values})
            return jsonify(mode)

        @app.get("/fixture/results")
        def results():
            return jsonify({str(user.id): {"logs": ReviewLog.query.filter_by(user_id=user.id).count(),
                "receipts": ReviewReceipt.query.filter_by(user_id=user.id).count(),
                "ratings": [log.rating for log in ReviewLog.query.filter_by(user_id=user.id).order_by(ReviewLog.id).all()]}
                for user in User.query.all()})

        @app.before_request
        def failures():
            if not request.path.startswith(("/api/v1/learning/", "/learning/")):
                return None
            if "/ratings/" in request.path:
                if mode["receipts"] == "failure":
                    return jsonify(error="Fixture receipt unavailable"), 503
            elif request.method == "GET" and mode["reads"] == "failure":
                return jsonify(error="Fixture read unavailable"), 503
            elif request.path.endswith("/notes") and mode["reads"] == "empty":
                return jsonify(notes=[], total_due=0)
            if request.path.endswith("/rate") and request.method == "POST":
                time.sleep(float(mode["delay"]))
                if mode["rating"] == "failure":
                    return jsonify(error="Fixture write unavailable"), 503
            return None

        @app.after_request
        def lost_response(response):
            if request.path.endswith("/rate") and request.method == "POST" and response.status_code == 200 and mode["rating"] == "lost":
                return make_response(jsonify(error="Fixture lost response after commit"), 503)
            return response

        print("Disposable logins: learning1@example.test or learning2@example.test / LearningPreview123!", flush=True)
        with patch("project.services.learning_service.notes_dir_for_root", return_value=notes_dir):
            app.run(host="127.0.0.1", port=5057, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
