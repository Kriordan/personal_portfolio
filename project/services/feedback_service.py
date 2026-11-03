"""One bounded evaluation of an immutable submission, using the existing worker/ledger.

The snapshot is the complete original transcript through its boundary, the artifact
revisions it saved (plus revisions cited by those turns), and its saved notes. Recent-
message continuation never truncates evaluation. Private inputs are built here only;
learner reads use explicit projections. No grades or review-progress mutations.
"""
from datetime import timedelta, timezone
from uuid import uuid4

from flask import current_app
from sqlalchemy import select

from project.database import db
from project.learning import evaluator, interviewer
from project.learning.content_schema import evaluator_view, learner_view
from project.models import AIRequest, ArtifactRevision, PracticeFeedback, PracticeSession, SessionMessage, SessionMessageArtifact
from project.services import practice_budget, practice_service as practice
from project.services.learning_errors import NotFoundError


def settings():
    base = practice.ai_settings()
    return {**base, "model": current_app.config.get("LEARNING_AI_FEEDBACK_MODEL") or base["model"],
            "reasoning_effort": current_app.config.get("LEARNING_AI_FEEDBACK_REASONING_EFFORT") or "medium",
            "max_output_tokens": int(current_app.config.get("LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS", 4000))}


def unavailable(user_id, now):
    config = settings()
    if (not config["enabled"] or not practice.provider_ready(config) or not config["model"]
            or not practice_budget.priced(config["provider"], config["model"], config["tier"])):
        return "disabled"
    if practice.ai_owner_id() != user_id:
        return "owner_only"
    smallest = practice_budget.worst_case(config["provider"], config["model"], config["tier"],
                                         input_bytes=0, max_output_tokens=config["max_output_tokens"])
    if practice_budget.month_status(now, smallest_microusd=smallest)["exhausted"]:
        return "budget"
    return None


def _snapshot(session, sequence):
    row = db.session.scalar(select(SessionMessage).where(
        SessionMessage.practice_session_id == session.id, SessionMessage.kind == "submission",
        SessionMessage.sequence == sequence)) if practice._whole_number(sequence, minimum=1) else None
    if row is None:
        raise NotFoundError("snapshot not found")
    return row


def _inputs(session, snapshot):
    payload = practice._pinned_exercise(session).payload
    through = snapshot.data["through_sequence"]
    transcript = [t for t in practice._turns(session.id) if t["sequence"] <= through]
    records = practice._records(session.id, before=snapshot.sequence)
    sources = {}
    for turn in transcript:
        if turn["role"] == "learner":
            source_id = f"turn-{turn['sequence']}"
            turn["source_id"] = source_id
            sources[source_id] = {"body": turn["body"], "reference": {"kind": "turn", "sequence": turn["sequence"]}}
    # Include original cited artifact revisions as well as the snapshot's selected heads.
    revisions = db.session.scalars(select(ArtifactRevision).join(
        SessionMessageArtifact, SessionMessageArtifact.artifact_revision_id == ArtifactRevision.id).join(
        SessionMessage, SessionMessage.id == SessionMessageArtifact.message_id).where(
        SessionMessage.practice_session_id == session.id,
        ((SessionMessage.kind == "turn") & (SessionMessage.sequence <= through)) | (SessionMessage.id == snapshot.id)
    ).distinct().order_by(ArtifactRevision.artifact_id, ArtifactRevision.revision)).all()
    selected = {c["artifact_id"]: c["revision"] for c in snapshot.data["checks"]}
    artifacts = []
    for row in revisions:
        source_id = f"artifact-{row.artifact_id}-{row.revision}"
        reference = {"kind": "artifact", "artifact_id": row.artifact_id, "revision": row.revision}
        sources[source_id] = {"body": row.body, "reference": reference}
        artifacts.append({"source_id": source_id, "artifact_id": row.artifact_id, "revision": row.revision,
                          "selected": selected[row.artifact_id] == row.revision, "title": row.title,
                          "language": row.language, "body": row.body})
    for artifact_id, spec in practice._artifact_specs(payload).items():
        if selected[artifact_id] == 0:
            artifacts.append({"artifact_id": artifact_id, "revision": 0, "selected": True,
                              "title": spec["title"], "language": practice._state(None, spec)[1], "body": ""})
    revision = snapshot.data["brief_revision"]
    brief = practice._brief_dto(practice._brief_record(session.id, revision) if revision else None)
    for entry in brief["entries"]:
        source_id = f"note-{entry['id']}-{revision}"
        entry["source_id"] = source_id
        sources[source_id] = {"body": entry["text"], "reference": {
            "kind": "note", "entry_id": entry["id"], "revision": revision}}
    revealed = practice._revealed(records)
    return {"exercise": learner_view(payload)["content"], "assessment": evaluator_view(payload),
            "requirements": [{"id": r["id"], "fact": r["fact"], "revealed": r["id"] in revealed}
                             for r in payload["content"]["facilitator"]["hidden_constraints"]],
            "transcript": transcript, "artifacts": artifacts, "brief": brief, "sources": sources,
            "syntax_checks": practice._submission_dto(snapshot)["checks"],
            "coverage": {"complete_snapshot": True, "through_sequence": through,
                         "turn_count": len(transcript), "learner_turn_count": sum(t["role"] == "learner" for t in transcript),
                         "artifact_revisions": [{"artifact_id": key, "revision": value} for key, value in selected.items()],
                         "brief_revision": revision, "hints_given": practice._hints_given(records),
                         "context_choices": practice._context_choices(records)}}


