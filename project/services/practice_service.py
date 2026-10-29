"""Practice sessions: a pinned exercise, an ordered record, and immutable artifact revisions.

Every mutation follows one order: validate input, take the owner's user-row lock, check
the request receipt, read owner-scoped rows fresh, write, record the receipt, commit.
Deletion takes the same lock, and so does the AI worker when it writes a reply; its claim,
sweep, and next-call check rely on row locks instead (see "AI replies" below).

The ordered record holds conversation turns and snapshots of the learner's brief
(kind='brief'). A learner turn cites the exact artifact revisions it was sent with.
Learner text never goes into receipts (they store a payload hash) or log messages.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy import and_, func, select, text, update

from project.curriculum_terms import (
    ARTIFACT_LANGUAGES, BRIEF_ENTRY_TYPES, BRIEF_MAX_ENTRIES, CURRENT_PROFILES, FORMAT_LANGUAGES,
    MAX_EXPECTED_ARTIFACTS,
)
from project.database import db
from project.learning import interviewer
from project.learning.content_schema import interviewer_view, learner_view, opening_view, selector_view
from project.models import (
    AIRequest, ArtifactRevision, ContentRevision, CurriculumItem, PracticeReceipt, PracticeSession,
    SessionMessage, SessionMessageArtifact, User,
)
from project.services import curriculum_service, learning_service, practice_budget, practice_signals
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError


def validate_request_id(value):
    # learning_service may still be loading when this module is imported; look it up at call time.
    return learning_service.validate_request_id(value)

ARTIFACT_MAX_BYTES = 64 * 1024
TURN_MAX_BYTES = 8 * 1024
BRIEF_ENTRY_MAX_BYTES = 2 * 1024
MAX_EDITS = MAX_EXPECTED_ARTIFACTS
MAX_SOURCES = 10
MAX_INT = 2_147_483_647
LISTED_SESSIONS = 20
OPEN_STATUSES = ("active", "paused")
EDIT_FIELDS = {"artifact_id", "base_revision", "language", "body"}
BRIEF_FIELDS = {"base_revision", "entries"}
ENTRY_REQUIRED = {"id", "type", "text", "pinned"}
ENTRY_FIELDS = ENTRY_REQUIRED | {"basis", "sources"}
# Learner entries only. Disclosed scenario facts and model interpretations arrive with the interviewer.
ENTRY_BASES = ("learner",)
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*(?::[a-z0-9-]+)?")
ENTRY_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class PracticeValidationError(ValidationError):
    """Input the learner can correct.

    `part` says what it concerns: "artifact", "brief", or "turn". `field` names the
    artifact or brief entry, if any.
    """

    def __init__(self, message, *, field=None, part=None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.part = part or ("artifact" if field else None)


class RequestConflictError(ConflictError):
    """The request ID was already used for a different change."""

    code = "request_conflict"


class StaleViewError(ConflictError):
    """The request came from a view of the session that is now out of date. Nothing was saved."""

    def __init__(self, *, conflicts=(), refresh=(), brief_conflict=None, brief_refresh=None, latest_turn=None):
        super().__init__("This view of the session is out of date.")
        # Artifacts whose submitted text, or cited revision, is behind newer saved work:
        # artifact_id, base_revision, and the current revision, language, and body.
        self.conflicts = list(conflicts)
        # Artifacts this view left untouched that changed elsewhere, with their current text.
        self.refresh = list(refresh)
        # The current brief, when the submitted (or cited) brief is behind it.
        self.brief_conflict = brief_conflict
        # The current brief, when this view's untouched brief changed elsewhere.
        self.brief_refresh = brief_refresh
        # The latest turn's sequence, when turns arrived after this view loaded.
        self.latest_turn = latest_turn

    @property
    def code(self):
        if self.conflicts:
            return "stale_artifact"
        if self.brief_conflict is not None:
            return "stale_brief"
        if self.latest_turn is not None:
            return "stale_transcript"
        return "out_of_date"

    def details(self):
        """The parts a client needs to look at again, keyed as in the JSON API."""
        details = {}
        if self.conflicts:
            details["conflicts"] = self.conflicts
        if self.brief_conflict is not None:
            details["brief"] = self.brief_conflict
        if self.latest_turn is not None:
            details["latest_sequence"] = self.latest_turn
        return details


def enabled():
    return bool(current_app.config.get("LEARNING_PRACTICE_ENABLED"))


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


def normalize_text(value, *, field=None, part=None, limit, label="This text"):
    """Store one canonical form: LF line endings, valid UTF-8, no NUL, within the byte limit."""
    if not isinstance(value, str):
        raise PracticeValidationError(f"{label} is missing.", field=field, part=part)
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text:
        raise PracticeValidationError(f"{label} contains a NUL character, which can't be saved.",
                                      field=field, part=part)
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        raise PracticeValidationError(f"{label} contains an invalid character.", field=field, part=part) from None
    if size > limit:
        raise PracticeValidationError(
            f"{label} is {size / 1024:.1f} KiB; the limit is {limit // 1024} KiB.", field=field, part=part)
    return text


def _whole_number(value, *, minimum=0):
    return type(value) is int and minimum <= value <= MAX_INT


def _check_session_id(session_id):
    """Malformed IDs are simply not found, like another account's sessions."""
    try:
        if not isinstance(session_id, str) or str(UUID(session_id)) != session_id:
            raise ValueError
    except ValueError:
        raise NotFoundError("practice session not found") from None


def _lock_owner(user_id):
    """Serialize this owner's practice writes. The user row exists before any practice row.

    FOR NO KEY UPDATE rather than FOR UPDATE: inserting a row that references the user takes
    FOR KEY SHARE on it, and the reply worker inserts ledger charges without this lock while
    holding a request row. FOR UPDATE would make the worker wait on an owner waiting on it.
    """
    if db.session.get_bind().dialect.name == "sqlite":
        # SELECT ... FOR UPDATE is a no-op on SQLite; a write takes its database lock.
        db.session.execute(update(User).where(User.id == user_id).values(id=User.id))
    else:
        db.session.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True)).scalar_one()


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


def _set_status(session, status):
    """Move between active and paused. Returns whether anything changed."""
    if session.status == status:
        return False
    if session.status not in OPEN_STATUSES:
        raise PracticeValidationError("A completed session can't be paused or resumed.")
    session.status = status
    return True


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


def _next_sequence(session_id):
    latest = db.session.scalar(select(func.max(SessionMessage.sequence)).where(
        SessionMessage.practice_session_id == session_id))
    return (latest or 0) + 1


def _latest_turn(session_id):
    """The sequence a turn must expect. Brief snapshots and other records don't count."""
    latest = db.session.scalar(select(func.max(SessionMessage.sequence)).where(
        SessionMessage.practice_session_id == session_id, SessionMessage.kind == "turn"))
    return latest or 0


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
                                  profile_version=CURRENT_PROFILES[opening["interaction_style"]],
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


# Input normalization. Everything is checked before the lock is taken.

def _normalize_edits(edits, *, minimum=1):
    if not isinstance(edits, list) or not minimum <= len(edits) <= MAX_EDITS:
        raise PracticeValidationError(f"Send between 1 and {MAX_EDITS} artifact edits." if minimum
                                      else f"Send at most {MAX_EDITS} artifact edits.")
    normalized, seen = [], set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != EDIT_FIELDS:
            raise PracticeValidationError("Each edit needs artifact_id, base_revision, language, and body.")
        artifact_id = edit["artifact_id"]
        if (not isinstance(artifact_id, str) or len(artifact_id) > 128 or not IDENTIFIER.fullmatch(artifact_id)
                or artifact_id in seen):
            raise PracticeValidationError("Each artifact can be edited once per save.")
        seen.add(artifact_id)
        if not _whole_number(edit["base_revision"]):
            raise PracticeValidationError("The base revision must be a whole number.", field=artifact_id)
        if edit["language"] not in ARTIFACT_LANGUAGES:
            raise PracticeValidationError("Choose a supported notation.", field=artifact_id)
        body = normalize_text(edit["body"], field=artifact_id, limit=ARTIFACT_MAX_BYTES)
        normalized.append({"artifact_id": artifact_id, "base_revision": edit["base_revision"],
                           "language": edit["language"], "body": body})
    return sorted(normalized, key=lambda entry: entry["artifact_id"])


