"""Practice sessions: a pinned exercise, an ordered record, and immutable artifact revisions.

Every mutation follows one order: validate input, take the owner's user-row lock, check
the request receipt, read owner-scoped rows fresh, write, record the receipt, commit.
Later writers (the AI worker, deletion) must take the same lock first.

Learner text never goes into receipts (they store a payload hash) or log messages.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, select, update

from project.curriculum_terms import ARTIFACT_LANGUAGES, FORMAT_LANGUAGES
from project.database import db
from project.learning.content_schema import learner_view, opening_view
from project.models import (
    ArtifactRevision, ContentRevision, CurriculumItem, PracticeReceipt, PracticeSession,
    SessionMessage, SessionMessageArtifact, User,
)
from project.services import curriculum_service
from project.services.learning_service import ConflictError, NotFoundError, ValidationError, validate_request_id

ARTIFACT_MAX_BYTES = 64 * 1024
MAX_EDITS = 20
MAX_INT = 2_147_483_647
LISTED_SESSIONS = 20
OPEN_STATUSES = ("active", "paused")
EDIT_FIELDS = {"artifact_id", "base_revision", "language", "body"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*(?::[a-z0-9-]+)?")


class PracticeValidationError(ValidationError):
    """Input the learner can correct. `field` names the artifact it concerns, if any."""

    def __init__(self, message, *, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


class RequestConflictError(ConflictError):
    """The request ID was already used for a different change."""

    code = "request_conflict"


class StaleArtifactError(ConflictError):
    """An artifact changed elsewhere after this view loaded. Nothing was saved."""

    code = "stale_artifact"

    def __init__(self, conflicts):
        super().__init__("An artifact changed elsewhere.")
        # Each entry: artifact_id, base_revision, and the current revision, language and body.
        self.conflicts = conflicts


def describe_failure(exc):
    """A log-safe summary of a database failure: class, SQLSTATE, and constraint name.

    Never log str(exc): PostgreSQL's DETAIL line can quote the failing row, including
    learner text, even when SQL parameters are hidden.
    """
    orig = getattr(exc, "orig", None)
    parts = [type(exc).__name__]
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "sqlite_errorname", None)
    if isinstance(sqlstate, str) and re.fullmatch(r"[A-Z0-9_]{1,40}", sqlstate):
        parts.append(f"sqlstate={sqlstate}")
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if isinstance(constraint, str) and re.fullmatch(r"[a-z0-9_]{1,63}", constraint):
        parts.append(f"constraint={constraint}")
    return " ".join(parts)


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite returns naive timestamps
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest(operation, session_id, payload):
    canonical = json.dumps({"operation": operation, "session": session_id, "payload": payload},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256(canonical)


def default_language(artifact_format):
    return FORMAT_LANGUAGES[artifact_format][0]


def normalize_text(value, *, field=None, limit, label="This text"):
    """Store one canonical form: LF line endings, valid UTF-8, no NUL, within the byte limit."""
    if not isinstance(value, str):
        raise PracticeValidationError(f"{label} is missing.", field=field)
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text:
        raise PracticeValidationError(f"{label} contains a NUL character, which can't be saved.", field=field)
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        raise PracticeValidationError(f"{label} contains an invalid character.", field=field) from None
    if size > limit:
        raise PracticeValidationError(
            f"{label} is {size / 1024:.1f} KiB; the limit is {limit // 1024} KiB.", field=field)
    return text


def _check_session_id(session_id):
    """Malformed IDs are simply not found, like another account's sessions."""
    try:
        if not isinstance(session_id, str) or str(UUID(session_id)) != session_id:
            raise ValueError
    except ValueError:
        raise NotFoundError("practice session not found") from None


def _lock_owner(user_id):
    """Serialize this owner's practice writes. The user row exists before any practice row."""
    if db.session.get_bind().dialect.name == "sqlite":
        # SELECT ... FOR UPDATE is a no-op on SQLite; a write takes its database lock.
        db.session.execute(update(User).where(User.id == user_id).values(id=User.id))
    else:
        db.session.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()


def _replay(user_id, request_id, operation, digest):
    receipt = db.session.execute(select(PracticeReceipt).where(
        PracticeReceipt.user_id == user_id, PracticeReceipt.request_id == request_id
    ).execution_options(populate_existing=True)).scalar_one_or_none()
    if receipt is None:
        return None
    if receipt.operation != operation or receipt.payload_sha256 != digest:
        raise RequestConflictError("This request ID was already used for a different change.")
    return receipt.response


