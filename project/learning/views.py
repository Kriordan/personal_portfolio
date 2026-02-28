import json
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from project.database import db
from project.learning.queue_builder import build_review_queue
from project.learning.scheduler_config import get_effective_target_recall
from project.learning.schedulers import ScheduleInput
from project.learning.schedulers.factory import get_scheduler
from project.models import ReviewLog, ReviewProgress

from . import learning_blueprint


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


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", value or "").strip().lower()
    return re.sub(r"[\s_-]+", "-", cleaned).strip("-")


def _ensure_unique_card_id(note, desired_id):
    existing_ids = {card.get("id") for card in note.get("flashcards", [])}
    if desired_id and desired_id not in existing_ids:
        return desired_id
    base = desired_id or "inc"
    counter = 1
    candidate = f"{base}-{counter}"
    while candidate in existing_ids:
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


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
        note_tags = note.get("tags", [])
        for card in note.get("flashcards", []):
            card_id = card.get("id")
            if not card_id:
                continue
            card_tags = card.get("tags", [])
            merged_tags = list(dict.fromkeys([*note_tags, *card_tags]))
            card_type = card.get("type", "qa")
            if card_type == "incident":
                symptom = card.get("symptom", "")
                root_cause = card.get("root_cause", "")
                fix = card.get("fix", "")
                prevention = card.get("prevention", "")
                prompt = (
                    f"Symptom: {symptom}\n\n"
                    "What's the likely root cause? How do you fix it? "
                    "How do you prevent regression?"
                )
                response_parts = []
                if root_cause:
                    response_parts.append(f"Root cause: {root_cause}")
                if fix:
                    response_parts.append(f"Fix: {fix}")
                if prevention:
                    response_parts.append(f"Prevention: {prevention}")
                response = "\n".join(response_parts).strip()
            elif card_type == "cloze":
                text = card.get("text", "")
                prompt = re.sub(r"\{\{c\d+::(.*?)\}\}", "[...]", text)
                response = re.sub(r"\{\{c\d+::(.*?)\}\}", r"\1", text).strip()
            elif card_type == "command":
                prompt = card.get("prompt", "")
                response = card.get("answer", "")
            elif card_type == "code_diff":
                prompt = f"{card.get('prompt', '')}\n\nWhat code change fixes this?"
                before = card.get("before", "")
                after = card.get("after", "")
                response = f"Before:\n{before}\n\nAfter:\n{after}".strip()
            else:
                prompt = card.get("question", "")
                response = card.get("answer", "")
            cards.append(
                {
                    "card_id": f"{note_id}:{card_id}",
                    "note_id": note_id,
                    "note_title": note_title,
                    "type": card_type,
                    "tags": merged_tags,
                    "prompt": prompt,
                    "response": response,
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
        if progress is not None and progress.is_suspended:
            continue
        if progress is None or progress.next_review <= now:
            due_cards.append(card)

    due_cards = build_review_queue(due_cards, progress_map)

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
    note_data["flashcards"] = _build_cards([note_data])
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
    card_lookup = {card["card_id"]: card for card in cards}
    if card_id not in card_lookup:
        return jsonify({"error": "card not found"}), 404
    card = card_lookup[card_id]
    effective_target_recall = get_effective_target_recall(card.get("tags", []))

    progress = ReviewProgress.query.filter_by(
        user_id=current_user.id, card_id=card_id
    ).one_or_none()

    now = datetime.now(timezone.utc)
    if progress is None:
        progress = ReviewProgress(
            user_id=current_user.id,
            card_id=card_id,
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
        "half_life_days": progress.half_life_days,
        "predicted_recall": progress.predicted_recall,
        "interval": progress.interval,
        "easiness": progress.easiness,
        "repetitions": progress.repetitions,
        "next_review": progress.next_review,
    }

    scheduler = get_scheduler(current_user.scheduler_preference)
    schedule_output = scheduler.compute(
        ScheduleInput(
            learning_state=progress.learning_state,
            step_index=progress.step_index,
            easiness=progress.easiness,
            interval=progress.interval,
            repetitions=progress.repetitions,
            lapses=progress.lapses,
            half_life_days=progress.half_life_days,
            predicted_recall=progress.predicted_recall,
            target_recall=effective_target_recall,
            rating=rating,
            now=now,
            last_reviewed=progress.last_reviewed,
        )
    )

    progress.learning_state = schedule_output.learning_state
    progress.step_index = schedule_output.step_index
    progress.easiness = schedule_output.easiness
    progress.interval = schedule_output.interval
    progress.repetitions = schedule_output.repetitions
    progress.lapses = schedule_output.lapses
    progress.half_life_days = schedule_output.half_life_days
    progress.predicted_recall = schedule_output.predicted_recall
    progress.target_recall = effective_target_recall
    progress.next_review = schedule_output.next_review
    progress.last_reviewed = now
    progress.last_rating = rating
    progress.scheduler_version = schedule_output.scheduler_version
    if schedule_output.is_graduated and progress.graduated_at is None:
        progress.graduated_at = now
    if rating < 3 and progress.graduated_at is not None:
        progress.graduated_at = None

    log_entry = ReviewLog(
        user_id=current_user.id,
        card_id=card_id,
        reviewed_at=now,
        rating=rating,
        scheduler_version=progress.scheduler_version,
        learning_state_before=before["learning_state"],
        learning_state_after=progress.learning_state,
        step_index_before=before["step_index"],
        step_index_after=progress.step_index,
        lapses_before=before["lapses"],
        lapses_after=progress.lapses,
        half_life_before=before["half_life_days"],
        half_life_after=progress.half_life_days,
        predicted_recall_before=before["predicted_recall"],
        predicted_recall_after=progress.predicted_recall,
        target_recall=progress.target_recall,
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

    response_data = {
        "card_id": progress.card_id,
        "learning_state": progress.learning_state,
        "interval": progress.interval,
        "repetitions": progress.repetitions,
        "easiness": progress.easiness,
        "next_review": progress.next_review.isoformat(),
        "next_review_display": _format_next_review_display(
            now, progress.next_review, before["learning_state"], progress.learning_state
        ),
        "scheduler_version": progress.scheduler_version,
    }

    show_debug = current_user.is_admin
    if show_debug:
        debug_info = schedule_output.debug_info or {}
        response_data["debug"] = {
            "scheduler_version": progress.scheduler_version,
            "predicted_recall_before": debug_info.get("predicted_recall_before"),
            "predicted_recall_after": progress.predicted_recall,
            "half_life_days": progress.half_life_days,
            "target_recall": progress.target_recall,
            "next_review": progress.next_review.isoformat(),
        }

    return jsonify(response_data)


@learning_blueprint.route("/api/incident", methods=["POST"])
@login_required
def create_incident():
    if not current_user.is_admin:
        return jsonify({"error": "admin access required"}), 403

    payload = request.get_json(silent=True) or {}
    note_id = payload.get("note_id")
    title = payload.get("title")
    symptom = payload.get("symptom")
    root_cause = payload.get("root_cause")
    fix = payload.get("fix")
    prevention = payload.get("prevention", "")
    tags = payload.get("tags", [])

    if not symptom or not root_cause or not fix:
        return jsonify({"error": "symptom, root_cause, and fix are required"}), 400

    resolved_note_id = note_id or _slugify(title)
    if not resolved_note_id:
        return jsonify({"error": "note_id or title is required"}), 400

    note_path = (_notes_dir() / f"{resolved_note_id}.json").resolve()
    if not note_path.is_relative_to(_notes_dir().resolve()):
        return jsonify({"error": "invalid note_id"}), 400

    note = _load_note(resolved_note_id)
    if note is None:
        note = {
            "id": resolved_note_id,
            "title": title or resolved_note_id.replace("-", " ").title(),
            "created_at": datetime.now(timezone.utc).date().isoformat(),
            "tags": tags,
            "summary": "",
            "flashcards": [],
        }

    desired_card_id = payload.get("id")
    if desired_card_id:
        existing_ids = {card.get("id") for card in note.get("flashcards", [])}
        if desired_card_id in existing_ids:
            return jsonify({"error": "card id already exists"}), 400

    card_id = _ensure_unique_card_id(note, desired_card_id or "inc")
    new_card = {
        "id": card_id,
        "type": "incident",
        "title": title or "",
        "symptom": symptom,
        "root_cause": root_cause,
        "fix": fix,
        "prevention": prevention,
        "tags": tags,
    }
    note.setdefault("flashcards", []).append(new_card)

    note_path.write_text(
        json.dumps(note, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    return jsonify({"note_id": resolved_note_id, "card_id": card_id}), 201
