"""Synthetic release review through the real snapshot, worker, validator and budget path.

The CLI refuses any database except its named local disposable PostgreSQL databases.
Keep that database across rounds: the $2 total ceiling includes uncertain charges.
Raw outputs here are synthetic evaluation artifacts, never production learner data.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from flask import current_app
from sqlalchemy import case as sql_case, func, select
from sqlalchemy.engine import make_url

from project.curriculum_terms import CURRENT_PROFILES
from project.database import db
from project.learning import interviewer
from project.learning.content_schema import load_catalog
from project.models import ContentRevision, CurriculumItem, LearningAICharge, PracticeFeedback, PracticeSession, SessionMessage, User
from project.services import curriculum_service, feedback_service, practice_service as practice, practice_worker
from project.services.learning_ai_provider import ProviderError

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests/fixtures/feedback/cases-v1.json"
OWNER = "feedback-evaluation@example.test"
CAP_MICROUSD = 2_000_000
MAX_CALLS = 40
LOCK = (1427870284, 3)


def guard_url(url, provider):
    parsed = make_url(url)
    database = "learning_feedback_eval" if provider == "openai" else "learning_feedback_eval_fake"
    if parsed.get_backend_name() != "postgresql" or parsed.host not in ("127.0.0.1", "localhost") or parsed.database != database:
        raise ValueError(f"Use only the local disposable PostgreSQL database {database}.")


def load_cases():
    document = json.loads(CASES.read_text())
    if document["schema_version"] != 1 or len({c["id"] for c in document["cases"]}) != len(document["cases"]):
        raise ValueError("Invalid evaluation fixture version or duplicate case ID.")
    return document


def seed():
    """Fixtures only. No importer publication or human-review attestation on a real DB."""
    db.create_all()
    users = db.session.scalars(select(User)).all()
    if users and (len(users) != 1 or users[0].id != 1 or users[0].email != OWNER):
        raise ValueError("Unexpected data in the evaluation database.")
    if not users:
        db.session.add(User(id=1, username="Synthetic evaluation", email=OWNER, email_verified=True))
    now = datetime.now(timezone.utc)
    for name in ("catalog.json", "catalog-v2.json"):
        catalog = load_catalog(ROOT / "curriculum/idempotency" / name)
        for item in catalog["items"]:
            if db.session.get(CurriculumItem, item["id"]) is None:
                db.session.add(CurriculumItem(id=item["id"], kind=item["kind"]))
                db.session.flush()
            existing = db.session.get(ContentRevision, (item["id"], item["version"]))
            checksum = curriculum_service.content_checksum(item, catalog["schema_version"])
            if existing is not None and existing.checksum != checksum:
                raise ValueError("Fixture content changed; do not overwrite the pinned review dataset.")
            if existing is None:
                db.session.add(ContentRevision(item_id=item["id"], version=item["version"], schema_version=catalog["schema_version"],
                    payload=item, checksum=checksum, imported_at=now, published_at=now,
                    reviewed_by="Synthetic evaluation fixture, not production publication", reviewed_on=now.date()))
    db.session.commit()


def _record(sid, role, kind, body="", data=None):
    row = SessionMessage(practice_session_id=sid, sequence=practice._next_sequence(sid),
                         role=role, kind=kind, body=body, data=data or {}, modality="text", created_at=practice._now())
    db.session.add(row)
    db.session.commit()
    return row.sequence


def _send(sid, body):
    detail = practice.session_detail(1, sid)
    practice.send_turn(db.session.get(User, 1), sid, body=body, request_id=str(uuid4()),
        expected_sequence=detail["messages"][-1]["sequence"], brief_revision=detail["session_brief"]["revision"],
        artifact_revisions={a["artifact_id"]: a["revision"] for a in detail["artifacts"]})


def _save(sid, bodies):
    detail = practice.session_detail(1, sid)
    edits = [{"artifact_id": a["artifact_id"], "base_revision": a["revision"], "language": a["language"],
              "body": bodies[a["artifact_id"]]} for a in detail["artifacts"] if a["artifact_id"] in bodies]
    if edits:
        practice.save_work(db.session.get(User, 1), sid, edits=edits, request_id=str(uuid4()))


def snapshot(document, case):
    """Create an actual saved submission; no generated interviewer calls during setup."""
    current_app.config["LEARNING_AI_ENABLED"] = False
    version = case.get("version", 2)
    item = db.session.get(ContentRevision, (document["exercise_id"], version)).payload
    now, sid = practice._now(), str(uuid4())
    db.session.add(PracticeSession(id=sid, user_id=1, exercise_id=document["exercise_id"], exercise_version=version,
        interaction_style="interviewer", status="active", profile_version=CURRENT_PROFILES["interviewer"],
        created_at=now, updated_at=now))
    db.session.commit()
    _record(sid, "interviewer", "turn", item["content"]["facilitator"]["opening_prompt"])
    _send(sid, case["question"])
    facts = [r["fact"] for r in item["content"]["facilitator"]["hidden_constraints"] if r["id"] in case["disclosures"]]
    if facts:
        turn = _record(sid, "interviewer", "turn", "\n".join(facts))
        _record(sid, "interviewer", "context", data={"revealed": case["disclosures"], "turn_sequence": turn})
    for index in range(case.get("hints_given", 0)):
        _send(sid, "Please give me a hint.")
        turn = _record(sid, "interviewer", "turn", item["content"]["facilitator"]["permitted_hints"][index])
        _record(sid, "interviewer", "assistance", data={"hint_index": index, "turn_sequence": turn})
    if case.get("initial_artifacts"):
        _save(sid, case["initial_artifacts"])
        _send(sid, case["initial_message"])
    bodies = {**document["bases"][case["base"]], **case.get("artifacts", {})}
    _save(sid, bodies)
    if case.get("notes"):
        practice.save_work(db.session.get(User, 1), sid, request_id=str(uuid4()),
                           brief={"base_revision": 0, "entries": case["notes"]})
    _send(sid, case["message"])
    if case.get("continue_recent"):
        _record(sid, "learner", "context", data={"from_sequence": practice._latest_turn(sid)})
    detail = practice.session_detail(1, sid)
    submitted = practice.save_and_submit(db.session.get(User, 1), sid,
        edits=[{"artifact_id": a["artifact_id"], "base_revision": a["revision"], "language": a["language"], "body": a["body"]}
               for a in detail["artifacts"]],
        brief={"base_revision": detail["session_brief"]["revision"], "entries": detail["session_brief"]["entries"]},
        expected_sequence=detail["messages"][-1]["sequence"], request_id=str(uuid4()))
    current_app.config["LEARNING_AI_ENABLED"] = True
    return sid, submitted["submission"]["sequence"]


def total_committed():
    amount = sql_case((LearningAICharge.state == "settled", LearningAICharge.cost_microusd),
                      else_=LearningAICharge.reserved_microusd)
    return int(db.session.scalar(select(func.coalesce(func.sum(amount), 0)).where(LearningAICharge.state != "released")) or 0)


class RecordingProvider:
    def __init__(self, provider):
        self.provider, self.calls = provider, []

    def call(self, body, *, deadline):
        # The production worker already reserved this call. Also enforce the review's
        # all-time cap across rounds/months; unknown outcomes remain reserved.
        if total_committed() > CAP_MICROUSD or db.session.query(LearningAICharge).count() > MAX_CALLS:
            raise ProviderError("evaluation_cap", charged="no")
        started = time.monotonic()
        record = {"request_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(),
                  "request_bytes": interviewer.body_bytes(body)}
        self.calls.append(record)
        try:
            result = self.provider.call(body, deadline=deadline)
            record.update(deepcopy(result))
            return result
        except ProviderError as exc:
            record.update(error=exc.code, charged=exc.charged, usage=exc.usage)
            raise
        finally:
            record["wall_seconds"] = round(time.monotonic() - started, 3)


def run_case(document, case, provider, before_call=lambda record: None):
    sid, sequence = snapshot(document, case)
    queued = feedback_service.request_feedback(db.session.get(User, 1), sid, sequence, request_id=str(uuid4()))
    request_id = queued["request"]["id"]
    record = {"id": case["id"], "version": case.get("version", 2), "session_id": sid,
              "submission_sequence": sequence, "request_id": request_id, "queued": queued["request"],
              "review_should": case["review"]}
    before_call(record)
    recorder = RecordingProvider(provider)
    if request_id:
        practice_worker.run_once(recorder, worker_id="feedback-eval")
    result = feedback_service.detail(1, sid, sequence)
    saved = db.session.get(PracticeFeedback, request_id) if request_id else None
    ids = sorted({i for f in saved.data["findings"] for i in f["misconception_ids"]}) if saved else []
    record.update(calls=recorder.calls, result=result, mapped_ids=ids, checks={
        "completed_and_validated": saved is not None,
        "one_call": len(recorder.calls) == 1,
        "expected_mappings": ids == sorted(case["expect_ids"]),
        "assistance_coverage": bool(saved and saved.data["coverage"]["hints_given"] == case.get("hints_given", 0)),
        "complete_snapshot": bool(saved and saved.data["coverage"]["complete_snapshot"]),
    })
    return record


def charges():
    keys = ("id", "reply_id", "purpose", "provider", "model", "pricing_version", "state", "reserved_microusd",
            "cost_microusd", "input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens")
    return [{key: getattr(row, key) for key in keys} for row in db.session.scalars(select(LearningAICharge).order_by(LearningAICharge.id))]