def _normalize_sources(sources, entry_id):
    """A source is a turn ({"turn": 3}) or an artifact revision ({"artifact_id": "api", "revision": 2})."""
    if not isinstance(sources, list) or len(sources) > MAX_SOURCES:
        raise PracticeValidationError(f"An entry can cite up to {MAX_SOURCES} sources.", field=entry_id, part="brief")
    normalized = []
    for source in sources:
        if isinstance(source, dict) and set(source) == {"turn"} and _whole_number(source["turn"], minimum=1):
            value = {"turn": source["turn"]}
        elif (isinstance(source, dict) and set(source) == {"artifact_id", "revision"}
              and isinstance(source["artifact_id"], str) and len(source["artifact_id"]) <= 128
              and IDENTIFIER.fullmatch(source["artifact_id"]) and _whole_number(source["revision"], minimum=1)):
            value = {"artifact_id": source["artifact_id"], "revision": source["revision"]}
        else:
            raise PracticeValidationError("A source must be a turn or an artifact revision.", field=entry_id,
                                          part="brief")
        if value in normalized:
            raise PracticeValidationError("An entry cites the same source twice.", field=entry_id, part="brief")
        normalized.append(value)
    return normalized


def _normalize_brief(brief):
    if not isinstance(brief, dict) or set(brief) != BRIEF_FIELDS:
        raise PracticeValidationError("The brief needs base_revision and entries.", part="brief")
    if not _whole_number(brief["base_revision"]):
        raise PracticeValidationError("The brief's base revision must be a whole number.", part="brief")
    entries = brief["entries"]
    if not isinstance(entries, list):
        raise PracticeValidationError("The brief's entries must be a list.", part="brief")
    if len(entries) > BRIEF_MAX_ENTRIES:
        raise PracticeValidationError(
            f"The brief holds up to {BRIEF_MAX_ENTRIES} entries; this has {len(entries)}.", part="brief")
    normalized, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or not ENTRY_REQUIRED <= set(entry) <= ENTRY_FIELDS:
            raise PracticeValidationError("Each brief entry needs id, type, text, and pinned.", part="brief")
        entry_id = entry["id"]
        if not isinstance(entry_id, str) or not ENTRY_ID.fullmatch(entry_id) or entry_id in seen:
            raise PracticeValidationError("Each brief entry needs its own short lowercase ID.", part="brief")
        seen.add(entry_id)
        if not isinstance(entry["type"], str) or entry["type"] not in BRIEF_ENTRY_TYPES:
            raise PracticeValidationError("Choose assumption, question, decision, or next step.", field=entry_id,
                                          part="brief")
        if entry.get("basis", "learner") not in ENTRY_BASES:
            raise PracticeValidationError("Entries you write have the basis \"learner\".", field=entry_id,
                                          part="brief")
        text = normalize_text(entry["text"], field=entry_id, part="brief", limit=BRIEF_ENTRY_MAX_BYTES,
                              label="This brief entry").strip()
        if not text:
            raise PracticeValidationError("A brief entry needs text.", field=entry_id, part="brief")
        if type(entry["pinned"]) is not bool:
            raise PracticeValidationError("pinned must be true or false.", field=entry_id, part="brief")
        normalized.append({"id": entry_id, "type": entry["type"], "basis": "learner", "text": text,
                           "pinned": entry["pinned"], "sources": _normalize_sources(entry.get("sources", []), entry_id)})
    return {"base_revision": brief["base_revision"], "entries": normalized}


def _normalize_turn(body):
    text = normalize_text(body, part="turn", limit=TURN_MAX_BYTES, label="Your message").strip()
    if not text:
        raise PracticeValidationError("Write a message before sending.", part="turn")
    return text


def same_text(body, saved_body):
    """Whether submitted artifact text equals saved text once normalized as a save would."""
    try:
        return normalize_text(body, limit=ARTIFACT_MAX_BYTES) == saved_body
    except PracticeValidationError:
        return False


def same_brief(entries, saved_entries):
    """Whether submitted brief entries equal saved ones once normalized as a save would."""
    try:
        return _normalize_brief({"base_revision": 0, "entries": entries})["entries"] == saved_entries
    except PracticeValidationError:
        return False


def _check_expected_sequence(value):
    if not _whole_number(value):
        raise PracticeValidationError("expected_sequence must be a whole number.", part="turn")


def _normalize_citations(revisions):
    if not isinstance(revisions, dict) or not 1 <= len(revisions) <= MAX_EDITS:
        raise PracticeValidationError("artifact_revisions maps each artifact ID to the revision you are looking at.",
                                      part="turn")
    for artifact_id, revision in revisions.items():
        if not isinstance(artifact_id, str) or len(artifact_id) > 128 or not IDENTIFIER.fullmatch(artifact_id):
            raise PracticeValidationError("artifact_revisions has an invalid artifact ID.", part="turn")
        if not _whole_number(revision):
            raise PracticeValidationError("Each cited revision must be a whole number.", field=artifact_id)
    return dict(sorted(revisions.items()))


# Decisions. Each decides everything before anything is written, so a refusal saves nothing.

def _decide_edits(session, specs, edits, now):
    """For head H and the base B the learner was shown:

    - submitted equals H: unchanged, no new row;
    - B is H: write H + 1;
    - submitted equals B: untouched in this view, keep the newer H ("refresh");
    - otherwise: conflict.

    Returns (outcomes, rows to write, conflicts, refresh).
    """
    outcomes, writes, conflicts, refresh = {}, [], [], []
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
            refresh.append({"artifact_id": spec["id"], "revision": head_number,
                            "language": head.language, "body": head.body})
        else:
            conflicts.append({"artifact_id": spec["id"], "base_revision": edit["base_revision"],
                              "revision": head_number, "language": head.language, "body": head.body})
    return outcomes, writes, conflicts, refresh


def _brief_record(session_id, revision=None):
    """The latest brief snapshot, or the one with the given revision number."""
    query = select(SessionMessage).where(SessionMessage.practice_session_id == session_id,
                                         SessionMessage.kind == "brief")
    if revision is None:
        query = query.order_by(SessionMessage.sequence.desc()).limit(1)
    else:
        query = query.where(SessionMessage.data["revision"].as_integer() == revision)
    return db.session.execute(query.execution_options(populate_existing=True)).scalar_one_or_none()


def _entry_dto(entry):
    return {"id": entry["id"], "type": entry["type"], "basis": entry["basis"], "text": entry["text"],
            "pinned": entry["pinned"],
            "sources": [{"turn": source["turn"]} if "turn" in source
                        else {"artifact_id": source["artifact_id"], "revision": source["revision"]}
                        for source in entry["sources"]]}


def _brief_dto(record):
    if record is None:
        return {"revision": 0, "entries": [], "saved_at": None}
    return {"revision": record.data["revision"], "entries": [_entry_dto(entry) for entry in record.data["entries"]],
            "saved_at": _iso(record.created_at)}


