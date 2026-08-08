"""Business logic shared by learning web and API routes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project.database import db
from project.learning.queue_builder import build_review_queue
from project.learning.scheduler_config import get_effective_target_recall
from project.learning.schedulers import ScheduleInput
from project.learning.schedulers.factory import get_scheduler
from project.models import ReviewLog, ReviewProgress, User


class LearningServiceError(Exception):
    """Base learning service exception."""


class NotFoundError(LearningServiceError):
    """Raised when requested learning content does not exist."""


class ValidationError(LearningServiceError):
    """Raised when service input fails validation."""


class ConflictError(LearningServiceError):
    """Raised when a resource conflict occurs."""


def _ensure_aware(value: datetime) -> datetime:
    """Coerce naive datetimes to UTC.

    Some DB backends/tests may deserialize timezone columns as naive values.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def notes_dir_for_root(root_path: str) -> Path:
    """Return notes directory for a Flask app root."""
    return Path(root_path).parent / "notes"


def _validated_note_path(notes_dir: Path, note_id: str) -> Path:
    """Return a contained JSON path for a validated note ID."""
    if (
        not isinstance(note_id, str)
        or len(note_id) > 100
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", note_id)
    ):
        raise ValidationError("invalid note_id")

    resolved_notes_dir = notes_dir.resolve()
    note_path = (resolved_notes_dir / f"{note_id}.json").resolve()
    if not note_path.is_relative_to(resolved_notes_dir):
        raise ValidationError("invalid note_id")
    return note_path


def load_note(notes_dir: Path, note_id: str) -> dict[str, Any] | None:
    """Load a single note JSON file by ID."""
    try:
        note_path = _validated_note_path(notes_dir, note_id)
    except ValidationError:
        return None
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


def load_notes(notes_dir: Path) -> list[dict[str, Any]]:
    """Load all note JSON files under notes directory."""
    notes = []
    for note_path in sorted(notes_dir.glob("*.json")):
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


