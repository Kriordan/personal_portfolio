"""Business logic shared by learning web and API routes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from werkzeug.utils import secure_filename

from project.database import db
from project.learning.queue_builder import build_review_queue
from project.learning.scheduler_config import get_effective_target_recall
from project.learning.schedulers import ScheduleInput
from project.learning.schedulers.factory import get_scheduler
from project.models import ReviewLog, ReviewProgress, ReviewReceipt, User


class LearningServiceError(Exception):
    """Base learning service exception."""


class NotFoundError(LearningServiceError):
    """Raised when requested learning content does not exist."""


class ValidationError(LearningServiceError):
    """Raised when service input fails validation."""


class InvalidRatingError(ValidationError):
    """Raised when a review rating is outside the supported range."""


class InvalidCardIdError(ValidationError):
    """Raised when a review card ID does not use the expected format."""


class ConflictError(LearningServiceError):
    """Raised when a resource conflict occurs."""


class StaleReviewError(ConflictError):
    """Another client changed this card after the queue was loaded."""


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
    if not isinstance(note_id, str) or len(note_id) > 100:
        raise ValidationError("invalid note_id")

    safe_note_id = secure_filename(note_id)
    if safe_note_id != note_id or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", safe_note_id
    ):
        raise ValidationError("invalid note_id")

    resolved_notes_dir = notes_dir.resolve()
    note_path = (resolved_notes_dir / f"{safe_note_id}.json").resolve()
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

    if not isinstance(data, dict) or data.get("id", note_id) != note_id:
        return None
    data.setdefault("id", note_id)
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        data["title"] = note_id.replace("-", " ").title()
    if not isinstance(data.get("summary"), str):
        data["summary"] = ""
    data["tags"] = _tags(data.get("tags"))
    if not isinstance(data.get("created_at"), str):
        data["created_at"] = None
    data.setdefault("flashcards", [])
    return data


def load_notes(notes_dir: Path) -> list[dict[str, Any]]:
    """Load all note JSON files under notes directory."""
    notes = []
    for note_path in sorted(notes_dir.glob("*.json")):
        data = load_note(notes_dir, note_path.stem)
        if data is not None:
            notes.append(data)
    return notes


def build_cards(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten note flashcards into review-card payloads."""
    cards = []
    seen = set()
    for note in notes:
        note_id = note.get("id")
        note_title = note.get("title")
        note_tags = _tags(note.get("tags"))
        raw_cards = note.get("flashcards", [])
        for card in raw_cards if isinstance(raw_cards, list) else []:
            if not isinstance(card, dict):
                continue
            card_id = card.get("id")
            if (not isinstance(card_id, str) or not card_id or ":" in card_id
                    or len(f"{note_id}:{card_id}") > 128 or (note_id, card_id) in seen):
                continue
            card_tags = _tags(card.get("tags"))
            merged_tags = list(dict.fromkeys([*note_tags, *card_tags]))
            card_type = card.get("type", "qa")
            fields = {
                "qa": ("question", "answer"), "incident": ("symptom", "root_cause", "fix"),
                "cloze": ("text",), "command": ("prompt", "answer"),
                "code_diff": ("prompt", "before", "after"),
            }
            if not isinstance(card_type, str) or card_type not in fields:
                continue
            if any(not isinstance(card.get(key), str) or not card[key].strip() for key in fields[card_type]):
                continue
            seen.add((note_id, card_id))
            sections = []
            if card_type == "incident":
                symptom = card.get("symptom", "")
                root_cause = card.get("root_cause", "")
                fix = card.get("fix", "")
                prevention = card.get("prevention", "") if isinstance(card.get("prevention", ""), str) else ""
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
                sections = [{"label": label, "text": value, "code": False} for label, value in
                            (("Root cause", root_cause), ("Fix", fix), ("Prevention", prevention)) if value]
            elif card_type == "cloze":
                text = card.get("text", "")
                prompt = re.sub(r"\{\{c\d+::(.*?)\}\}", "[...]", text)
                response = re.sub(r"\{\{c\d+::(.*?)\}\}", r"\1", text).strip()
            elif card_type == "command":
                prompt = card.get("prompt", "")
                response = card.get("answer", "")
                sections = [{"label": "Command", "text": response, "code": True}]
            elif card_type == "code_diff":
                prompt = f"{card.get('prompt', '')}\n\nWhat code change fixes this?"
                before = card.get("before", "")
                after = card.get("after", "")
                response = f"Before:\n{before}\n\nAfter:\n{after}".strip()
                sections = [{"label": label, "text": value, "code": True} for label, value in
                            (("Before", before), ("After", after))]
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
                    "response_sections": sections,
                }
            )
    return cards


def _tags(value: Any) -> list[str]:
    return [tag for tag in value if isinstance(tag, str)] if isinstance(value, list) else []


def _is_due(progress: ReviewProgress | None, now: datetime) -> bool:
    return progress is None or (not progress.is_suspended and _ensure_aware(progress.next_review) <= now)


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
    card_counts: dict[str, int] = {}
    for card in cards:
        card_counts[card["note_id"]] = card_counts.get(card["note_id"], 0) + 1
        progress = progress_by_card.get(card["card_id"])
        if _is_due(progress, review_now):
            due_counts[card["note_id"]] = due_counts.get(card["note_id"], 0) + 1

    for note in notes:
        note["flashcard_count"] = card_counts.get(note["id"], 0)
        note["due_count"] = due_counts.get(note["id"], 0)
    return notes, sum(due_counts.values())


