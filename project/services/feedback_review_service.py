"""Learner decisions and optional extra recall practice, with the existing scheduler.

Annotations have optimistic revisions and content-free practice receipts. Extra
practice is one pass per finding; its completion is derived from existing review
logs, whose opaque session tag records the source without storing feedback text.
Only explicit ratings change scheduling. No generation or new queue is involved.
"""
from datetime import timezone

from flask import current_app
from sqlalchemy import select

from project.database import db
from project.learning.content_schema import evaluator_view
from project.models import PracticeFeedback, PracticeFeedbackAnnotation, ReviewLog, ReviewReceipt
from project.services import curriculum_service, feedback_service, learning_service, practice_service as practice
from project.services.learning_errors import ConflictError, NotFoundError, StaleReviewError

DECISIONS = ("unreviewed", "agree", "disagree")
NOTE_LIMIT = 2000


class AnnotationConflict(ConflictError):
    def __init__(self, current):
        super().__init__("Your response changed in another tab.")
        self.current = current


class DecisionRequired(ConflictError):
    """A new follow-up rating requires the learner's current agreement."""


def annotation_dto(row=None):
    return {"revision": row.revision if row else 0, "decision": row.decision if row else "unreviewed",
            "note": row.note if row else "",
            "updated_at": practice._iso(practice._aware(row.updated_at).astimezone(timezone.utc)) if row else None}


def annotations(request_id):
    return {r.finding_id: annotation_dto(r) for r in db.session.scalars(select(PracticeFeedbackAnnotation).where(
        PracticeFeedbackAnnotation.feedback_request_id == request_id))}


def targets(session, finding):
    """Resolve private IDs to authored public question identities; never return the mapping packet."""
    if finding["kind"] != "concern":
        return []
    assessment = evaluator_view(practice._pinned_exercise(session).payload)
    mappings = {m["id"]: m for m in assessment.get("misconceptions", [])}
    return list(dict.fromkeys((mappings[key]["concept_id"], question)
        for key in finding["misconception_ids"] if key in mappings
        for question in mappings[key]["review_question_ids"]))


def _finding(user_id, session_id, sequence, finding_id):
    session = practice._owned_session(user_id, session_id)
    snapshot = feedback_service._snapshot(session, sequence)
    result = db.session.scalar(select(PracticeFeedback).where(PracticeFeedback.submission_id == snapshot.id))
    finding = next((f for f in result.data["findings"] if f["id"] == finding_id), None) if result else None
    if finding is None:
        raise NotFoundError("finding not found")
    return session, result, finding


def _annotation(result, finding):
    return db.session.get(PracticeFeedbackAnnotation, (result.request_id, finding["id"]), populate_existing=True)


def annotate(user, session_id, sequence, finding_id, *, decision, note, expected_revision, request_id, now=None):
    practice.validate_request_id(request_id)
    if decision not in DECISIONS or not practice._whole_number(expected_revision, minimum=0):
        raise practice.PracticeValidationError("Choose a response and a valid revision.")
    if not isinstance(note, str) or "\x00" in note:
        raise practice.PracticeValidationError("Use plain text for your note.")
    note = note.replace("\r\n", "\n").replace("\r", "\n")
    try:
        note.encode("utf-8")
    except UnicodeEncodeError:
        raise practice.PracticeValidationError("Use valid text for your note.") from None
    if len(note) > NOTE_LIMIT:
        raise practice.PracticeValidationError("Keep the note to 2,000 characters or fewer.")
    digest = practice._digest("annotate", session_id, dict(sequence=sequence, finding_id=finding_id,
        decision=decision, note=note, expected_revision=expected_revision))
    now = now or practice._now()
    try:
        practice._lock_owner(user.id)
        replay = practice._replay(user.id, request_id, "annotate", digest)
        if replay is not None:
            db.session.commit()
            return replay
        _, result, finding = _finding(user.id, session_id, sequence, finding_id)
        row = _annotation(result, finding)
        current = annotation_dto(row)
        if current["revision"] != expected_revision:
            raise AnnotationConflict(current)
        changed = current["decision"] != decision or current["note"] != note
        revision = current["revision"] + int(changed)
        if changed:
            if row is None:
                row = PracticeFeedbackAnnotation(feedback_request_id=result.request_id, finding_id=finding_id)
                db.session.add(row)
            row.decision, row.note, row.revision, row.updated_at = decision, note, revision, now
        response = dict(session_id=session_id, submission_sequence=sequence, finding_id=finding_id,
                        revision=revision, changed=changed)
        practice._record(user.id, request_id, session_id, "annotate", digest, response, now)
        db.session.commit()
        return response
    except Exception:
        db.session.rollback()
        raise


