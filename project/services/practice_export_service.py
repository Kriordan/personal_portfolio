"""Portable, learner-safe exports from one read-only database snapshot.

No request receipts, provider inputs, private assessment packet, or account-wide
progress are serialized. The export is fully built before a download is sent.
"""
from datetime import timezone
from html import escape
import json
import re

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from project.database import db
from project.learning.content_schema import learner_view
from project.models import (ArtifactRevision, ContentRevision, PracticeFeedback, PracticeFeedbackAnnotation,
    PracticeSession, ReviewLog, SessionMessage, SessionMessageArtifact)
from project.services import feedback_review_service, practice_service as practice
from project.services.learning_errors import NotFoundError

DEFAULT_MAX_BYTES = 32 * 1024 * 1024
FORMATS = {"json": "application/json", "md": "text/markdown"}


class ExportTooLarge(Exception):
    """Refuse an oversized download rather than silently omit saved history."""


def _limit():
    return current_app.config.get("LEARNING_EXPORT_MAX_BYTES", DEFAULT_MAX_BYTES)


def _time(value):
    return practice._aware(value).astimezone(timezone.utc).isoformat() if value is not None else None


def _json(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, **kwargs)


class _Budget:
    def __init__(self):
        self.remaining = _limit()

    def keep(self, value):
        self.remaining -= len(_json(value).encode("utf-8")) + 2
        if self.remaining < 0:
            raise ExportTooLarge()
        return value


def _rows(reader, query):
    # Stream database batches; don't load unlimited artifact history before
    # applying the byte allowance. The final response is buffered, never partial.
    return reader.scalars(query.execution_options(yield_per=50))


def session_export(user_id, session_id, *, now=None):
    practice._check_session_id(session_id)
    if db.engine.dialect.name == "sqlite" and isinstance(db.engine.pool, StaticPool):
        # In-memory SQLite shares one physical connection. Checking out another
        # wrapper would roll back a caller's flushed writes when it closes.
        caller = db.session()
        if caller.in_transaction() and caller.connection().connection.driver_connection.in_transaction:
            raise InvalidRequestError("Commit or roll back in-memory SQLite work before exporting.")
    # Authentication may already have opened the request's ORM transaction.
    # Use an independent connection so isolation never rolls back caller work.
    with db.engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
        with connection.begin():
            if connection.dialect.name == "postgresql":
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            elif connection.dialect.name == "sqlite":
                # sqlite3's legacy mode doesn't BEGIN on SELECT by itself.
                connection.exec_driver_sql("BEGIN")
            with Session(bind=connection, autoflush=False) as reader:
                session = reader.scalar(select(PracticeSession).where(
                    PracticeSession.id == session_id, PracticeSession.user_id == user_id))
                if session is None:
                    raise NotFoundError("practice session not found")
                return _contents(reader, session, now or practice._now())


