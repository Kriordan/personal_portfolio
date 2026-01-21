import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from project.database import db
from project.models import ReviewProgress

from . import learning_blueprint
from .spaced_repetition import update_schedule


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

    if progress is None:
        progress = ReviewProgress(
            user_id=current_user.id,
            card_id=card_id,
            easiness=2.5,
            interval=1,
            repetitions=0,
            next_review=datetime.now(timezone.utc),
        )

    progress.easiness, progress.interval, progress.repetitions = update_schedule(
        progress.easiness, progress.interval, progress.repetitions, rating
    )
    now = datetime.now(timezone.utc)
    progress.last_reviewed = now
    progress.next_review = now + timedelta(days=progress.interval)

    db.session.add(progress)
    db.session.commit()

    return jsonify(
        {
            "card_id": progress.card_id,
            "interval": progress.interval,
            "repetitions": progress.repetitions,
            "easiness": progress.easiness,
            "next_review": progress.next_review.isoformat(),
        }
    )