def _tag(result, finding):
    return f"feedback:{result.request_id}:{finding['id']}"


def _completed(user_id, result, finding):
    return set(db.session.scalars(select(ReviewLog.card_id).where(
        ReviewLog.user_id == user_id, ReviewLog.session_id == _tag(result, finding))))


def review_detail(user_id, session_id, sequence, finding_id):
    session, result, finding = _finding(user_id, session_id, sequence, finding_id)
    decision = annotation_dto(_annotation(result, finding))["decision"]
    questions, unavailable, completed = [], 0, _completed(user_id, result, finding)
    linked = targets(session, finding)
    if decision == "agree":
        for concept_id, question_id in linked:
            if question_id in completed:
                continue
            try:
                card = curriculum_service.published_review_question(concept_id, question_id)
            except (NotFoundError, ConflictError):
                unavailable += 1
                continue
            progress = learning_service.progress_map([question_id], user_id).get(question_id)
            if progress and progress.is_suspended:
                unavailable += 1
                continue
            questions.append({**card, "progress_revision": progress.revision if progress else 0})
    return {"session": practice._session_dto(session, practice._pinned_exercise(session).payload),
            "finding": {"id": finding["id"], "title": finding["title"]}, "accepted": decision == "agree",
            "questions": questions, "total": len(linked), "completed": len({q for _, q in linked} & completed),
            "unavailable": unavailable}


def review_card(user_id, session_id, sequence, finding_id, *, card_id, content_version, expected_revision, request_id):
    practice.validate_request_id(request_id)
    if not practice._whole_number(content_version, minimum=1) or not practice._whole_number(expected_revision, minimum=0):
        raise practice.PracticeValidationError("Use a valid question version and progress revision.")
    session, result, finding = _finding(user_id, session_id, sequence, finding_id)
    if annotation_dto(_annotation(result, finding))["decision"] != "agree":
        raise DecisionRequired()
    concept_id = next((c for c, q in targets(session, finding) if q == card_id), None)
    if concept_id is None:
        raise NotFoundError("question not linked")
    if card_id in _completed(user_id, result, finding):
        raise StaleReviewError()
    card = curriculum_service.published_review_question(concept_id, card_id, version=content_version, reveal_answer=True)
    progress = learning_service.progress_map([card_id], user_id).get(card_id)
    if expected_revision != (progress.revision if progress else 0) or (progress and progress.is_suspended):
        raise StaleReviewError()
    return card


def rate_review(user, session_id, sequence, finding_id, *, card_id, content_version, expected_revision, request_id, rating):
    """Hold the owner lock through authorization and the existing rating transaction.

    This serializes disagreement/deletion with rating and prevents two different
    attempts finishing the same follow-up question. Same-ID replays still succeed
    after agreement is withdrawn; they replay history rather than rating again.
    """
    practice.validate_request_id(request_id)
    try:
        practice._lock_owner(user.id)
        _, result, finding = _finding(user.id, session_id, sequence, finding_id)
        receipt = db.session.get(ReviewReceipt, (user.id, request_id), populate_existing=True)
        if receipt is None:
            review_card(user.id, session_id, sequence, finding_id, card_id=card_id,
                        content_version=content_version, expected_revision=expected_revision, request_id=request_id)
        return learning_service.rate_card_for_user(user=user,
            notes_dir=learning_service.notes_dir_for_root(current_app.root_path),
            card_id=card_id, content_version=content_version, expected_revision=expected_revision,
            request_id=request_id, rating=rating, session_id=_tag(result, finding))
    except Exception:
        db.session.rollback()
        raise