def _check_sources(session_id, entries):
    turns = {source["turn"] for entry in entries for source in entry["sources"] if "turn" in source}
    cited = {(source["artifact_id"], source["revision"])
             for entry in entries for source in entry["sources"] if "artifact_id" in source}
    known_turns = set(db.session.scalars(select(SessionMessage.sequence).where(
        SessionMessage.practice_session_id == session_id, SessionMessage.kind == "turn",
        SessionMessage.sequence.in_(turns)))) if turns else set()
    known_revisions = set(db.session.execute(select(ArtifactRevision.artifact_id, ArtifactRevision.revision).where(
        ArtifactRevision.practice_session_id == session_id,
        ArtifactRevision.artifact_id.in_({artifact_id for artifact_id, _ in cited})))) if cited else set()
    for entry in entries:
        for source in entry["sources"]:
            found = (source["turn"] in known_turns if "turn" in source
                     else (source["artifact_id"], source["revision"]) in known_revisions)
            if not found:
                raise PracticeValidationError("A brief entry cites a turn or revision that doesn't exist.",
                                              field=entry["id"], part="brief")


def _decide_brief(session, brief):
    """The artifact rule, applied to the whole brief snapshot.

    Returns (outcome, entries to write or None, conflict, refresh); conflict and refresh
    are the current brief when they apply.
    """
    head = _brief_record(session.id)
    head_number = head.data["revision"] if head else 0
    submitted, base = brief["entries"], brief["base_revision"]
    if submitted == (head.data["entries"] if head else []):
        return {"revision": head_number, "changed": False}, None, None, None
    if base == head_number:
        _check_sources(session.id, submitted)
        return {"revision": head_number + 1, "changed": True}, submitted, None, None
    if base > head_number:
        raise PracticeValidationError("That brief revision doesn't exist.", part="brief")
    base_record = _brief_record(session.id, base) if base else None
    if submitted == (base_record.data["entries"] if base_record else []):
        return {"revision": head_number, "changed": False}, None, None, _brief_dto(head)
    return None, None, _brief_dto(head), None


def _write(session, artifact_rows, brief_outcome, brief_entries, now):
    """Write decided artifact revisions and brief snapshot. Returns whether anything was written."""
    db.session.add_all(artifact_rows)
    db.session.flush()
    if brief_entries is not None:
        db.session.add(SessionMessage(
            practice_session_id=session.id, sequence=_next_sequence(session.id), role="learner", kind="brief",
            modality="text", body="", data={"revision": brief_outcome["revision"], "entries": brief_entries},
            created_at=now))
        db.session.flush()
    return bool(artifact_rows) or brief_entries is not None


def _append_turn(session, specs, text, brief_revision, now):
    """Append a learner turn citing every artifact's current revision."""
    turn = SessionMessage(practice_session_id=session.id, sequence=_next_sequence(session.id), role="learner",
                          kind="turn", modality="text", body=text, data={"brief_revision": brief_revision},
                          created_at=now)
    db.session.add(turn)
    db.session.flush()
    cited = []
    for artifact_id in sorted(specs):
        head = _head(session.id, artifact_id)
        if head is not None:
            db.session.add(SessionMessageArtifact(message_id=turn.id, artifact_revision_id=head.id,
                                                  practice_session_id=session.id))
            cited.append({"artifact_id": artifact_id, "revision": head.revision})
    db.session.flush()
    return turn, cited


# Mutations.

def save_work(user, session_id, *, edits=None, brief=None, request_id, status="active", now=None):
    """All-or-nothing save of artifact edits and/or the brief. Unchanged content writes nothing.

    Saving resumes a paused session. status="paused" saves and then pauses.
    """
    validate_request_id(request_id)
    _check_session_id(session_id)
    if status not in OPEN_STATUSES:
        raise PracticeValidationError("The status must be active or paused.")
    normalized = _normalize_edits([] if edits is None else edits, minimum=0 if brief is not None else 1)
    normalized_brief = _normalize_brief(brief) if brief is not None else None
    operation = "pause" if status == "paused" else "save"
    digest = _digest(operation, session_id, {"edits": normalized, "brief": normalized_brief})
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, operation, digest)
        if replay is not None:
            db.session.commit()
            return replay
        session = _owned_session(user.id, session_id)
        if status == "paused":
            _cancel_pending_reply(session, now)
        specs = _artifact_specs(_pinned_exercise(session).payload)
        outcomes, rows, conflicts, refresh = _decide_edits(session, specs, normalized, now)
        brief_outcome = brief_entries = brief_conflict = brief_refresh = None
        if normalized_brief is not None:
            brief_outcome, brief_entries, brief_conflict, brief_refresh = _decide_brief(session, normalized_brief)
        if conflicts or brief_conflict is not None:
            raise StaleViewError(conflicts=conflicts, refresh=refresh, brief_conflict=brief_conflict,
                                 brief_refresh=brief_refresh)
        changed = _write(session, rows, brief_outcome, brief_entries, now)
        if status == "paused" or session.status == "paused":
            changed = _set_status(session, status) or changed
        if changed:
            session.updated_at = now
        response = {"session_id": session.id}
        if normalized:
            response["artifacts"] = outcomes
        if normalized_brief is not None:
            response["brief"] = brief_outcome
        response["status"] = session.status
        _record(user.id, request_id, session.id, operation, digest, response, now)
        db.session.commit()
        return response
    except Exception:
        db.session.rollback()
        raise


def save_and_send(user, session_id, *, edits, brief, body, expected_sequence, request_id, now=None):
    """The website's Send: save every artifact and the brief, then append the turn, in one transaction.

    A turn needs an up-to-date view. Anything changed elsewhere since the page loaded,
    including an untouched artifact or brief, or a newer turn, refuses the whole request
    so the learner can look first.
    """
    validate_request_id(request_id)
    _check_session_id(session_id)
    normalized = _normalize_edits(edits)
    normalized_brief = _normalize_brief(brief)
    text = _normalize_turn(body)
    _check_expected_sequence(expected_sequence)
    digest = _digest("send", session_id, {"edits": normalized, "brief": normalized_brief, "body": text,
                                          "expected_sequence": expected_sequence})
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, "send", digest)
        if replay is not None:
            db.session.commit()
            return replay
        session = _owned_session(user.id, session_id)
        if _settle_stale_reply(session, now) is not None:
            raise ReplyPendingError("The interviewer is still replying.")
        specs = _artifact_specs(_pinned_exercise(session).payload)
        if {edit["artifact_id"] for edit in normalized} != set(specs):
            raise PracticeValidationError("Send every artifact with the message.", part="turn")
        outcomes, rows, conflicts, refresh = _decide_edits(session, specs, normalized, now)
        brief_outcome, brief_entries, brief_conflict, brief_refresh = _decide_brief(session, normalized_brief)
        latest = _latest_turn(session.id)
        if conflicts or refresh or brief_conflict is not None or brief_refresh is not None or latest != expected_sequence:
            raise StaleViewError(conflicts=conflicts, refresh=refresh, brief_conflict=brief_conflict,
                                 brief_refresh=brief_refresh, latest_turn=None if latest == expected_sequence else latest)
        _write(session, rows, brief_outcome, brief_entries, now)
        turn, cited = _append_turn(session, specs, text, brief_outcome["revision"], now)
        if session.status == "paused":
            _set_status(session, "active")
        session.updated_at = now
        reply = _queue_reply(session, turn, now)
        response = {"session_id": session.id, "sequence": turn.sequence, "artifact_revisions": cited,
                    "brief_revision": brief_outcome["revision"], "artifacts": outcomes, "brief": brief_outcome,
                    "status": session.status, "reply": reply, "latest_sequence": turn.sequence}
        _record(user.id, request_id, session.id, "send", digest, response, now)
        db.session.commit()
        _wake_worker(reply)
        return response
    except Exception:
        db.session.rollback()
        raise