def note_with_cards(notes_dir: Path, note_id: str, user_id: int | None = None) -> dict[str, Any]:
    """Load a note and transform flashcards into rendered cards."""
    note_data = load_note(notes_dir, note_id)
    if note_data is None:
        raise NotFoundError("note not found")
    if user_id is not None:
        summarize_notes_for_user([note_data], user_id=user_id)
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
        if _is_due(progress, review_now):
            card["progress_revision"] = progress.revision if progress else 0
            due_cards.append(card)
    return build_review_queue(due_cards, progress_by_card)


def review_page(notes_dir: Path, *, user_id: int, note_id: str | None = None, limit: int | None = None) -> dict:
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 100):
        raise ValidationError("invalid limit")
    if note_id is not None:
        note = load_note(notes_dir, note_id)
        if note is None:
            raise NotFoundError("note not found")
        notes = [note]
    else:
        notes = load_notes(notes_dir)
    cards = review_cards_for_user(notes, user_id=user_id)
    return {"cards": cards[:limit] if limit else cards, "total_due": len(cards)}


def validate_request_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("invalid request_id")
    try:
        normalized = str(UUID(value))
    except (ValueError, AttributeError):
        raise ValidationError("invalid request_id") from None
    if value != normalized:
        raise ValidationError("invalid request_id")
    return value


def rating_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("expected an object")
    return {key: payload.get(key) for key in (
        "card_id", "rating", "response_ms", "session_id", "request_id", "expected_revision"
    )}


def _receipt_response(receipt: ReviewReceipt, user: User) -> dict:
    result = dict(receipt.response)
    if not user.is_admin:
        result.pop("debug", None)
    return result


def rating_receipt(user: User, request_id: str) -> dict | None:
    validate_request_id(request_id)
    receipt = db.session.get(ReviewReceipt, (user.id, request_id))
    return _receipt_response(receipt, user) if receipt else None


def rate_card_for_user(*, user: User, notes_dir: Path, card_id: str, rating: int,
                       response_ms: int | None = None, session_id: str | None = None,
                       request_id: str | None = None, expected_revision: int | None = None,
                       now: datetime | None = None) -> dict[str, Any]:
    """Serialize ratings, committing progress, a log, and its receipt atomically."""
    if type(rating) is not int or not 0 <= rating <= 5:
        raise InvalidRatingError("rating must be an integer between 0 and 5")
    if not isinstance(card_id, str) or len(card_id) > 128 or ":" not in card_id:
        raise InvalidCardIdError("invalid card_id format")
    if response_ms is not None and (type(response_ms) is not int or not 0 <= response_ms <= 86_400_000):
        raise ValidationError("invalid response_ms")
    if session_id is not None and (not isinstance(session_id, str) or not 1 <= len(session_id) <= 64):
        raise ValidationError("invalid session_id")
    if expected_revision is not None and (type(expected_revision) is not int or not 0 <= expected_revision <= 2_147_483_647):
        raise ValidationError("invalid revision")
    if request_id is not None:
        validate_request_id(request_id)
        if expected_revision is None:
            raise ValidationError("expected_revision required with request_id")
    payload = dict(card_id=card_id, rating=rating, response_ms=response_ms,
                   session_id=session_id, expected_revision=expected_revision)
    try:
        # The user row exists before a first review. Locking only a progress row
        # would leave concurrent first reviews unprotected. SQLite fixtures need
        # a write lock because SELECT FOR UPDATE is a no-op on that backend.
        if db.session.get_bind().dialect.name == "sqlite":
            db.session.execute(update(User).where(User.id == user.id).values(id=User.id))
        else:
            db.session.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()
        if request_id:
            receipt = db.session.get(ReviewReceipt, (user.id, request_id))
            if receipt:
                if receipt.payload != payload:
                    raise ConflictError("This request ID was already used for a different rating.")
                result = _receipt_response(receipt, user)
                db.session.commit()
                return result
        result = _apply_rating(user=user, notes_dir=notes_dir, card_id=card_id, rating=rating,
                               response_ms=response_ms, session_id=session_id,
                               expected_revision=expected_revision, now=now)
        if request_id:
            result["request_id"] = request_id
            db.session.add(ReviewReceipt(user_id=user.id, request_id=request_id, payload=payload,
                                         response=result, created_at=now or datetime.now(timezone.utc)))
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def _apply_rating(
    *,
    user: User,
    notes_dir: Path,
    card_id: str,
    rating: int,
    response_ms: int | None = None,
    session_id: str | None = None,
    expected_revision: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply a rating to a card and persist progress/log records."""
    if rating < 0 or rating > 5:
        raise InvalidRatingError("rating must be between 0 and 5")

    if not isinstance(card_id, str):
        raise InvalidCardIdError("invalid card_id format")

    parts = card_id.split(":", 1)
    if len(parts) != 2:
        raise InvalidCardIdError("invalid card_id format")
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
    progress = ReviewProgress.query.filter_by(user_id=user.id, card_id=card_id).populate_existing().one_or_none()
    if expected_revision is not None and (
        expected_revision != (progress.revision if progress else 0)
        or (progress is not None and progress.is_suspended)
    ):
        raise StaleReviewError("This card changed elsewhere. Load a fresh review queue.")
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
            revision=0,
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
    progress.revision += 1
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
        "progress_revision": progress.revision,
        "saved_at": review_now.isoformat(),
        "rating": rating,
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