def build_cards(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten note flashcards into review-card payloads."""
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


def progress_map(card_ids: list[str], user_id: int) -> dict[str, ReviewProgress]:
    """Load review progress rows for a user and card IDs."""
    if not card_ids:
        return {}
    progress_rows = ReviewProgress.query.filter(
        ReviewProgress.user_id == user_id,
        ReviewProgress.card_id.in_(card_ids),
    ).all()
    return {row.card_id: row for row in progress_rows}


def summarize_notes_for_user(
    notes: list[dict[str, Any]],
    *,
    user_id: int,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Attach due/flashcard counts and return total due count."""
    review_now = now or datetime.now(timezone.utc)
    cards = build_cards(notes)
    progress_by_card = progress_map([card["card_id"] for card in cards], user_id)
    due_counts: dict[str, int] = {}
    for card in cards:
        progress = progress_by_card.get(card["card_id"])
        is_due = progress is None or _ensure_aware(progress.next_review) <= review_now
        if is_due:
            due_counts[card["note_id"]] = due_counts.get(card["note_id"], 0) + 1

    for note in notes:
        note["flashcard_count"] = len(note.get("flashcards", []))
        note["due_count"] = due_counts.get(note["id"], 0)
    return notes, sum(due_counts.values())


def note_with_cards(notes_dir: Path, note_id: str) -> dict[str, Any]:
    """Load a note and transform flashcards into rendered cards."""
    note_data = load_note(notes_dir, note_id)
    if note_data is None:
        raise NotFoundError("note not found")
    note_data["flashcards"] = build_cards([note_data])
    return note_data


def review_cards_for_user(
    notes: list[dict[str, Any]],
    *,
    user_id: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return due cards in queue order for review."""
    review_now = now or datetime.now(timezone.utc)
    cards = build_cards(notes)
    progress_by_card = progress_map([card["card_id"] for card in cards], user_id)
    due_cards = []
    for card in cards:
        progress = progress_by_card.get(card["card_id"])
        if progress is not None and progress.is_suspended:
            continue
        if progress is None or _ensure_aware(progress.next_review) <= review_now:
            due_cards.append(card)
    return build_review_queue(due_cards, progress_by_card)


def rate_card_for_user(
    *,
    user: User,
    notes_dir: Path,
    card_id: str,
    rating: int,
    response_ms: int | None = None,
    session_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply a rating to a card and persist progress/log records."""
    if rating < 0 or rating > 5:
        raise ValidationError("rating must be between 0 and 5")

    parts = card_id.split(":", 1)
    if len(parts) != 2:
        raise ValidationError("invalid card_id format")
    note_id, _ = parts

    note = load_note(notes_dir, note_id)
    if note is None:
        raise NotFoundError("card not found")

    cards = build_cards([note])
    card_lookup = {card["card_id"]: card for card in cards}
    card = card_lookup.get(card_id)
    if card is None:
        raise NotFoundError("card not found")

    effective_target_recall = get_effective_target_recall(card.get("tags", []))
    progress = ReviewProgress.query.filter_by(user_id=user.id, card_id=card_id).one_or_none()
    review_now = now or datetime.now(timezone.utc)

    if progress is None:
        progress = ReviewProgress(
            user_id=user.id,
            card_id=card_id,
            learning_state="new",
            step_index=None,
            lapses=0,
            last_rating=None,
            easiness=2.5,
            interval=1,
            repetitions=0,
            next_review=review_now,
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

    scheduler = get_scheduler(user.scheduler_preference)
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
            now=review_now,
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
    progress.last_reviewed = review_now
    progress.last_rating = rating
    progress.scheduler_version = schedule_output.scheduler_version
    if schedule_output.is_graduated and progress.graduated_at is None:
        progress.graduated_at = review_now
    if rating < 3 and progress.graduated_at is not None:
        progress.graduated_at = None

    db.session.add(progress)
    db.session.add(
        ReviewLog(
            user_id=user.id,
            card_id=card_id,
            reviewed_at=review_now,
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
    )
    db.session.commit()

    response_data = {
        "card_id": progress.card_id,
        "learning_state": progress.learning_state,
        "interval": progress.interval,
        "repetitions": progress.repetitions,
        "easiness": progress.easiness,
        "next_review": progress.next_review.isoformat(),
        "next_review_display": format_next_review_display(
            review_now,
            progress.next_review,
            before["learning_state"],
            progress.learning_state,
        ),
        "scheduler_version": progress.scheduler_version,
    }

    if user.is_admin:
        debug_info = schedule_output.debug_info or {}
        response_data["debug"] = {
            "scheduler_version": progress.scheduler_version,
            "predicted_recall_before": debug_info.get("predicted_recall_before"),
            "predicted_recall_after": progress.predicted_recall,
            "half_life_days": progress.half_life_days,
            "target_recall": progress.target_recall,
            "next_review": progress.next_review.isoformat(),
        }
    return response_data


def slugify(value: str) -> str:
    """Create a normalized slug ID from text."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", value or "").strip().lower()
    return re.sub(r"[\s_-]+", "-", cleaned).strip("-")


def ensure_unique_card_id(note: dict[str, Any], desired_id: str | None) -> str:
    """Generate a unique card ID within a note."""
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


def create_incident_card(
    *,
    notes_dir: Path,
    note_id: str | None,
    title: str | None,
    symptom: str | None,
    root_cause: str | None,
    fix: str | None,
    prevention: str | None = "",
    tags: list[str] | None = None,
    desired_card_id: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Create and persist an incident card in a note file."""
    if not symptom or not root_cause or not fix:
        raise ValidationError("symptom, root_cause, and fix are required")

    resolved_note_id = note_id or slugify(title or "")
    if not resolved_note_id:
        raise ValidationError("note_id or title is required")
    note_path = _validated_note_path(notes_dir, resolved_note_id)

    note = load_note(notes_dir, resolved_note_id)
    normalized_tags = tags or []
    if note is None:
        created_on = (now or datetime.now(timezone.utc)).date().isoformat()
        note = {
            "id": resolved_note_id,
            "title": title or resolved_note_id.replace("-", " ").title(),
            "created_at": created_on,
            "tags": normalized_tags,
            "summary": "",
            "flashcards": [],
        }

    if desired_card_id:
        existing_ids = {card.get("id") for card in note.get("flashcards", [])}
        if desired_card_id in existing_ids:
            raise ConflictError("card id already exists")

    card_id = ensure_unique_card_id(note, desired_card_id or "inc")
    note.setdefault("flashcards", []).append(
        {
            "id": card_id,
            "type": "incident",
            "title": title or "",
            "symptom": symptom,
            "root_cause": root_cause,
            "fix": fix,
            "prevention": prevention or "",
            "tags": normalized_tags,
        }
    )
    note_path.write_text(
        json.dumps(note, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return resolved_note_id, card_id


def format_next_review_display(
    now: datetime,
    next_review: datetime,
    before_state: str | None,
    after_state: str,
) -> str:
    """Build user-facing next review text."""
    delta = _ensure_aware(next_review) - now
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