def _contents(reader, session, now):
    budget = _Budget()
    payload = reader.get(ContentRevision, (session.exercise_id, session.exercise_version)).payload
    exercise = learner_view(payload)
    result = budget.keep({"format": "engineering-learning.practice-session", "schema_version": 1,
        "exported_at": _time(now), "session": {**practice._session_dto(session, payload),
            "profile_version": session.profile_version, "created_at": _time(session.created_at),
            "updated_at": _time(session.updated_at)}, "exercise": exercise})
    artifacts = {}
    for spec in exercise["content"]["brief"]["expected_artifacts"]:
        artifacts[spec["id"]] = budget.keep({"artifact_id": spec["id"], "title": spec["title"],
            "format": spec["format"], "current_revision": 0, "revisions": [
                {"revision": 0, "language": practice.default_language(spec["format"]), "body": "", "saved_at": None}]})
    for row in _rows(reader, select(ArtifactRevision).where(ArtifactRevision.practice_session_id == session.id)
                     .order_by(ArtifactRevision.artifact_id, ArtifactRevision.revision)):
        artifact = artifacts[row.artifact_id]
        artifact["revisions"].append(budget.keep({"revision": row.revision, "language": row.language,
            "body": row.body, "saved_at": _time(row.created_at)}))
        artifact["current_revision"] = row.revision
    result["artifacts"] = list(artifacts.values())

    citations = {}
    query = select(SessionMessageArtifact.message_id, ArtifactRevision.artifact_id, ArtifactRevision.revision).join(
        ArtifactRevision, ArtifactRevision.id == SessionMessageArtifact.artifact_revision_id).where(
        SessionMessageArtifact.practice_session_id == session.id).order_by(
            SessionMessageArtifact.message_id, ArtifactRevision.artifact_id)
    for message_id, artifact_id, revision in reader.execute(query.execution_options(yield_per=50)):
        citations.setdefault(message_id, []).append(budget.keep({"artifact_id": artifact_id, "revision": revision}))

    turns, briefs, submissions, records, snapshot_ids = [], [practice._brief_dto(None)], [], [], {}
    for row in _rows(reader, select(SessionMessage).where(SessionMessage.practice_session_id == session.id)
                     .order_by(SessionMessage.sequence)):
        if row.kind == "turn":
            turns.append(budget.keep({"sequence": row.sequence, "role": row.role, "body": row.body,
                "created_at": _time(row.created_at), "artifact_revisions": citations.get(row.id, []),
                "brief_revision": (row.data or {}).get("brief_revision"), "hint": False}))
        elif row.kind == "brief":
            briefs.append(budget.keep({**practice._brief_dto(row), "sequence": row.sequence, "saved_at": _time(row.created_at)}))
        elif row.kind == "submission":
            item = budget.keep({**practice._submission_dto(row), "feedback": None})
            submissions.append(item)
            snapshot_ids[row.id] = item
        elif row.kind in ("context", "assistance"):
            # Only these records' public projections are exported below.
            # Bound memory even if many small records are present.
            budget.keep({"sequence": row.sequence, "role": row.role, "kind": row.kind, "data": row.data})
            records.append(row)
    hinted = {(r.data or {}).get("turn_sequence") for r in records if r.kind == "assistance" and r.role == "interviewer"}
    for turn in turns:
        turn["hint"] = turn["sequence"] in hinted
    result.update(transcript=turns, brief_revisions=briefs, submissions=submissions,
        revealed_requirements=practice._revealed_requirements(payload, records),
        context_choices=practice._context_choices(records))

    annotations = {}
    for row in _rows(reader, select(PracticeFeedbackAnnotation).join(PracticeFeedback,
            PracticeFeedbackAnnotation.feedback_request_id == PracticeFeedback.request_id).where(
                PracticeFeedback.practice_session_id == session.id)):
        annotations[(row.feedback_request_id, row.finding_id)] = budget.keep(feedback_review_service.annotation_dto(row))
    dimensions = {d["id"]: d["label"] for d in exercise["content"]["brief"]["assessment_dimensions"]}
    review_sources = {}
    for row in _rows(reader, select(PracticeFeedback).where(PracticeFeedback.practice_session_id == session.id)
                     .order_by(PracticeFeedback.submission_id)):
        item = snapshot_ids[row.submission_id]
        item["feedback"] = budget.keep(_feedback(row, dimensions, annotations))
        for finding in item["feedback"]["findings"]:
            review_sources[f"feedback:{row.request_id}:{finding['id']}"] = (item["sequence"], finding["id"])
    # The tag joins only this session's saved feedback. Other sessions and the
    # learner's ordinary review history are outside a practice-session export.
    ratings = []
    query = select(ReviewLog).join(PracticeFeedback,
        ReviewLog.session_id.like("feedback:" + PracticeFeedback.request_id + ":%"))
    query = query.where(ReviewLog.user_id == session.user_id,
        PracticeFeedback.practice_session_id == session.id).order_by(ReviewLog.reviewed_at, ReviewLog.id)
    for row in _rows(reader, query):
        if row.session_id in review_sources:
            sequence, finding_id = review_sources[row.session_id]
            ratings.append(budget.keep({"submission_sequence": sequence, "finding_id": finding_id,
                "card_id": row.card_id, "content_version": row.content_version,
                "rating": row.rating, "reviewed_at": _time(row.reviewed_at)}))
    result["followup_ratings"] = ratings
    return result


