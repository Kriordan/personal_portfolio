"""Disposable Learning fixture on localhost:5057; never uses production data.

POST /fixture/state with reads=success|failure|empty, rating=success|failure|lost,
receipts=success|failure, delay=seconds, practice=success|failure|lost,
ai=success|slow|fail|lost|hang|invalid, cap_usd=dollars, context_bytes=bytes. With --concept, practice
sessions are enabled; practice=failure makes saves and sends (website and API) fail
before saving, and practice=lost saves and then reports an unconfirmed result. AI replies
come from a scripted fake provider (never a paid call) for learning1, the configured
owner; `ai` switches how it behaves, cap_usd lowers the monthly AI budget, and
context_bytes shrinks what the interviewer may read (to try Continue with recent messages).
The fake selector reveals a requirement when a message repeats one of its clarification
cues (or shares two distinctive words with one), and gives a hint when asked for one.
GET /fixture/results reports saved counts. The 10-second access token also exercises
the real refresh flow. All notes and database files live in a temporary directory and
are removed when stopped.
"""
import json
import argparse
import os
import shutil
import signal
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
from project.models import (  # noqa: E402
    AIRequest, ArtifactRevision, ContentRevision, CurriculumItem, Gift, Playlist, PracticeReceipt,
    PracticeSession, ReviewLog, ReviewProgress, ReviewReceipt, SessionMessage, User,
)
from project.learning.content_schema import load_catalog  # noqa: E402
from project.services import practice_budget, practice_service, practice_worker  # noqa: E402
from project.services.curriculum_service import content_checksum  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concept', action='store_true', help='Include the idempotency web demo with CSRF enabled.')
    parser.add_argument('--port', type=int, default=5057, help='Use another port to preserve an existing demo.')
    args = parser.parse_args()
    email_validator.TEST_ENVIRONMENT = True
    # Stopping with SIGTERM (as preview tools do) exits like Ctrl+C, so the temporary database is removed.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
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
            "TESTING": True, "TEMPLATES_AUTO_RELOAD": True, "SECRET_KEY": "disposable-learning-only",
            "JWT_SECRET_KEY": "disposable-learning-jwt-secret-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(directory) / 'preview.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(seconds=10), "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=1),
            "WTF_CSRF_ENABLED": args.concept, "SESSION_COOKIE_SECURE": False, "RATELIMIT_ENABLED": False,
            "LEARNING_PREVIEW_FIXTURE": args.concept, "LEARNING_PRACTICE_ENABLED": args.concept,
            "LEARNING_AI_ENABLED": args.concept, "LEARNING_AI_PROVIDER": "fake",
            "LEARNING_AI_OWNER_EMAIL": "learning1@example.test", "LEARNING_AI_CALL_SECONDS": 10,
            "LEARNING_AI_LEASE_MARGIN_SECONDS": 5, "LEARNING_AI_START_SECONDS": 30,
        })
        talisman.force_https = False
        mode = {"reads": "success", "rating": "success", "receipts": "success", "delay": 0, "practice": "success",
                "ai": "success"}

        def simulate_failures(operation):
            """Simulated database failures, so the rescue page and replay can be inspected."""
            def fixture_operation(*call_args, **call_kwargs):
                if mode["practice"] == "failure":
                    raise OperationalError("fixture", {}, Exception("Fixture practice database unavailable"))
                result = operation(*call_args, **call_kwargs)
                if mode["practice"] == "lost":
                    raise OperationalError("fixture", {}, Exception("Fixture lost the result after commit"))
                return result
            return fixture_operation
        now = datetime.now(timezone.utc)
        with app.app_context():
            if args.concept:
                # Deleting a practice session relies on database cascades, which SQLite
                # enforces only with this pragma on every connection.
                event.listen(db.engine, "connect", lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON"))
                db.engine.dispose()
            db.create_all()
            if args.concept:
                # Fixture-only publication: not a human review attestation and
                # never the configured application database or importer.
                catalog = load_catalog(ROOT / 'curriculum/idempotency/catalog.json')
                for item in catalog['items']:
                    db.session.add(CurriculumItem(id=item['id'], kind=item['kind']))
                db.session.flush()
                for item in catalog['items']:
                    db.session.add(ContentRevision(item_id=item['id'], version=item['version'], schema_version=1,
                        payload=item, checksum=content_checksum(item), imported_at=now, published_at=now,
                        reviewed_by='Disposable demo fixture', reviewed_on=now.date()))
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
            if "cap_usd" in values:
                app.config.update(LEARNING_AI_MONTHLY_CAP_USD=float(values["cap_usd"]),
                                  LEARNING_AI_WARN_USD=float(values["cap_usd"]) * 0.8)
            if "context_bytes" in values:
                app.config["LEARNING_AI_CONTEXT_BYTES"] = int(values["context_bytes"])
            return jsonify(dict(mode, cap_usd=app.config.get("LEARNING_AI_MONTHLY_CAP_USD", 50),
                                context_bytes=practice_service.ai_settings()["context_bytes"]))

        @app.get("/fixture/results")
        def results():
            def practice_counts(user_id):
                sessions = [row.id for row in PracticeSession.query.filter_by(user_id=user_id).all()]
                return {"sessions": len(sessions),
                        "artifact_revisions": ArtifactRevision.query.filter(
                            ArtifactRevision.practice_session_id.in_(sessions)).count(),
                        "turns": SessionMessage.query.filter(SessionMessage.practice_session_id.in_(sessions),
                                                             SessionMessage.kind == "turn").count(),
                        "brief_revisions": SessionMessage.query.filter(
                            SessionMessage.practice_session_id.in_(sessions), SessionMessage.kind == "brief").count(),
                        "submissions": SessionMessage.query.filter(
                            SessionMessage.practice_session_id.in_(sessions), SessionMessage.kind == "submission").count(),
                        "receipts": PracticeReceipt.query.filter_by(user_id=user_id).count(),
                        "replies": dict(db.session.query(AIRequest.status, db.func.count()).filter(
                            AIRequest.practice_session_id.in_(sessions)).group_by(AIRequest.status).all())}
            return jsonify({str(user.id): {"logs": ReviewLog.query.filter_by(user_id=user.id).count(),
                "receipts": ReviewReceipt.query.filter_by(user_id=user.id).count(),
                "ratings": [log.rating for log in ReviewLog.query.filter_by(user_id=user.id).order_by(ReviewLog.id).all()],
                "practice": practice_counts(user.id)}
                for user in User.query.all()} | {"ai_spend_microusd": practice_budget.committed(
                    practice_budget.period(datetime.now(timezone.utc)))})

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

        if args.concept:
            # Scripted replies only: the fake provider never contacts a network or spends money.
            practice_worker.start(app, practice_worker.FakeProvider(lambda: mode["ai"], delay=3.0), poll_seconds=1.0)
        print("Disposable logins: learning1@example.test or learning2@example.test / LearningPreview123!", flush=True)
        with patch("project.services.learning_service.notes_dir_for_root", return_value=notes_dir), \
                patch.object(practice_service, "save_work", simulate_failures(practice_service.save_work)), \
                patch.object(practice_service, "save_and_send", simulate_failures(practice_service.save_and_send)), \
                patch.object(practice_service, "save_and_submit", simulate_failures(practice_service.save_and_submit)), \
                patch.object(practice_service, "send_turn", simulate_failures(practice_service.send_turn)), \
                patch.object(practice_service, "request_reply", simulate_failures(practice_service.request_reply)):
            app.run(host="127.0.0.1", port=args.port, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