def _record(user_id, request_id, session_id, operation, digest, response, now):
    db.session.add(PracticeReceipt(user_id=user_id, request_id=request_id, practice_session_id=session_id,
                                   operation=operation, payload_sha256=digest, response=response, created_at=now))


def _owned_session(user_id, session_id):
    _check_session_id(session_id)
    session = db.session.execute(select(PracticeSession).where(
        PracticeSession.id == session_id, PracticeSession.user_id == user_id
    ).execution_options(populate_existing=True)).scalar_one_or_none()
    if session is None:
        raise NotFoundError("practice session not found")
    return session


def _pinned_exercise(session):
    return db.session.get(ContentRevision, (session.exercise_id, session.exercise_version))


def _artifact_specs(payload):
    """The pinned exercise's expected artifacts, in authored order."""
    return {spec["id"]: spec for spec in payload["content"]["brief"]["expected_artifacts"]}


def _head(session_id, artifact_id):
    return db.session.execute(select(ArtifactRevision).where(
        ArtifactRevision.practice_session_id == session_id, ArtifactRevision.artifact_id == artifact_id
    ).order_by(ArtifactRevision.revision.desc()).limit(1).execution_options(populate_existing=True)).scalar_one_or_none()


def _revision(session_id, artifact_id, number):
    return db.session.execute(select(ArtifactRevision).where(
        ArtifactRevision.practice_session_id == session_id, ArtifactRevision.artifact_id == artifact_id,
        ArtifactRevision.revision == number,
    )).scalar_one_or_none()


def _state(row, spec):
    """What the learner sees for a revision. Revision 0 is an empty body in the default notation."""
    return (row.body, row.language) if row else ("", default_language(spec["format"]))


def _session_dto(session, payload):
    return {
        "id": session.id, "exercise_id": session.exercise_id, "exercise_version": session.exercise_version,
        "exercise_title": payload["title"], "concept_id": payload["content"]["concept_id"],
        "interaction_style": session.interaction_style, "status": session.status,
        "created_at": _iso(session.created_at), "updated_at": _iso(session.updated_at),
    }


def _published_exercise(exercise_id, concept_id=None):
    if not isinstance(exercise_id, str) or not IDENTIFIER.fullmatch(exercise_id) or len(exercise_id) > 128:
        raise NotFoundError("exercise not found")
    row = db.session.scalar(select(ContentRevision).join(CurriculumItem).where(
        ContentRevision.item_id == exercise_id, CurriculumItem.kind == "exercise",
        ContentRevision.published_at.is_not(None),
    ).order_by(ContentRevision.version.desc()).limit(1))
    if row is None or (concept_id is not None and row.payload["content"]["concept_id"] != concept_id):
        raise NotFoundError("exercise not found")
    return row


def start_session(user, *, exercise_id, request_id, concept_id=None, now=None):
    """Pin the latest published exercise revision and record the interviewer's opening turn."""
    validate_request_id(request_id)
    digest = _digest("start", None, {"exercise_id": exercise_id, "concept_id": concept_id})
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, "start", digest)
        if replay is not None:
            db.session.commit()
            return replay
        exercise = _published_exercise(exercise_id, concept_id)
        opening = opening_view(exercise.payload)
        if opening["interaction_style"] != "interviewer":
            raise PracticeValidationError("Only interviewer exercises are available.")
        session = PracticeSession(id=str(uuid4()), user_id=user.id, exercise_id=exercise.item_id,
                                  exercise_version=exercise.version, interaction_style=opening["interaction_style"],
                                  status="active", created_at=now, updated_at=now)
        db.session.add(session)
        db.session.flush()
        db.session.add(SessionMessage(practice_session_id=session.id, sequence=1, role="interviewer", kind="turn",
                                      modality="text", body=opening["opening_prompt"], created_at=now))
        response = {"session_id": session.id, "exercise_id": exercise.item_id,
                    "exercise_version": exercise.version}
        _record(user.id, request_id, session.id, "start", digest, response, now)
        db.session.commit()
        return response
    except Exception:
        db.session.rollback()
        raise


