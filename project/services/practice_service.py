"""Practice sessions: a pinned exercise, an ordered record, and immutable artifact revisions.

Every mutation follows one order: validate input, take the owner's user-row lock, check
the request receipt, read owner-scoped rows fresh, write, record the receipt, commit.
Deletion takes the same lock, and so must later writers (the AI worker).

The ordered record holds conversation turns and snapshots of the learner's brief
(kind='brief'). A learner turn cites the exact artifact revisions it was sent with.
Learner text never goes into receipts (they store a payload hash) or log messages.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy import and_, func, select, update

from project.curriculum_terms import ARTIFACT_LANGUAGES, BRIEF_ENTRY_TYPES, FORMAT_LANGUAGES
from project.database import db
from project.learning.content_schema import learner_view, opening_view
from project.models import (
    ArtifactRevision, ContentRevision, CurriculumItem, PracticeReceipt, PracticeSession,
    SessionMessage, SessionMessageArtifact, User,
)
from project.services import curriculum_service, learning_service
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError


def validate_request_id(value):
    # learning_service may still be loading when this module is imported; look it up at call time.
    return learning_service.validate_request_id(value)

ARTIFACT_MAX_BYTES = 64 * 1024
TURN_MAX_BYTES = 8 * 1024
BRIEF_MAX_ENTRIES = 50
BRIEF_ENTRY_MAX_BYTES = 2 * 1024
MAX_EDITS = 20
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
    return turn.sequence, cited


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
        sequence, cited = _append_turn(session, specs, text, brief_outcome["revision"], now)
        if session.status == "paused":
            _set_status(session, "active")
        session.updated_at = now
        response = {"session_id": session.id, "sequence": sequence, "artifact_revisions": cited,
                    "brief_revision": brief_outcome["revision"], "artifacts": outcomes, "brief": brief_outcome,
                    "status": session.status}
        _record(user.id, request_id, session.id, "send", digest, response, now)
        db.session.commit()
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
        sequence, cited = _append_turn(session, specs, text, brief_number, now)
        if session.status == "paused":
            _set_status(session, "active")
        session.updated_at = now
        response = {"session_id": session.id, "sequence": sequence, "artifact_revisions": cited,
                    "brief_revision": brief_number, "status": session.status}
        _record(user.id, request_id, session.id, "send", digest, response, now)
        db.session.commit()
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
        _lock_owner(user.id)
        session = _owned_session(user.id, session_id)
        concept_id = _pinned_exercise(session).payload["content"]["concept_id"]
        db.session.delete(session)
        db.session.commit()
        return {"session_id": session_id, "concept_id": concept_id}
    except Exception:
        db.session.rollback()
        raise


# Reads.

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
             "created_at": _iso(message.created_at), "artifact_revisions": citations.get(message.id, []),
             "brief_revision": (message.data or {}).get("brief_revision")}
            for message in messages]


def session_detail(user_id, session_id):
    """The learner-safe view of a session: exercise brief, the learner's brief, artifacts, and transcript."""
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
    return {"session": _session_dto(session, payload), "brief": brief,
            "session_brief": _brief_dto(_brief_record(session.id)), "artifacts": artifacts,
            "messages": _turns(session.id)}


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