def send_turn(user, session_id, *, body, expected_sequence, artifact_revisions, brief_revision, request_id, now=None):
    """Append a learner turn that cites saved work (the JSON API). Every citation must be current."""
    validate_request_id(request_id)
    _check_session_id(session_id)
    text = _normalize_turn(body)
    _check_expected_sequence(expected_sequence)
    cited_view = _normalize_citations(artifact_revisions)
    if not _whole_number(brief_revision):
        raise PracticeValidationError("brief_revision must be a whole number.", part="brief")
    digest = _digest("send", session_id, {"artifact_revisions": cited_view, "brief_revision": brief_revision,
                                          "body": text, "expected_sequence": expected_sequence})
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, "send", digest)
        if replay is not None:
            db.session.commit()
            return replay
        session = _owned_session(user.id, session_id)
        if _settle_stale_reply(session, now) is not None:
            raise ReplyPendingError("The interviewer is still replying.")
        specs = _artifact_specs(_pinned_exercise(session).payload)
        if set(cited_view) != set(specs):
            raise PracticeValidationError(f"Cite every artifact: {', '.join(sorted(specs))}.", part="turn")
        conflicts = []
        for artifact_id, revision in cited_view.items():
            head = _head(session.id, artifact_id)
            head_number = head.revision if head else 0
            if revision > head_number:
                raise PracticeValidationError("That artifact revision doesn't exist.", field=artifact_id)
            if revision < head_number:
                conflicts.append({"artifact_id": artifact_id, "base_revision": revision, "revision": head_number,
                                  "language": head.language, "body": head.body})
        brief_head = _brief_record(session.id)
        brief_number = brief_head.data["revision"] if brief_head else 0
        if brief_revision > brief_number:
            raise PracticeValidationError("That brief revision doesn't exist.", part="brief")
        latest = _latest_turn(session.id)
        if conflicts or brief_revision < brief_number or latest != expected_sequence:
            raise StaleViewError(conflicts=conflicts,
                                 brief_conflict=_brief_dto(brief_head) if brief_revision < brief_number else None,
                                 latest_turn=None if latest == expected_sequence else latest)
        turn, cited = _append_turn(session, specs, text, brief_number, now)
        if session.status == "paused":
            _set_status(session, "active")
        session.updated_at = now
        reply = _queue_reply(session, turn, now)
        response = {"session_id": session.id, "sequence": turn.sequence, "artifact_revisions": cited,
                    "brief_revision": brief_number, "status": session.status, "reply": reply,
                    "latest_sequence": turn.sequence}
        _record(user.id, request_id, session.id, "send", digest, response, now)
        db.session.commit()
        _wake_worker(reply)
        return response
    except Exception:
        db.session.rollback()
        raise


def set_status(user, session_id, *, status, request_id, now=None):
    """Pause or resume a session. Repeating either changes nothing."""
    validate_request_id(request_id)
    _check_session_id(session_id)
    if status not in OPEN_STATUSES:
        raise PracticeValidationError("The status must be active or paused.")
    operation = "pause" if status == "paused" else "resume"
    digest = _digest(operation, session_id, {"status": status})
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, operation, digest)
        if replay is not None:
            db.session.commit()
            return replay
        session = _owned_session(user.id, session_id)
        if status == "paused":
            _cancel_pending_reply(session, now)
        changed = _set_status(session, status)
        if changed:
            session.updated_at = now
        response = {"session_id": session.id, "status": session.status, "changed": changed}
        _record(user.id, request_id, session.id, operation, digest, response, now)
        db.session.commit()
        return response
    except Exception:
        db.session.rollback()
        raise


def delete_session(user, session_id):
    """Delete a session and, by database cascade, everything recorded in it.

    There is no receipt to replay: the session's receipts go with it, so repeating a
    delete reports not found.
    """
    _check_session_id(session_id)
    try:
        if (db.session.get_bind().dialect.name == "sqlite"
                and not db.session.execute(text("PRAGMA foreign_keys")).scalar()):
            # Without it SQLite skips the cascades and would keep every row of a "deleted" session.
            raise RuntimeError("Deleting a practice session needs SQLite foreign keys on (PRAGMA foreign_keys=ON).")
        _lock_owner(user.id)
        session = _owned_session(user.id, session_id)
        concept_id = _pinned_exercise(session).payload["content"]["concept_id"]
        # The live reply's row before the session's, in the lock order every writer uses: a
        # worker about to make a paid call holds that row, then needs the session's.
        _live_request(session.id)
        db.session.delete(session)
        db.session.commit()
        return {"session_id": session_id, "concept_id": concept_id}
    except Exception:
        db.session.rollback()
        raise


# AI replies. A reply is an AIRequest row: queued with the learner's turn, claimed by the
# worker, fenced before every paid call, and written under the owner lock. Lock order
# everywhere: owner, request, session, budget, charge. The worker's claim, sweep, and
# next-call check never take the owner lock; owner-side writes lock the live request row
# before they change the session row, so the two sides take turns instead of deadlocking.

PROVIDERS = ("fake", "openai")
LIVE = ("pending", "running")
# Any reply the schema allows fits: at most REPLY_MAX_CHARS characters of up to four UTF-8 bytes.
REPLY_MAX_BYTES = 4 * interviewer.REPLY_MAX_CHARS


class ReplyPendingError(ConflictError):
    """The interviewer is still replying; another turn now would race that reply."""

    code = "reply_pending"


class CallFenced(Exception):
    """The reply is no longer wanted (cancelled, paused, deleted, or reclaimed). Make no paid call."""


def ai_settings():
    config = current_app.config
    provider = config.get("LEARNING_AI_PROVIDER", "openai")
    model = config.get("LEARNING_AI_MODEL") or ("fake-interviewer" if provider == "fake" else None)
    return {
        "enabled": bool(config.get("LEARNING_AI_ENABLED")), "provider": provider, "model": model,
        "selector_model": config.get("LEARNING_AI_SELECTOR_MODEL") or model,
        "tier": config.get("LEARNING_AI_SERVICE_TIER", "default"),
        "start_seconds": int(config.get("LEARNING_AI_START_SECONDS", 120)),
        "call_seconds": int(config.get("LEARNING_AI_CALL_SECONDS", 60)),
        "lease_margin_seconds": int(config.get("LEARNING_AI_LEASE_MARGIN_SECONDS", 30)),
        "max_output_tokens": int(config.get("LEARNING_AI_MAX_OUTPUT_TOKENS", 1200)),
        "selector_max_output_tokens": int(config.get("LEARNING_AI_SELECTOR_MAX_OUTPUT_TOKENS", 200)),
        "reasoning_effort": config.get("LEARNING_AI_REASONING_EFFORT") or None,
        # What the model may read per reply, in UTF-8 bytes (a token is at least one byte). The
        # default fits the bounded essential context; activation sizes it to the chosen model.
        "context_bytes": int(config.get("LEARNING_AI_CONTEXT_BYTES", 524_288)),
        "check_in_turns": int(config.get("LEARNING_AI_CHECK_IN_TURNS", 24)),
        "base_url": config.get("LEARNING_AI_BASE_URL", "https://api.openai.com/v1"),
    }


def provider_ready(settings):
    """Whether this release can call the configured provider: the fake always; OpenAI with its key."""
    if settings["provider"] == "fake":
        return True
    return settings["provider"] == "openai" and bool(os.environ.get("LEARNING_OPENAI_API_KEY"))


def ai_owner_id():
    """The one verified account named by LEARNING_AI_OWNER_EMAIL, or None, which turns AI off."""
    email = current_app.config.get("LEARNING_AI_OWNER_EMAIL")
    if not isinstance(email, str) or not email.strip():
        return None
    ids = db.session.scalars(select(User.id).where(
        func.lower(User.email) == email.strip().lower(), User.email_verified.is_(True)).limit(2)).all()
    return ids[0] if len(ids) == 1 else None


def reply_unavailable(user_id, now):
    """Why the interviewer can't reply for this learner now, or None when it can."""
    settings = ai_settings()
    if (not settings["enabled"] or settings["provider"] not in PROVIDERS or not provider_ready(settings)
            or not settings["model"]
            or not practice_budget.priced(settings["provider"], settings["model"], settings["tier"])
            or not practice_budget.priced(settings["provider"], settings["selector_model"], settings["tier"])):
        return "disabled"
    if ai_owner_id() != user_id:
        return "owner_only"
    if _month(now)["exhausted"]:
        return "budget"
    return None