def _normalize_edits(edits):
    if not isinstance(edits, list) or not 1 <= len(edits) <= MAX_EDITS:
        raise PracticeValidationError(f"Send between 1 and {MAX_EDITS} artifact edits.")
    normalized, seen = [], set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != EDIT_FIELDS:
            raise PracticeValidationError("Each edit needs artifact_id, base_revision, language, and body.")
        artifact_id = edit["artifact_id"]
        if (not isinstance(artifact_id, str) or len(artifact_id) > 128 or not IDENTIFIER.fullmatch(artifact_id)
                or artifact_id in seen):
            raise PracticeValidationError("Each artifact can be edited once per save.")
        seen.add(artifact_id)
        base = edit["base_revision"]
        if type(base) is not int or not 0 <= base <= MAX_INT:
            raise PracticeValidationError("The base revision must be a whole number.", field=artifact_id)
        if edit["language"] not in ARTIFACT_LANGUAGES:
            raise PracticeValidationError("Choose a supported notation.", field=artifact_id)
        body = normalize_text(edit["body"], field=artifact_id, limit=ARTIFACT_MAX_BYTES)
        normalized.append({"artifact_id": artifact_id, "base_revision": base,
                           "language": edit["language"], "body": body})
    return sorted(normalized, key=lambda entry: entry["artifact_id"])


def _apply_edits(session, specs, edits, now):
    """Decide every edit before writing any, so a conflict saves nothing.

    For head H and the base B the learner was shown:
    - submitted equals H: unchanged, no new row;
    - B is H: write H + 1;
    - submitted equals B: untouched in this view, keep the newer H;
    - otherwise: conflict.
    """
    outcomes, writes, conflicts = {}, [], []
    for edit in edits:
        spec = specs.get(edit["artifact_id"])
        if spec is None:
            raise PracticeValidationError("This exercise has no such artifact.", field=edit["artifact_id"])
        if edit["language"] not in FORMAT_LANGUAGES[spec["format"]]:
            raise PracticeValidationError(f"{spec['title']} can't be written as {edit['language']}.", field=spec["id"])
        head = _head(session.id, spec["id"])
        head_number = head.revision if head else 0
        submitted = (edit["body"], edit["language"])
        if submitted == _state(head, spec):
            outcomes[spec["id"]] = {"revision": head_number, "changed": False}
        elif edit["base_revision"] == head_number:
            writes.append(ArtifactRevision(
                practice_session_id=session.id, artifact_id=spec["id"], revision=head_number + 1,
                title=spec["title"], format=spec["format"], language=edit["language"], body=edit["body"],
                body_sha256=_sha256(edit["body"]), created_at=now))
            outcomes[spec["id"]] = {"revision": head_number + 1, "changed": True}
        elif edit["base_revision"] > head_number:
            raise PracticeValidationError("That artifact revision doesn't exist.", field=spec["id"])
        elif submitted == _state(_revision(session.id, spec["id"], edit["base_revision"]), spec):
            outcomes[spec["id"]] = {"revision": head_number, "changed": False}
        else:
            conflicts.append({"artifact_id": spec["id"], "base_revision": edit["base_revision"],
                              "revision": head_number, "language": head.language, "body": head.body})
    if conflicts:
        raise StaleArtifactError(conflicts)
    db.session.add_all(writes)
    db.session.flush()
    return outcomes


def save_artifacts(user, session_id, *, edits, request_id, now=None):
    """All-or-nothing artifact save. Unchanged content creates no revision."""
    validate_request_id(request_id)
    _check_session_id(session_id)
    normalized = _normalize_edits(edits)
    digest = _digest("save", session_id, normalized)
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, "save", digest)
        if replay is not None:
            db.session.commit()
            return replay
        session = _owned_session(user.id, session_id)
        outcomes = _apply_edits(session, _artifact_specs(_pinned_exercise(session).payload), normalized, now)
        if any(outcome["changed"] for outcome in outcomes.values()):
            session.updated_at = now
        response = {"session_id": session.id, "artifacts": outcomes}
        _record(user.id, request_id, session.id, "save", digest, response, now)
        db.session.commit()
        return response
    except Exception:
        db.session.rollback()
        raise


def _turns(session_id):
    citations = {}
    for message_id, artifact_id, revision in db.session.execute(
            select(SessionMessageArtifact.message_id, ArtifactRevision.artifact_id, ArtifactRevision.revision)
            .join(ArtifactRevision, ArtifactRevision.id == SessionMessageArtifact.artifact_revision_id)
            .where(SessionMessageArtifact.practice_session_id == session_id)
            .order_by(ArtifactRevision.artifact_id)):
        citations.setdefault(message_id, []).append({"artifact_id": artifact_id, "revision": revision})
    messages = db.session.scalars(select(SessionMessage).where(
        SessionMessage.practice_session_id == session_id, SessionMessage.kind == "turn"
    ).order_by(SessionMessage.sequence))
    return [{"sequence": message.sequence, "role": message.role, "kind": message.kind, "body": message.body,
             "created_at": _iso(message.created_at), "artifact_revisions": citations.get(message.id, [])}
            for message in messages]


