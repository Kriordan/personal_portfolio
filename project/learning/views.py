import json
from datetime import datetime, timezone
from pathlib import Path

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from project.database import db
from project.models import ReviewLog, ReviewProgress

from . import learning_blueprint
from .scheduler_config import SCHEDULER_VERSION
from .spaced_repetition import compute_schedule


def _notes_dir() -> Path:
    return Path(current_app.root_path).parent / "notes"


def _load_note(note_id: str):
    note_path = _notes_dir() / f"{note_id}.json"
    if not note_path.exists():
        return None
    try:
        data = json.loads(note_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    data.setdefault("id", note_id)
    data.setdefault("title", note_id.replace("-", " ").title())
    data.setdefault("summary", "")
    data.setdefault("flashcards", [])
    return data


def _load_notes():
    notes = []
    for note_path in sorted(_notes_dir().glob("*.json")):
        try:
            data = json.loads(note_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        note_id = data.get("id") or note_path.stem
        data.setdefault("id", note_id)
        data.setdefault("title", note_id.replace("-", " ").title())
        data.setdefault("summary", "")
        data.setdefault("flashcards", [])
        notes.append(data)
    return notes


def _build_cards(notes):
    cards = []
    for note in notes:
        note_id = note.get("id")
        note_title = note.get("title")
        for card in note.get("flashcards", []):
            card_id = card.get("id")
            if not card_id:
                continue
            cards.append(
                {
                    "card_id": f"{note_id}:{card_id}",
                    "note_id": note_id,
                    "note_title": note_title,
                    "question": card.get("question", ""),
                    "answer": card.get("answer", ""),
                }
            )
    return cards


def _progress_map(card_ids):
    if not card_ids:
        return {}
    progress_rows = ReviewProgress.query.filter(
        ReviewProgress.user_id == current_user.id,
        ReviewProgress.card_id.in_(card_ids),
    ).all()
    return {row.card_id: row for row in progress_rows}


def _format_next_review_display(now, next_review, before_state, after_state):
    delta = next_review - now
    seconds = max(0, int(delta.total_seconds()))

    if seconds < 60:
        display = "Next review in <1 min"
    elif seconds < 3600:
        minutes = round(seconds / 60)
        display = f"Next review in {minutes} min"
    elif seconds < 86400:
        hours = round(seconds / 3600)
        display = f"Next review in {hours} hr"
    else:
        days = round(seconds / 86400)
        display = f"Next review in {days} day{'s' if days != 1 else ''}"

    if before_state in {"new", "learning", "relearning"} and after_state == "review":
        return f"Graduated: {display}"

    return display


@learning_blueprint.route("/")
@login_required
def index():
    notes = _load_notes()
    cards = _build_cards(notes)
    progress_map = _progress_map([card["card_id"] for card in cards])
    now = datetime.now(timezone.utc)

    due_counts = {}
    for card in cards:
        progress = progress_map.get(card["card_id"])
        is_due = progress is None or progress.next_review <= now
        if is_due:
            due_counts[card["note_id"]] = due_counts.get(card["note_id"], 0) + 1

    for note in notes:
        note["flashcard_count"] = len(note.get("flashcards", []))
        note["due_count"] = due_counts.get(note["id"], 0)

    total_due = sum(due_counts.values())
    return render_template(
        "learning/index.html",
        notes=notes,
        total_due=total_due,
    )


@learning_blueprint.route("/review")
@login_required
def review():
    notes = _load_notes()
    cards = _build_cards(notes)
    progress_map = _progress_map([card["card_id"] for card in cards])
    now = datetime.now(timezone.utc)

    due_cards = []
    for card in cards:
        progress = progress_map.get(card["card_id"])
        if progress is None or progress.next_review <= now:
            due_cards.append(card)

    due_cards.sort(
        key=lambda card: (
            progress_map.get(card["card_id"]).next_review
            if progress_map.get(card["card_id"])
            else now
        )
    )

    return render_template(
        "learning/review.html",
        cards=due_cards,
    )


@learning_blueprint.route("/note/<note_id>")
@login_required
def note(note_id):
    note_data = _load_note(note_id)
    if note_data is None:
        abort(404)
    return render_template("learning/note.html", note=note_data)


@learning_blueprint.route("/rate", methods=["POST"])
@login_required
def rate_card():
    payload = request.get_json(silent=True) or {}
    card_id = payload.get("card_id")
    rating = payload.get("rating")
    response_ms = payload.get("response_ms")
    session_id = payload.get("session_id")

    if not card_id or rating is None:
        return jsonify({"error": "card_id and rating are required"}), 400

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be an integer"}), 400

    if rating < 0 or rating > 5:
        return jsonify({"error": "rating must be between 0 and 5"}), 400

    notes = _load_notes()
    cards = _build_cards(notes)
    if card_id not in {card["card_id"] for card in cards}:
        return jsonify({"error": "card not found"}), 404

    progress = ReviewProgress.query.filter_by(
        user_id=current_user.id, card_id=card_id
    ).one_or_none()

    now = datetime.now(timezone.utc)
    if progress is None:
        progress = ReviewProgress(
            user_id=current_user.id,
            card_id=card_id,
            scheduler_version=SCHEDULER_VERSION,
            learning_state="new",
            step_index=None,
            lapses=0,
            last_rating=None,
            easiness=2.5,
            interval=1,
            repetitions=0,
            next_review=now,
        )
    before = {
        "learning_state": progress.learning_state,
        "step_index": progress.step_index,
        "lapses": progress.lapses,
        "interval": progress.interval,
        "easiness": progress.easiness,
        "repetitions": progress.repetitions,
        "next_review": progress.next_review,
    }

    schedule = compute_schedule(
        progress.learning_state,
        progress.step_index,
        progress.easiness,
        progress.interval,
        progress.repetitions,
        progress.lapses,
        rating,
        now,
    )

    progress.learning_state = schedule["learning_state"]
    progress.step_index = schedule["step_index"]
    progress.easiness = schedule["easiness"]
    progress.interval = schedule["interval"]
    progress.repetitions = schedule["repetitions"]
    progress.lapses = schedule["lapses"]
    progress.next_review = schedule["next_review"]
    progress.last_reviewed = now
    progress.last_rating = rating
    progress.scheduler_version = SCHEDULER_VERSION

    log_entry = ReviewLog(
        user_id=current_user.id,
        card_id=card_id,
        reviewed_at=now,
        rating=rating,
        scheduler_version=SCHEDULER_VERSION,
        learning_state_before=before["learning_state"],
        learning_state_after=progress.learning_state,
        step_index_before=before["step_index"],
        step_index_after=progress.step_index,
        lapses_before=before["lapses"],
        lapses_after=progress.lapses,
        interval_before=before["interval"],
        easiness_before=before["easiness"],
        repetitions_before=before["repetitions"],
        next_review_before=before["next_review"],
        interval_after=progress.interval,
        easiness_after=progress.easiness,
        repetitions_after=progress.repetitions,
        next_review_after=progress.next_review,
        response_ms=response_ms,
        session_id=session_id,
    )

    db.session.add(progress)
    db.session.add(log_entry)
    db.session.commit()

    return jsonify(
        {
            "card_id": progress.card_id,
            "learning_state": progress.learning_state,
            "interval": progress.interval,
            "repetitions": progress.repetitions,
            "easiness": progress.easiness,
            "next_review": progress.next_review.isoformat(),
            "next_review_display": _format_next_review_display(
                now, progress.next_review, before["learning_state"], progress.learning_state
            ),
        }
    )