def _feedback(row, dimensions, annotations):
    findings = []
    for finding in row.data["findings"]:
        evidence = []
        for citation in finding["evidence"]:
            location = {"turn": ("sequence",), "artifact": ("artifact_id", "revision"),
                        "note": ("entry_id", "revision")}[citation["kind"]]
            evidence.append({key: citation[key] for key in ("kind", "quote", "line", *location)})
        findings.append({**{key: finding[key] for key in (
            "id", "kind", "dimension_id", "title", "explanation", "next_step")},
            "dimension_label": dimensions[finding["dimension_id"]], "evidence": evidence,
            "remediation": [{key: link[key] for key in ("concept_id", "section_id")} for link in finding["remediation"]],
            "annotation": annotations.get((row.request_id, finding["id"]), feedback_review_service.annotation_dto())})
    coverage = row.data["coverage"]
    return {"created_at": _time(row.created_at), "summary": row.data["summary"], "findings": findings,
        "coverage": {**{key: coverage[key] for key in ("complete_snapshot", "through_sequence", "turn_count",
            "learner_turn_count", "brief_revision", "hints_given")},
            "artifact_revisions": [{key: a[key] for key in ("artifact_id", "revision")} for a in coverage["artifact_revisions"]],
            "context_choices": [{key: c[key] for key in ("sequence", "from_sequence")} for c in coverage["context_choices"]]}}


def _prose(value):
    # Render learner/provider prose literally in Markdown viewers. In particular,
    # don't turn saved HTML or image/link syntax into active document content.
    return re.sub(r"([\\`*_{}\[\]()#+.!|~\-])", r"\\\1", escape(str(value), quote=False))


def _fence(body, language="text"):
    fence = "`" * max(3, max((len(run) + 1 for run in re.findall(r"`+", body)), default=0))
    return f"{fence}{language}\n{body}\n{fence}"