def context(request_id):
    """Private worker input only. Never serialize this object to a learner response."""
    request = db.session.get(AIRequest, request_id, populate_existing=True)
    if request is None or request.kind != "feedback":
        return None
    session = db.session.get(PracticeSession, request.practice_session_id, populate_existing=True)
    snapshot = db.session.get(SessionMessage, request.turn_message_id)
    if session is None or snapshot is None or snapshot.kind != "submission":
        return None
    return {"model": request.model, "profile_version": request.profile_version, **_inputs(session, snapshot)}


def _obstacle(session, snapshot, now):
    config = settings()
    inputs = {"model": config["model"], "profile_version": evaluator.PROFILE, **_inputs(session, snapshot)}
    body = evaluator.request_body(inputs, config)
    if interviewer.body_bytes(body) > config["context_bytes"]:
        return "context_too_large"
    worst = practice_budget.worst_case(config["provider"], config["model"], config["tier"],
                                      input_bytes=interviewer.body_bytes(body), max_output_tokens=config["max_output_tokens"])
    if practice_budget.month_status(now, smallest_microusd=worst)["exhausted"]:
        return "budget"
    return None


def request_feedback(user, session_id, sequence, *, request_id, now=None):
    practice.validate_request_id(request_id)
    practice._check_session_id(session_id)
    if not practice._whole_number(sequence, minimum=1):
        raise practice.PracticeValidationError("Choose a saved snapshot.")
    digest = practice._digest("feedback", session_id, {"sequence": sequence})
    now = now or practice._now()
    try:
        practice._lock_owner(user.id)
        replay = practice._replay(user.id, request_id, "feedback", digest)
        if replay is not None:
            db.session.commit()
            practice._wake_worker(replay["request"])
            return replay
        session = practice._owned_session(user.id, session_id)
        snapshot = _snapshot(session, sequence)
        completed = db.session.scalar(select(AIRequest).where(
            AIRequest.turn_message_id == snapshot.id, AIRequest.kind == "feedback", AIRequest.status == "completed"))
        live = practice._settle_stale_reply(session, now)
        if completed is not None:
            state = practice._reply_dto(completed.id, "completed")
        elif live is not None and live.kind == "feedback" and live.turn_message_id == snapshot.id:
            state = practice._reply_dto(live.id, live.status)
        else:
            if live is not None:
                practice._raise_pending(live)
            if session.status not in practice.OPEN_STATUSES:
                raise practice.PracticeValidationError("A completed session can't request feedback.")
            reason = unavailable(user.id, now) or _obstacle(session, snapshot, now)
            state = practice._reply_dto(reason=reason)
            if not reason:
                config = settings()
                previous = db.session.scalar(select(AIRequest.created_at).where(
                    AIRequest.turn_message_id == snapshot.id, AIRequest.kind == "feedback"
                ).order_by(AIRequest.created_at.desc()).limit(1))
                # Deterministic ordering even under a frozen clock or sub-microsecond retries.
                created = max(now, practice._aware(previous) + timedelta(microseconds=1)) if previous else now
                row = AIRequest(id=str(uuid4()), practice_session_id=session.id, turn_message_id=snapshot.id,
                                kind="feedback", status="pending", profile_version=evaluator.PROFILE,
                                provider=config["provider"], model=config["model"], selector_model=config["model"],
                                context_from_sequence=1, created_at=created)
                db.session.add(row)
                practice._set_status(session, "active")
                session.updated_at = now
                state = practice._reply_dto(row.id, "pending")
        response = {"session_id": session.id, "submission_sequence": sequence, "request": state}
        practice._record(user.id, request_id, session.id, "feedback", digest, response, now)
        db.session.commit()
        practice._wake_worker(state)
        return response
    except Exception:
        db.session.rollback()
        raise