def _month(now):
    """This month's spending. It reads as exhausted once not even the smallest reply would fit."""
    settings = ai_settings()
    smallest = practice_budget.worst_case(settings["provider"], settings["model"], settings["tier"],
                                          input_bytes=0, max_output_tokens=settings["max_output_tokens"])
    return practice_budget.month_status(now, smallest_microusd=smallest or 0)


def ai_budget(user_id, now):
    """The month's spending, shown only to the owner."""
    return _month(now) if ai_owner_id() == user_id else None


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _effective(request, now, unavailable):
    """How a reply reads now. A stale live request reads as interrupted, so nothing waits on it forever."""
    settings = ai_settings()
    if request.status == "pending":
        if unavailable:
            return "interrupted", unavailable
        if _aware(request.created_at) + timedelta(seconds=settings["start_seconds"]) < now:
            return "interrupted", "not_started"
    if request.status == "running" and request.lease_expires_at is not None and _aware(request.lease_expires_at) < now:
        return "interrupted", "lease_expired"
    return request.status, request.error_code


def _live_request(session_id):
    """Under the owner lock: the session's pending or running request, locked.

    The lock makes this wait for a worker inside its next-call check, then read the lease that
    check extended, so a reply about to make a paid call is never also marked interrupted.
    """
    return db.session.execute(select(AIRequest).where(
        AIRequest.practice_session_id == session_id, AIRequest.status.in_(LIVE)
    ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()


def _settle_stale_reply(session, now):
    """Under the owner lock: record a stale live request as interrupted. Returns any request still live."""
    request = _live_request(session.id)
    if request is None:
        return None
    status, code = _effective(request, now, reply_unavailable(session.user_id, now))
    if status != "interrupted":
        return request
    request.status, request.error_code, request.finished_at, request.lease_expires_at = status, code, now, None
    db.session.flush()
    return None


def _cancel_pending_reply(session, now):
    """Pausing stops generation that hasn't started. A running reply's next-call check stops the rest."""
    request = _settle_stale_reply(session, now)
    if request is not None and request.status == "pending":
        request.status, request.error_code, request.finished_at = "cancelled", "paused", now
        db.session.flush()


def _reply_dto(reply_id=None, status="unavailable", reason=None):
    return {"id": reply_id, "status": status, "reason": reason}


def _queue_reply(session, turn, now, *, context_from_sequence=None):
    """Queue the interviewer's reply to `turn` when AI may reply for this learner, the interviewer
    can read what the reply needs, and its worst case fits the budget. The reply reads from the
    learner's latest Continue with recent messages choice, if any."""
    unavailable = reply_unavailable(session.user_id, now)
    if unavailable:
        return _reply_dto(reason=unavailable)
    if context_from_sequence is None:
        context_from_sequence = _context_from(_records(session.id))
    obstacle, _ = _reply_obstacle(session, turn, now, context_from_sequence)
    if obstacle:
        return _reply_dto(reason=obstacle)
    settings = ai_settings()
    request = AIRequest(id=str(uuid4()), practice_session_id=session.id, turn_message_id=turn.id, kind="reply",
                        status="pending", profile_version=session.profile_version, provider=settings["provider"],
                        model=settings["model"], selector_model=settings["selector_model"],
                        context_from_sequence=context_from_sequence, created_at=now)
    db.session.add(request)
    db.session.flush()
    return _reply_dto(request.id, "pending")


def _wake_worker(reply):
    if reply.get("status") == "pending":
        practice_signals.reply_queued.set()


def _latest_learner_turn(session_id):
    return db.session.execute(select(SessionMessage).where(
        SessionMessage.practice_session_id == session_id, SessionMessage.kind == "turn",
        SessionMessage.role == "learner",
    ).order_by(SessionMessage.sequence.desc()).limit(1)).scalar_one_or_none()


def request_reply(user, session_id, *, request_id, edits=None, brief=None, context=None, now=None):
    """Ask for a reply to the latest learner turn: a retry, or a turn saved while AI was unavailable.

    The website also saves the page's artifacts and brief in the same transaction, so asking
    never discards typing. Only the latest learner turn qualifies. If a reply reached it
    meanwhile (seen from another tab, or arriving late), asking still saves, and the reply's
    status is "answered".

    context="recent" is Continue with recent messages: when the whole conversation no longer
    fits what the interviewer can read, record that replies read from the earliest message
    that fits, and ask. Nothing is deleted; later replies keep reading from there.
    """
    validate_request_id(request_id)
    _check_session_id(session_id)
    if context not in (None, "recent"):
        raise PracticeValidationError('context must be "recent" when given.', field="context", part="turn")
    normalized = _normalize_edits([] if edits is None else edits, minimum=0)
    normalized_brief = _normalize_brief(brief) if brief is not None else None
    payload = {"edits": normalized, "brief": normalized_brief}
    if context is not None:
        payload["context"] = context
    digest = _digest("reply", session_id, payload)
    now = now or _now()
    try:
        _lock_owner(user.id)
        replay = _replay(user.id, request_id, "reply", digest)
        if replay is not None:
            db.session.commit()
            return replay
        session = _owned_session(user.id, session_id)
        if _settle_stale_reply(session, now) is not None:
            raise ReplyPendingError("The interviewer is already replying.")
        changed = False
        response = {"session_id": session.id}
        if normalized or normalized_brief is not None:
            specs = _artifact_specs(_pinned_exercise(session).payload)
            outcomes, rows, conflicts, refresh = _decide_edits(session, specs, normalized, now)
            brief_outcome = brief_entries = brief_conflict = brief_refresh = None
            if normalized_brief is not None:
                brief_outcome, brief_entries, brief_conflict, brief_refresh = _decide_brief(session, normalized_brief)
            if conflicts or brief_conflict is not None:
                raise StaleViewError(conflicts=conflicts, refresh=refresh, brief_conflict=brief_conflict,
                                     brief_refresh=brief_refresh)
            changed = _write(session, rows, brief_outcome, brief_entries, now)
            if normalized:
                response["artifacts"] = outcomes
            if normalized_brief is not None:
                response["brief"] = brief_outcome
        turn = _latest_learner_turn(session.id)
        if turn is None:
            raise PracticeValidationError("Send a message first.", part="turn")
        if _latest_turn(session.id) != turn.sequence:
            reply = _reply_dto(status="answered")  # what was asked for has happened
        elif context == "recent":
            reply, choice = _continue_recent(session, turn, now)
            if choice is not None:
                response["context_from_sequence"] = choice
                changed = True
        else:
            reply = _queue_reply(session, turn, now)
        if session.status == "paused":
            changed = _set_status(session, "active") or changed
        if changed or reply["status"] == "pending":
            session.updated_at = now
        response.update(reply=reply, latest_sequence=turn.sequence, status=session.status)
        _record(user.id, request_id, session.id, "reply", digest, response, now)
        db.session.commit()
        _wake_worker(reply)
        return response
    except Exception:
        db.session.rollback()
        raise


def _continue_recent(session, turn, now):
    """Record a Continue with recent messages choice for `turn`, when it moves where replies read
    from, and queue the reply. Returns the reply and the new starting message (or None)."""
    unavailable = reply_unavailable(session.user_id, now)
    if unavailable:
        return _reply_dto(reason=unavailable), None  # nothing to read from, so no choice to record
    if session.profile_version not in interviewer.PROFILES:
        return _queue_reply(session, turn, now), None  # a release that knows the profile checks its size
    current = _context_from(_records(session.id))
    start = _recent_from(session, turn)
    if start is None:
        return _reply_dto(reason="essential_too_large"), None
    if start <= current:
        return _queue_reply(session, turn, now), None  # the conversation already fits from where it reads
    db.session.add(SessionMessage(practice_session_id=session.id, sequence=_next_sequence(session.id), role="learner",
                                  kind="context", modality="text", body="", data={"from_sequence": start},
                                  created_at=now))
    db.session.flush()
    return _queue_reply(session, turn, now, context_from_sequence=start), start


def reply_summary(session, now):
    """The latest learner turn's reply as the learner sees it, and what the learner can do next.

    Asking needs AI available for this learner, a conversation the interviewer can read at once
    (or **Continue with recent messages** when it can't), and room in this month's budget for
    the reply's worst case. `too_large_part` names what to shorten when even the essentials don't fit.
    """
    unavailable = reply_unavailable(session.user_id, now)
    turn = _latest_learner_turn(session.id)
    request = None
    if turn is not None:
        request = db.session.execute(select(AIRequest).where(AIRequest.turn_message_id == turn.id).order_by(
            AIRequest.created_at.desc()).limit(1).execution_options(populate_existing=True)).scalar_one_or_none()
    status, error = _effective(request, now, unavailable) if request is not None else ("none", None)
    answered = turn is not None and _latest_turn(session.id) != turn.sequence
    part = None
    if unavailable is None and turn is not None and not answered and status not in LIVE:
        unavailable, part = _reply_obstacle(session, turn, now, _context_from(_records(session.id)))
    return {"id": request.id if request is not None else None, "status": status, "error": error,
            "turn_sequence": turn.sequence if turn is not None else None, "answered": answered,
            "can_request": turn is not None and not answered and status not in LIVE and unavailable is None,
            "can_continue_recent": unavailable == "context_too_large",
            "unavailable": unavailable, "too_large_part": part}


def reply_updates(user_id, session_id, *, after, now=None):
    """What a polling page needs: the reply's state and every turn after `after`."""
    if not _whole_number(after):
        raise PracticeValidationError("after must be a whole number.")
    session = _owned_session(user_id, session_id)
    # The state first, as in session_detail; the latest sequence comes from the same read as
    # the turns, so a client that advances to it never skips a turn it wasn't sent.
    reply = reply_summary(session, now or _now())
    turns = _turns(session.id)
    return {"reply": reply, "turns": [turn for turn in turns if turn["sequence"] > after],
            "latest_sequence": turns[-1]["sequence"] if turns else 0,
            "revealed_requirements": _revealed_requirements(_pinned_exercise(session).payload, _records(session.id))}


def sweep_replies(now):
    """Record stale live requests as interrupted. Reads already treat them so; this keeps rows honest."""
    settings = ai_settings()
    try:
        started = db.session.execute(update(AIRequest).where(
            AIRequest.status == "pending", AIRequest.created_at < now - timedelta(seconds=settings["start_seconds"]),
        ).values(status="interrupted", error_code="not_started", finished_at=now).execution_options(
            synchronize_session=False))
        expired = db.session.execute(update(AIRequest).where(
            AIRequest.status == "running", AIRequest.lease_expires_at < now,
        ).values(status="interrupted", error_code="lease_expired", finished_at=now, lease_expires_at=None
                 ).execution_options(synchronize_session=False))
        db.session.commit()
        return started.rowcount + expired.rowcount
    except Exception:
        db.session.rollback()
        raise


def claim_reply(now, *, known_profiles, worker_id):
    """Claim the oldest pending reply by compare-and-swap. Returns (reply_id, claim_token) or None.

    Requests for an interviewer version this code doesn't know are left for code that does,
    which matters while an old and a new release overlap during a deploy.
    """
    settings = ai_settings()
    lease = now + timedelta(seconds=settings["call_seconds"] + settings["lease_margin_seconds"])
    try:
        candidates = db.session.scalars(select(AIRequest.id).where(
            AIRequest.status == "pending",
            AIRequest.created_at >= now - timedelta(seconds=settings["start_seconds"]),
            AIRequest.profile_version.in_(tuple(known_profiles)),
        ).order_by(AIRequest.created_at).limit(5)).all()
        for reply_id in candidates:
            token = f"{worker_id[:24]}:{uuid4().hex}"
            claimed = db.session.execute(update(AIRequest).where(
                AIRequest.id == reply_id, AIRequest.status == "pending",
            ).values(status="running", claim_token=token, started_at=now, lease_expires_at=lease).execution_options(
                synchronize_session=False))
            if claimed.rowcount == 1:
                db.session.commit()
                return reply_id, token
        db.session.commit()
        return None
    except Exception:
        db.session.rollback()
        raise


def reply_context(reply_id):
    """The inputs pinned to a reply's turn, read without locks; None when the request or session is gone.

    Server-side only: it holds the interviewer's instructions.
    """
    request = db.session.get(AIRequest, reply_id, populate_existing=True)
    if request is None:
        return None
    session = db.session.get(PracticeSession, request.practice_session_id, populate_existing=True)
    turn = db.session.get(SessionMessage, request.turn_message_id, populate_existing=True)
    if session is None or turn is None:
        return None
    return {
        "reply_id": request.id, "session_id": session.id, "user_id": session.user_id,
        "profile_version": request.profile_version, "provider": request.provider, "model": request.model,
        "selector_model": request.selector_model, "turn_sequence": turn.sequence,
        "context_from_sequence": request.context_from_sequence,
        **_reply_inputs(session, turn, request.context_from_sequence),
    }


def _records(session_id, *, before=None):
    """The session's disclosure, hint, and context-choice records, in order."""
    query = select(SessionMessage).where(SessionMessage.practice_session_id == session_id,
                                         SessionMessage.kind.in_(("context", "assistance")))
    if before is not None:
        query = query.where(SessionMessage.sequence < before)
    return db.session.scalars(query.order_by(SessionMessage.sequence)).all()


def _revealed(records):
    """Revealed requirement IDs in the order they were revealed, each with the reply that revealed it."""
    revealed = {}
    for row in records:
        if row.kind == "context" and row.role == "interviewer":
            for constraint_id in (row.data or {}).get("revealed", []):
                revealed.setdefault(constraint_id, (row.data or {}).get("turn_sequence"))
    return revealed


def _hints_given(records):
    return sum(1 for row in records if row.kind == "assistance" and row.role == "interviewer")


def _context_from(records):
    """Where the learner's latest Continue with recent messages choice has replies start reading; 1 means everything."""
    chosen = [(row.data or {}).get("from_sequence", 1) for row in records
              if row.kind == "context" and row.role == "learner"]
    return chosen[-1] if chosen else 1


def _reply_inputs(session, turn, context_from_sequence):
    """What a reply to `turn` is built from. Later edits never leak in: artifacts are the
    turn's cited revisions, the brief is the revision it was sent with, and what counts as
    revealed (and which hints were given) is what was recorded before the turn."""
    payload = _pinned_exercise(session).payload
    records = _records(session.id, before=turn.sequence)
    revealed_before, hints_given = list(_revealed(records)), _hints_given(records)
    hint_count = len(payload["content"]["facilitator"]["permitted_hints"])
    specs = _artifact_specs(payload)
    revision_ids = db.session.scalars(select(SessionMessageArtifact.artifact_revision_id).where(
        SessionMessageArtifact.message_id == turn.id)).all()
    revisions = db.session.scalars(select(ArtifactRevision).where(ArtifactRevision.id.in_(revision_ids)).order_by(
        ArtifactRevision.artifact_id)).all() if revision_ids else []
    brief_revision = (turn.data or {}).get("brief_revision", 0)
    brief = _brief_record(session.id, brief_revision) if brief_revision else None
    transcript = db.session.scalars(select(SessionMessage).where(
        SessionMessage.practice_session_id == session.id, SessionMessage.kind == "turn",
        SessionMessage.sequence >= context_from_sequence, SessionMessage.sequence <= turn.sequence,
    ).order_by(SessionMessage.sequence)).all()
    return {
        "exercise": {"title": payload["title"], "brief": learner_view(payload)["content"]["brief"]},
        "selector": {"message": turn.body, "hidden": selector_view(payload, revealed_constraint_ids=revealed_before),
                     "hints_left": hints_given < hint_count},
        "revealed_before": revealed_before, "hints_given": hints_given,
        "brief": {"revision": brief_revision, "entries": [_entry_dto(entry) for entry in brief.data["entries"]]
                  if brief is not None else []},
        "artifacts": [{"artifact_id": row.artifact_id, "title": specs.get(row.artifact_id, {}).get("title", row.title),
                       "revision": row.revision, "language": row.language, "body": row.body} for row in revisions],
        "transcript": [{"sequence": message.sequence, "role": message.role, "body": message.body}
                       for message in transcript],
    }


def reply_facilitator(context, selection):
    """What a reply may use: the authored instructions, the facts revealed before its turn and
    those its selector names now, and the next permitted hint only when the learner asked for
    one. Server-side only; None when the session is gone."""
    session = db.session.get(PracticeSession, context["session_id"], populate_existing=True)
    if session is None:
        return None
    return interviewer.facilitator(_pinned_exercise(session).payload, context, selection)


def _worst_case(session, turn, context_from_sequence):
    """The largest requests a reply to `turn` could make: every hidden requirement revealed at
    once and the next hint given. They bound both its cost and what the model must read."""
    settings = ai_settings()
    payload = _pinned_exercise(session).payload
    context = {"session_id": session.id, "profile_version": session.profile_version, "model": settings["model"],
               "selector_model": settings["selector_model"], "context_from_sequence": context_from_sequence,
               **_reply_inputs(session, turn, context_from_sequence)}
    facilitator = interviewer.facilitator(payload, context, {
        "constraint_ids": [item["id"] for item in context["selector"]["hidden"]], "hint_requested": True})
    return {"settings": settings, "context": context, "facilitator": facilitator,
            "selector": interviewer.selector_request(context, settings),
            "reply": interviewer.reply_request(context, facilitator, settings)}


def _narrowed(worst, index):
    """The worst-case reply reading the transcript from position `index` on."""
    transcript = worst["context"]["transcript"][index:]
    context = dict(worst["context"], transcript=transcript, context_from_sequence=transcript[0]["sequence"])
    return interviewer.reply_request(context, worst["facilitator"], worst["settings"])


def _largest_part(worst):
    """The biggest piece of what a reply must read: {"part": "artifact", "artifact_id", "title"},
    or {"part": "brief"}, {"part": "message"} (the turn itself), or {"part": "exercise"}."""
    context = worst["context"]
    parts = [({"part": "artifact", "artifact_id": artifact["artifact_id"], "title": artifact["title"]}, artifact)
             for artifact in context["artifacts"]]
    parts += [({"part": "brief"}, context["brief"]["entries"]), ({"part": "message"}, context["transcript"][-1]),
              ({"part": "exercise"}, [context["exercise"], worst["facilitator"]])]
    return max(parts, key=lambda part: len(json.dumps(part[1], ensure_ascii=False).encode("utf-8")))[0]


def _reply_obstacle(session, turn, now, context_from_sequence):
    """Why a reply to `turn` can't be queued, once AI is available: ("context_too_large", None)
    when the transcript doesn't fit what the interviewer can read, ("essential_too_large", part)
    when even the latest message with the brief and artifacts doesn't, ("budget", None) when its
    worst case doesn't fit this month's budget; otherwise (None, None).

    A reply reads the work its turn was sent with, so an essential that's too large is fixed by
    shortening it, saving, and sending a new message, never by asking again for this turn."""
    if session.profile_version not in interviewer.PROFILES:
        return None, None  # a release that knows the profile runs it, and checks before calling
    worst = _worst_case(session, turn, context_from_sequence)
    settings = worst["settings"]
    if interviewer.prompt_bytes(worst["reply"]) > settings["context_bytes"]:
        latest_only = _narrowed(worst, len(worst["context"]["transcript"]) - 1)
        if interviewer.prompt_bytes(latest_only) > settings["context_bytes"]:
            return "essential_too_large", _largest_part(worst)
        return "context_too_large", None
    total = 0
    for body, model in ((worst["selector"], settings["selector_model"]), (worst["reply"], settings["model"])):
        if body is not None:
            total += practice_budget.worst_case(settings["provider"], model, settings["tier"],
                                                input_bytes=interviewer.body_bytes(body),
                                                max_output_tokens=body["max_output_tokens"]) or 0
    return (None, None) if practice_budget.fits(total, now) else ("budget", None)


def _recent_from(session, turn):
    """The earliest message from which a reply to `turn` fits what the interviewer can read, or
    None when even the latest message alone doesn't. Fewer messages never read as more, so
    a binary search finds the longest recent stretch."""
    worst = _worst_case(session, turn, 1)
    allowance = worst["settings"]["context_bytes"]
    low, high = 0, len(worst["context"]["transcript"]) - 1
    if interviewer.prompt_bytes(_narrowed(worst, high)) > allowance:
        return None
    while low < high:
        middle = (low + high) // 2
        if interviewer.prompt_bytes(_narrowed(worst, middle)) <= allowance:
            high = middle
        else:
            low = middle + 1
    return worst["context"]["transcript"][low]["sequence"]


def begin_call(reply_id, token, *, purpose, input_bytes, max_output_tokens, deadline_seconds, now):
    """Before each paid call: fence the request, extend its lease, and reserve the worst case.

    Returns the charge ID. Raises CallFenced when the reply is no longer wanted (no
    reservation, no call), and practice_budget.BudgetExhausted when the cap would be exceeded.
    """
    settings = ai_settings()
    lease = now + timedelta(seconds=deadline_seconds + settings["lease_margin_seconds"])
    try:
        # Locks the request row (on SQLite, the database) first. A lease that has run out
        # already reads as interrupted, so it can't start a paid call either.
        held = db.session.execute(update(AIRequest).where(
            AIRequest.id == reply_id, AIRequest.status == "running", AIRequest.claim_token == token,
            AIRequest.lease_expires_at >= now,
        ).values(lease_expires_at=lease).execution_options(synchronize_session=False))
        if held.rowcount != 1:
            db.session.rollback()
            raise CallFenced("fenced")
        request = db.session.get(AIRequest, reply_id, populate_existing=True)
        # Then the session row, shared: a pause has either committed (and is seen here) or waits
        # until this call has started, and a call already in flight finishes with its reply kept.
        session = db.session.execute(select(PracticeSession).where(
            PracticeSession.id == request.practice_session_id).with_for_update(read=True)
            .execution_options(populate_existing=True)).scalar_one_or_none()
        if session is None:
            db.session.rollback()
            raise CallFenced("deleted")
        if session.status != "active":
            request.status, request.error_code, request.finished_at = "cancelled", "paused", now
            db.session.commit()
            raise CallFenced("paused")
        unavailable = reply_unavailable(session.user_id, now)
        if unavailable in ("disabled", "owner_only"):
            request.status, request.error_code, request.finished_at = "cancelled", unavailable, now
            db.session.commit()
            raise CallFenced(unavailable)
        model = request.selector_model if purpose == "select" else request.model
        try:
            charge_id = practice_budget.reserve(
                user_id=session.user_id, reply_id=reply_id, purpose=purpose, provider=request.provider, model=model,
                tier=settings["tier"], input_bytes=input_bytes, max_output_tokens=max_output_tokens,
                expires_at=lease, now=now)
        except practice_budget.BudgetExhausted as exc:
            request.status, request.error_code, request.finished_at = "failed", exc.code, now
            db.session.commit()
            raise
        db.session.commit()
        return charge_id
    except (CallFenced, practice_budget.BudgetExhausted):
        raise
    except Exception:
        db.session.rollback()
        raise


def finish_call(charge_id, *, outcome, usage=None, now):
    """Settle one call's charge in its own transaction.

    "settled" records the cost from usage (or the reservation, without usage); "released"
    means the provider refused before doing paid work; "uncertain" leaves the reservation,
    which keeps counting against the month.
    """
    try:
        if outcome == "settled":
            practice_budget.settle(charge_id, usage=usage, now=now)
        elif outcome == "released":
            practice_budget.release(charge_id, now=now)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def fail_reply(reply_id, token, *, code, now):
    """Record a definite failure, unless the request was already fenced."""
    try:
        db.session.execute(update(AIRequest).where(
            AIRequest.id == reply_id, AIRequest.status == "running", AIRequest.claim_token == token,
        ).values(status="failed", error_code=code, finished_at=now, lease_expires_at=None).execution_options(
            synchronize_session=False))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def complete_reply(reply_id, token, *, body, now, disclosure=None):
    """Write the interviewer's reply. Returns "written", "fenced", or "invalid".

    Fenced on status and claim token only, so a late reply that nothing has marked
    interrupted is still kept. The reply cites the revisions the turn was sent with.
    `disclosure` ({"constraint_ids", "hint_index"}) is what the reply was given to reveal;
    the same transaction records it after the reply, as an interviewer `context` record
    and an `assistance` record, so the revealed list and hint history match the replies.
    """
    constraint_ids = list((disclosure or {}).get("constraint_ids") or [])
    hint_index = (disclosure or {}).get("hint_index")
    try:
        found = db.session.get(AIRequest, reply_id, populate_existing=True)
        if found is None:
            return "fenced"
        session = db.session.get(PracticeSession, found.practice_session_id, populate_existing=True)
        if session is None:
            return "fenced"
        _lock_owner(session.user_id)
        request = db.session.execute(select(AIRequest).where(AIRequest.id == reply_id).with_for_update()
                                     .execution_options(populate_existing=True)).scalar_one_or_none()
        if request is None:
            db.session.rollback()
            return "fenced"
        if request.status == "completed" and request.claim_token == token:
            db.session.rollback()
            return "written"  # an earlier attempt committed before its connection failed
        if request.status != "running" or request.claim_token != token:
            db.session.rollback()
            return "fenced"
        try:
            text_body = normalize_text(body, limit=REPLY_MAX_BYTES, label="The reply").strip()
        except PracticeValidationError:
            text_body = ""
        if not text_body:
            request.status, request.error_code, request.finished_at = "failed", "invalid_output", now
            request.lease_expires_at = None
            db.session.commit()
            return "invalid"
        turn = db.session.get(SessionMessage, request.turn_message_id)
        records = _records(session.id, before=turn.sequence)
        revealed_before = _revealed(records)
        if (any(item in revealed_before for item in constraint_ids)
                or (hint_index is not None and hint_index != _hints_given(records))):
            # Only one reply per session is ever live, so this means the inputs were built wrongly.
            request.status, request.error_code, request.finished_at = "failed", "invalid_output", now
            request.lease_expires_at = None
            db.session.commit()
            return "invalid"
        reply = SessionMessage(practice_session_id=session.id, sequence=_next_sequence(session.id), role="interviewer",
                               kind="turn", modality="text", body=text_body, created_at=now,
                               data={"reply_id": request.id, "profile_version": request.profile_version,
                                     "brief_revision": (turn.data or {}).get("brief_revision", 0),
                                     "context_from_sequence": request.context_from_sequence})
        db.session.add(reply)
        db.session.flush()
        for revision_id in db.session.scalars(select(SessionMessageArtifact.artifact_revision_id).where(
                SessionMessageArtifact.message_id == turn.id)).all():
            db.session.add(SessionMessageArtifact(message_id=reply.id, artifact_revision_id=revision_id,
                                                  practice_session_id=session.id))
        for kind, data in (("context", {"revealed": constraint_ids} if constraint_ids else None),
                           ("assistance", {"hint_index": hint_index} if hint_index is not None else None)):
            if data is not None:
                db.session.add(SessionMessage(
                    practice_session_id=session.id, sequence=_next_sequence(session.id), role="interviewer",
                    kind=kind, modality="text", body="", created_at=now,
                    data={**data, "turn_sequence": reply.sequence, "reply_id": request.id}))
                db.session.flush()
        request.status, request.reply_message_id, request.finished_at = "completed", reply.id, now
        request.lease_expires_at = None
        session.updated_at = now
        db.session.commit()
        return "written"
    except Exception:
        db.session.rollback()
        raise


# Reads.

def _turns(session_id):
    """Every turn in order, with its citations and whether it gave a hint.

    The turns are read first: their citations and records commit with them, so a turn that
    lands between these reads is simply missing, never shown without its details.
    """
    messages = db.session.scalars(select(SessionMessage).where(
        SessionMessage.practice_session_id == session_id, SessionMessage.kind == "turn"
    ).order_by(SessionMessage.sequence)).all()
    citations = {}
    for message_id, artifact_id, revision in db.session.execute(
            select(SessionMessageArtifact.message_id, ArtifactRevision.artifact_id, ArtifactRevision.revision)
            .join(ArtifactRevision, ArtifactRevision.id == SessionMessageArtifact.artifact_revision_id)
            .where(SessionMessageArtifact.practice_session_id == session_id)
            .order_by(ArtifactRevision.artifact_id)):
        citations.setdefault(message_id, []).append({"artifact_id": artifact_id, "revision": revision})
    hinted = {(row.data or {}).get("turn_sequence") for row in _records(session_id)
              if row.kind == "assistance" and row.role == "interviewer"}
    return [{"sequence": message.sequence, "role": message.role, "kind": message.kind, "body": message.body,
             "created_at": _iso(message.created_at), "artifact_revisions": citations.get(message.id, []),
             "brief_revision": (message.data or {}).get("brief_revision"), "hint": message.sequence in hinted}
            for message in messages]


def _revealed_requirements(payload, records):
    """The facts revealed so far, in the order they were revealed, each with the reply that revealed it."""
    revealed = _revealed(records)
    facts = {item["id"]: item["fact"] for item in
             interviewer_view(payload, revealed_constraint_ids=list(revealed))["revealed_constraints"]}
    return [{"id": constraint_id, "fact": facts[constraint_id], "sequence": sequence}
            for constraint_id, sequence in revealed.items()]


def _context_choices(records):
    """Each Continue with recent messages choice: where it was made, and where replies read from after it."""
    return [{"sequence": row.sequence, "from_sequence": (row.data or {}).get("from_sequence", 1)}
            for row in records if row.kind == "context" and row.role == "learner"]


def session_detail(user_id, session_id, *, now=None):
    """The learner-safe view of a session: exercise brief, the learner's brief, artifacts, transcript, and reply."""
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
    now = now or _now()
    # Read the reply's state before the transcript: if the reply lands between the two reads,
    # the page shows it as still coming (and polls) rather than as arrived but missing. The
    # records come last, so every turn shown has its own.
    reply = reply_summary(session, now)
    messages = _turns(session.id)
    records = _records(session.id)
    learner_turns = sum(1 for message in messages if message["role"] == "learner")
    check_in = ai_settings()["check_in_turns"]
    return {"session": _session_dto(session, payload), "brief": brief,
            "session_brief": _brief_dto(_brief_record(session.id)), "artifacts": artifacts,
            "messages": messages, "reply": reply, "ai_budget": ai_budget(session.user_id, now),
            "revealed_requirements": _revealed_requirements(payload, records),
            "context_choices": _context_choices(records),
            "learner_turns": learner_turns, "check_in_due": check_in > 0 and learner_turns >= check_in}


def session_counts(user_id, session_id):
    """What deleting a session would remove."""
    session = _owned_session(user_id, session_id)

    def count(model, *conditions):
        return db.session.scalar(select(func.count()).select_from(model).where(
            model.practice_session_id == session.id, *conditions))
    return {"session": _session_dto(session, _pinned_exercise(session).payload),
            "turns": count(SessionMessage, SessionMessage.kind == "turn"),
            "brief_revisions": count(SessionMessage, SessionMessage.kind == "brief"),
            "artifact_revisions": count(ArtifactRevision)}


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