def markdown(document):
    parts = []
    remaining = _limit()

    def add(text):
        nonlocal remaining
        remaining -= len(text.encode("utf-8")) + 2
        if remaining < 0:
            raise ExportTooLarge()
        parts.append(text)

    def prose(text):
        add("\n".join("> " + line for line in _prose(text).split("\n")))

    session = document["session"]
    add("# Practice session: " + _prose(session["exercise_title"]))
    add(f"Session: {session['id']}  \nExercise: {_prose(session['exercise_id'])}, version {session['exercise_version']}  \n"
        f"Status: {session['status']}  \nExported: {document['exported_at']}  \nExport schema: {document['schema_version']}")
    add("Saved work only. Unsaved edits, unsent messages, and unfinished AI output are not included. "
        "AI feedback is a judgment to review, not a grade. This file is a portable record, not an import or backup restore format.")
    brief = document["exercise"]["content"]["brief"]
    add("## Exercise")
    prose(brief["scenario"])
    for key, title in (("learning_objectives", "Learning objectives"), ("functional_requirements", "Functional requirements"),
                       ("nonfunctional_requirements", "Nonfunctional requirements")):
        add("### " + title)
        for entry in brief[key]:
            prose(entry)
    add("## Revealed requirements")
    for entry in document["revealed_requirements"]:
        add(f"### Revealed at turn {entry['sequence']}")
        prose(entry["fact"])
    if not document["revealed_requirements"]:
        add("No additional requirements had been revealed.")
    add("## Conversation")
    for turn in document["transcript"]:
        add(f"### Turn {turn['sequence']}: {turn['role']}" + (" (hint given)" if turn["hint"] else ""))
        add(f"Saved: {turn['created_at']} · Notes revision: {turn['brief_revision'] or 0}")
        prose(turn["body"])
        for ref in turn["artifact_revisions"]:
            add(f"Artifact: {_prose(ref['artifact_id'])}, revision {ref['revision']}")
    for choice in document["context_choices"]:
        add(f"At record {choice['sequence']}, continued the interview from turn {choice['from_sequence']}. "
            "Earlier conversation remains in this export.")
    add("## Artifacts and revision history")
    for artifact in document["artifacts"]:
        add(f"### {_prose(artifact['title'])} ({_prose(artifact['artifact_id'])})")
        add(f"Current revision: {artifact['current_revision']}")
        for revision in artifact["revisions"]:
            add(f"#### Revision {revision['revision']} · {revision['language']} · {revision['saved_at'] or 'Initial empty work'}")
            add(_fence(revision["body"], revision["language"]))
    add("## Notes and revision history")
    for revision in document["brief_revisions"]:
        add(f"### Notes revision {revision['revision']} · {revision['saved_at'] or 'Initial empty notes'}")
        for entry in revision["entries"]:
            add(f"#### {_prose(entry['type'])}: {_prose(entry['id'])}" + (" (pinned)" if entry["pinned"] else ""))
            prose(entry["text"])
            for source in entry["sources"]:
                add(f"Source: turn {source['turn']}" if "turn" in source else
                    f"Source: {_prose(source['artifact_id'])}, revision {source['revision']}")
    add("## Saved snapshots and feedback")
    for snapshot in document["submissions"]:
        add(f"### Snapshot {snapshot['sequence']} · {snapshot['created_at']}")
        add(f"Conversation through record {snapshot['through_sequence']}; notes revision {snapshot['brief_revision']}. "
            f"Checker: {_prose(snapshot['checker_version'])}.")
        for check in snapshot["checks"]:
            add(f"{_prose(check['artifact_id'])}, revision {check['revision']}: {_prose(check['status'])}. "
                f"{_prose(check['message'])}" + (f" Line {check['line']}, column {check['column']}." if check['line'] else ""))
        feedback = snapshot["feedback"]
        if feedback is None:
            add("No completed feedback saved for this snapshot.")
            continue
        prose(feedback["summary"])
        coverage = feedback["coverage"]
        add(f"Assessed {coverage['turn_count']} conversation turns; {coverage['hints_given']} recorded hints. "
            "Later work is not part of this assessment.")
        for finding in feedback["findings"]:
            add(f"#### {_prose(finding['kind'])}: {_prose(finding['title'])} ({finding['id']})")
            add(_prose(finding["dimension_label"]))
            prose(finding["explanation"])
            for evidence in finding["evidence"]:
                label = (f"Turn {evidence['sequence']}" if evidence["kind"] == "turn" else
                         f"Artifact {_prose(evidence['artifact_id'])}, revision {evidence['revision']}" if evidence["kind"] == "artifact" else
                         f"Note {_prose(evidence['entry_id'])}, revision {evidence['revision']}")
                add(f"Evidence: {label}, line {evidence['line']}.")
                prose(evidence["quote"])
            add("Next step:")
            prose(finding["next_step"])
            for link in finding["remediation"]:
                add(f"Revisit concept {_prose(link['concept_id'])}, section {_prose(link['section_id'])}.")
            annotation = finding["annotation"]
            add(f"Your response: {annotation['decision']} (revision {annotation['revision']}).")
            if annotation["note"]:
                prose(annotation["note"])
    add("## Explicit follow-up ratings")
    for rating in document["followup_ratings"]:
        add(f"Snapshot {rating['submission_sequence']}, finding {rating['finding_id']}: "
            f"{_prose(rating['card_id'])} v{rating['content_version']} · rating {rating['rating']} · {rating['reviewed_at']}")
    if not document["followup_ratings"]:
        add("No follow-up ratings saved for these findings.")
    return "\n\n".join(parts) + "\n"


def render(document, format):
    if format not in FORMATS:
        raise practice.PracticeValidationError("Choose JSON or Markdown.")
    body = (_json(document, indent=2) + "\n") if format == "json" else markdown(document)
    data = body.encode("utf-8")
    if len(data) > _limit():
        raise ExportTooLarge()
    return data


def export_file(user_id, session_id, format):
    if format not in FORMATS:
        raise practice.PracticeValidationError("Choose JSON or Markdown.")
    document = session_export(user_id, session_id)
    return {"filename": f"practice-{session_id}.{format}", "mimetype": FORMATS[format],
            "data": render(document, format)}