def session_detail(user_id, session_id):
    """The learner-safe view of a session: brief, current artifacts, and transcript."""
    session = _owned_session(user_id, session_id)
    payload = _pinned_exercise(session).payload
    brief = learner_view(payload)["content"]["brief"]
    artifacts = []
    for spec in brief["expected_artifacts"]:
        head = _head(session.id, spec["id"])
        body, language = _state(head, spec)
        artifacts.append({
            "artifact_id": spec["id"], "title": spec["title"], "format": spec["format"],
            "instructions": spec["instructions"], "languages": list(FORMAT_LANGUAGES[spec["format"]]),
            "revision": head.revision if head else 0, "language": language, "body": body,
            "saved_at": _iso(head.created_at) if head else None,
        })
    return {"session": _session_dto(session, payload), "brief": brief, "artifacts": artifacts,
            "messages": _turns(session.id)}


def list_sessions(user_id, *, exercise_ids=None, statuses=OPEN_STATUSES, limit=LISTED_SESSIONS):
    query = select(PracticeSession, ContentRevision.payload).join(ContentRevision, and_(
        ContentRevision.item_id == PracticeSession.exercise_id,
        ContentRevision.version == PracticeSession.exercise_version,
    )).where(PracticeSession.user_id == user_id)
    if exercise_ids is not None:
        query = query.where(PracticeSession.exercise_id.in_(exercise_ids))
    if statuses is not None:
        query = query.where(PracticeSession.status.in_(statuses))
    rows = db.session.execute(query.order_by(PracticeSession.updated_at.desc()).limit(limit))
    return [_session_dto(session, payload) for session, payload in rows]


def concept_exercises(concept, *, user_id):
    """A concept's published exercises, each with this learner's sessions, newest first."""
    result = []
    for exercise_id in concept["content"]["exercise_ids"]:
        item = curriculum_service.published_learner_item(exercise_id)
        if item is None or item["kind"] != "exercise" or item["content"]["concept_id"] != concept["id"]:
            continue
        result.append({"id": item["id"], "title": item["title"],
                       "scenario": item["content"]["brief"]["scenario"],
                       "sessions": list_sessions(user_id, exercise_ids=[exercise_id], statuses=None, limit=5)})
    return result


def _owned_artifact(user_id, session_id, artifact_id):
    session = _owned_session(user_id, session_id)
    payload = _pinned_exercise(session).payload
    spec = _artifact_specs(payload).get(artifact_id)
    if spec is None:
        raise NotFoundError("artifact not found")
    return session, payload, spec


def artifact_history(user_id, session_id, artifact_id):
    session, payload, spec = _owned_artifact(user_id, session_id, artifact_id)
    rows = db.session.scalars(select(ArtifactRevision).where(
        ArtifactRevision.practice_session_id == session.id, ArtifactRevision.artifact_id == spec["id"]
    ).order_by(ArtifactRevision.revision.desc()))
    return {"session": _session_dto(session, payload),
            "artifact": {"artifact_id": spec["id"], "title": spec["title"], "format": spec["format"]},
            "revisions": [{"revision": row.revision, "language": row.language,
                           "bytes": len(row.body.encode("utf-8")), "created_at": _iso(row.created_at)}
                          for row in rows]}


def artifact_revision(user_id, session_id, artifact_id, revision):
    session, payload, spec = _owned_artifact(user_id, session_id, artifact_id)
    if type(revision) is not int or not 1 <= revision <= MAX_INT:
        raise NotFoundError("revision not found")
    row = _revision(session.id, spec["id"], revision)
    if row is None:
        raise NotFoundError("revision not found")
    return {"session": _session_dto(session, payload),
            "artifact": {"artifact_id": spec["id"], "title": spec["title"], "format": spec["format"]},
            "revision": {"revision": row.revision, "language": row.language, "body": row.body,
                         "bytes": len(row.body.encode("utf-8")), "created_at": _iso(row.created_at)},
            "current_revision": _head(session.id, spec["id"]).revision}


def practice_receipt(user_id, request_id):
    """Recover the result of a mutation whose response was lost."""
    validate_request_id(request_id)
    receipt = db.session.get(PracticeReceipt, (user_id, request_id))
    return {"operation": receipt.operation, "response": receipt.response} if receipt else None