def _dto(row, session):
    """Validated generated prose is learner content; private authored mappings stay server-side."""
    from project.services import feedback_review_service as review
    annotations = review.annotations(row.request_id)
    dimensions = {d["id"]: d["label"] for d in
                  learner_view(practice._pinned_exercise(session).payload)["content"]["brief"]["assessment_dimensions"]}
    findings = []
    for f in row.data["findings"]:
        annotation = annotations.get(f["id"], review.annotation_dto())
        findings.append({"dimension_label": dimensions[f["dimension_id"]], "annotation": annotation,
                         "practice_available": annotation["decision"] == "agree" and bool(review.targets(session, f)),
                         **{key: f[key] for key in (
            "id", "kind", "dimension_id", "title", "explanation", "next_step", "evidence", "remediation")}})
    return {"request_id": row.request_id, "created_at": practice._iso(practice._aware(row.created_at).astimezone(timezone.utc)),
            "summary": row.data["summary"], "findings": findings, "coverage": row.data["coverage"]}


def detail(user_id, session_id, sequence, *, now=None):
    session = practice._owned_session(user_id, session_id)
    snapshot = _snapshot(session, sequence)
    now = now or practice._now()
    request = db.session.scalar(select(AIRequest).where(
        AIRequest.turn_message_id == snapshot.id, AIRequest.kind == "feedback"
    ).order_by(AIRequest.created_at.desc(), AIRequest.id.desc()).limit(1))
    reason = unavailable(user_id, now)
    # Read state before the result: if completion lands between reads, poll once more.
    state = practice._reply_dto(reason=reason)
    if request is not None:
        status, code = practice._effective(request, now, reason)
        state = practice._reply_dto(request.id, status, code)
    row = db.session.scalar(select(PracticeFeedback).where(PracticeFeedback.submission_id == snapshot.id))
    live = db.session.scalar(select(AIRequest).where(
        AIRequest.practice_session_id == session.id, AIRequest.status.in_(practice.LIVE)))
    busy = None
    if live is not None and (request is None or live.id != request.id):
        effective, _ = practice._effective(live, now, practice._request_unavailable(live, user_id, now))
        if effective in practice.LIVE:
            busy = live.kind
    return {"submission_sequence": sequence, "request": state, "feedback": _dto(row, session) if row else None,
            "unavailable": reason, "busy": busy,
            "can_request": row is None and state["status"] not in practice.LIVE and not reason and not busy
                           and session.status in practice.OPEN_STATUSES}


def pending(session, now):
    """Workspace notice only; saves stay available while feedback is running."""
    request = db.session.scalar(select(AIRequest).where(
        AIRequest.practice_session_id == session.id, AIRequest.kind == "feedback", AIRequest.status.in_(practice.LIVE)))
    if request is None or practice._effective(request, now, unavailable(session.user_id, now))[0] not in practice.LIVE:
        return None
    snapshot = db.session.get(SessionMessage, request.turn_message_id)
    return {"sequence": snapshot.sequence, "status": request.status} if snapshot is not None else None


def complete(request_id, token, *, output, now):
    """Fenced, idempotent write. A late in-flight result survives pause, never deletion/retry."""
    try:
        found = db.session.get(AIRequest, request_id, populate_existing=True)
        if found is None or found.kind != "feedback":
            return "fenced"
        session = db.session.get(PracticeSession, found.practice_session_id, populate_existing=True)
        if session is None:
            return "fenced"
        practice._lock_owner(session.user_id)
        request = db.session.scalar(select(AIRequest).where(AIRequest.id == request_id).with_for_update()
                                    .execution_options(populate_existing=True))
        if request is None or request.claim_token != token or request.status not in ("running", "completed"):
            db.session.rollback()
            return "fenced"
        if request.status == "completed":
            db.session.rollback()
            return "written"
        try:
            data = evaluator.validate(output, context(request_id))
        except evaluator.InvalidFeedback:
            request.status, request.error_code, request.finished_at = "failed", "invalid_output", now
            request.lease_expires_at = None
            db.session.commit()
            return "invalid"
        db.session.add(PracticeFeedback(request_id=request_id, practice_session_id=session.id,
                                         submission_id=request.turn_message_id, data=data, created_at=now))
        request.status, request.finished_at, request.lease_expires_at = "completed", now, None
        db.session.commit()
        return "written"
    except Exception:
        db.session.rollback()
        raise
