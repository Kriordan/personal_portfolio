"""Owner-scoped, two-stage suggestions. GET recovery never calls a provider."""
import copy
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import click
from flask.cli import with_appcontext
from sqlalchemy import select

from project.database import db
from project.models import JobExtraction
from project.jobwizard.capture_lock import capture_lock, capture_capacity, NAMESPACE
from project.jobwizard.capture_policy import target_profile
from project.jobwizard.extraction import PARSER_VERSION, PROMPT_VERSION, VALIDATOR_VERSION
from project.jobwizard.extraction_errors import SuggestionError, MESSAGES
from project.services.jobwizard_service import (
    ConflictError, NotFoundError, StaleJobError, ValidationError, _owner_lock,
    get_job_for_user, iso, now, validate_request_id,
)

ACCOUNT_NAMESPACE = NAMESPACE + 2
SUMMARY_NAMESPACE = NAMESPACE + 3


def configured():
    return os.getenv("JOBWIZARD_EXTRACTION_ENABLED") == "1" and bool(os.getenv("BROWSERLESS_API_TOKEN"))


def _run(stage, **payload):
    try:
        result = subprocess.run([sys.executable, "-m", "project.jobwizard.extraction_worker"],
            input=json.dumps(dict(payload, stage=stage, parent_pid=os.getpid())), capture_output=True, text=True,
            timeout=19 if stage == "read" else 11, cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"})
    except subprocess.TimeoutExpired:
        raise SuggestionError("timeout") from None
    if result.returncode == -14:
        raise SuggestionError("timeout")
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise SuggestionError() from None
    if result.returncode or not isinstance(data, dict):
        raise SuggestionError(data.get("error") if isinstance(data, dict) else "failed")
    return data


def _get(user_id, attempt_id):
    validate_request_id(attempt_id)
    attempt = db.session.execute(select(JobExtraction).where(
        JobExtraction.id == attempt_id, JobExtraction.user_id == user_id).execution_options(populate_existing=True)).scalar_one_or_none()
    if not attempt:
        raise NotFoundError()
    if iso(attempt.expires_at) <= iso(now()):
        raise SuggestionError("expired", 410)
    return attempt


def _recover(user_id):
    # Only called while holding the account's process-lifetime lock.
    JobExtraction.query.filter_by(user_id=user_id, status="running").update(
        dict(status="interrupted", error_code="interrupted", finished_at=now()), synchronize_session=False)
    db.session.commit()
    db.session.expire_all()


def serialize(attempt):
    source = attempt.source or {}
    return dict(id=attempt.id, job_id=attempt.job_id, source_revision=attempt.source_revision,
        source_url=attempt.source_url, retry_of=attempt.retry_of, status=attempt.status, stage=attempt.stage,
        created_at=iso(attempt.created_at), fetched_at=iso(attempt.fetched_at), expires_at=iso(attempt.expires_at),
        finished_at=iso(attempt.finished_at), fields=source.get("fields", {}), warnings=source.get("warnings", []),
        result=attempt.result, error_code=attempt.error_code, error_message=MESSAGES.get(attempt.error_code),
        can_summarize=attempt.status == "ready" and bool(os.getenv("OPENAI_API_KEY")) and configured())


def status(*, user_id, attempt_id):
    _get(user_id, attempt_id)  # Ownership before recovery.
    with capture_lock(user_id, ACCOUNT_NAMESPACE) as fence:
        if fence:
            fence()
            _recover(user_id)
        return serialize(_get(user_id, attempt_id))


def _rate(user_id, stage):
    column = JobExtraction.created_at if stage == "read" else JobExtraction.summary_started_at
    limit = 10 if stage == "read" else 20
    if JobExtraction.query.filter(JobExtraction.user_id == user_id, column >= now() - timedelta(hours=1)).count() >= limit:
        raise SuggestionError("rate_limit", 429)


def start(*, user_id, payload):
    allowed = {"request_id", "listing_url", "job_id", "expected_revision", "retry_of"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValidationError()
    attempt_id = validate_request_id(payload.get("request_id"))
    url, job_id, revision, retry = (payload.get(k) for k in ("listing_url", "job_id", "expected_revision", "retry_of"))
    if job_id is not None:
        if type(job_id) is not int or job_id <= 0 or type(revision) is not int or revision < 0:
            raise ValidationError()
        get_job_for_user(user_id=user_id, job_id=job_id)
    elif revision is not None:
        raise ValidationError()
    if not target_profile(url):
        raise SuggestionError("unsupported")
    if retry is not None:
        validate_request_id(retry)
    with capture_lock(user_id, ACCOUNT_NAMESPACE) as fence:
        previous = db.session.get(JobExtraction, attempt_id)
        if previous:
            if (previous.user_id, previous.source_url, previous.job_id, previous.source_revision, previous.retry_of) != (user_id, url, job_id, revision, retry):
                raise ConflictError()
            if fence:
                fence()
                _recover(user_id)
            return serialize(_get(user_id, attempt_id))
        if not fence:
            raise SuggestionError("busy", 429)
        fence()
        _recover(user_id)
        _owner_lock(user_id)
        if job_id is not None and get_job_for_user(user_id=user_id, job_id=job_id).revision != revision:
            raise StaleJobError()
        if not configured():
            raise SuggestionError("unavailable", 503)
        _rate(user_id, "read")
        source, fetched_at = None, None
        if retry:
            parent = _get(user_id, retry)
            if (parent.source_url, parent.job_id, parent.source_revision) != (url, job_id, revision) or parent.status not in {"failed", "interrupted"}:
                raise ConflictError()
            # Explicit retry after a summary failure reuses the original source.
            source, fetched_at = copy.deepcopy(parent.source), parent.fetched_at
        created = now()
        attempt = JobExtraction(id=attempt_id, user_id=user_id, job_id=job_id, source_revision=revision,
            source_url=url, retry_of=retry, status="ready" if source else "running", stage="read",
            created_at=created, expires_at=created + timedelta(hours=24), source=source, fetched_at=fetched_at)
        if retry and source:
            # Retrying must not extend the source's privacy/freshness lifetime.
            attempt.expires_at = parent.expires_at
        db.session.add(attempt)
        fence()
        db.session.commit()
        if not source:
            _execute(user_id, attempt_id, "read", fence)
        return serialize(_get(user_id, attempt_id))


def summarize(*, user_id, attempt_id):
    _get(user_id, attempt_id)
    with capture_lock(user_id, ACCOUNT_NAMESPACE) as fence:
        if not fence:
            return serialize(_get(user_id, attempt_id))
        fence()
        _recover(user_id)
        _owner_lock(user_id)
        attempt = _get(user_id, attempt_id)
        # Same receipt never repeats a provider call, including failed attempts.
        if attempt.status != "ready":
            return serialize(attempt)
        if not configured() or not os.getenv("OPENAI_API_KEY"):
            raise SuggestionError("unavailable", 503)
        _rate(user_id, "summary")
        attempt.status, attempt.stage = "running", "summary"
        attempt.summary_started_at, attempt.error_code = now(), None
        fence()
        db.session.commit()
        _execute(user_id, attempt_id, "summary", fence)
        return serialize(_get(user_id, attempt_id))


def _execute(user_id, attempt_id, stage, fence):
    try:
        attempt = _get(user_id, attempt_id)
        if stage == "read":
            with capture_capacity() as capacity:
                if not capacity:
                    raise SuggestionError("capacity")
                capacity()
                output = _run("read", url=attempt.source_url)
                capacity()
        else:
            # A single model slot independent of the two shared browser slots.
            with capture_lock(0, SUMMARY_NAMESPACE) as capacity:
                if not capacity:
                    raise SuggestionError("capacity")
                capacity()
                output = _run("summary", source=attempt.source, model=os.getenv("JOBWIZARD_SUMMARY_MODEL", "gpt-6-luna"))
                capacity()
        fence()
        _owner_lock(user_id)
        attempt = _get(user_id, attempt_id)
        if attempt.status != "running" or attempt.stage != stage:
            raise ConflictError()
        if stage == "read":
            attempt.source, attempt.fetched_at, attempt.status = output["source"], now(), "ready"
        else:
            attempt.result, attempt.status = output["result"], "complete"
        attempt.finished_at = now()
        attempt.metrics = {**(attempt.metrics or {}), stage: {k: output[k] for k in ("seconds", "usage", "model") if k in output},
                           "parser": PARSER_VERSION, "prompt": PROMPT_VERSION, "validator": VALIDATOR_VERSION}
        fence()
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        fence()  # Lost locks can never publish a success or failure.
        _owner_lock(user_id)
        attempt = _get(user_id, attempt_id)
        if attempt.status == "running":
            attempt.status, attempt.finished_at = "failed", now()
            attempt.error_code = error.code if isinstance(error, SuggestionError) else "failed"
            db.session.commit()


def accept(*, user_id, job, review, original_job_id):
    """Called inside the job mutation/receipt transaction and owner row lock."""
    if not isinstance(review, dict) or set(review) != {"extraction_id", "bullets"}:
        raise ValidationError()
    attempt = _get(user_id, review["extraction_id"])
    if (attempt.status not in {"ready", "complete", "failed", "interrupted"} or not attempt.source
            or attempt.accepted_at or attempt.source_url != job.listing_url or attempt.job_id != original_job_id):
        raise ConflictError()
    if original_job_id is not None and attempt.source_revision != job.revision - 1:
        raise StaleJobError()
    items = review["bullets"]
    suggestions = (attempt.result or {}).get("bullets", [])
    if not isinstance(items, list) or len(items) > 8:
        raise ValidationError()
    bullets, seen = [], set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {"index", "text"} or type(item["index"]) is not int
                or not 0 <= item["index"] < len(suggestions) or item["index"] in seen
                or not isinstance(item["text"], str) or not 0 < len(item["text"].strip()) <= 300):
            raise ValidationError()
        seen.add(item["index"])
        original = suggestions[item["index"]]
        bullets.append({**copy.deepcopy(original), "text": item["text"].strip(), "edited": item["text"].strip() != original["text"]})
    fields = {key: {**copy.deepcopy(value), "edited": getattr(job, key) != value["value"]}
              for key, value in attempt.source.get("fields", {}).items() if key in {"title", "company_name"} and value}
    details = dict(source_url=attempt.source_url, fetched_at=iso(attempt.fetched_at), extraction_id=attempt.id,
        source_hash=attempt.source["source_hash"], versions=attempt.metrics or {}, fields=fields, bullets=bullets,
        partial=bool(attempt.source.get("warnings") or (attempt.result or {}).get("more_details") or attempt.status != "complete"))
    attempt.accepted_at, attempt.status = now(), "accepted"
    attempt.source, attempt.result = None, None
    return details


@click.command("prune-job-extractions")
@with_appcontext
def prune_extractions():
    """Remove expired source and receipts. Job excerpts/receipts remain durable."""
    count = JobExtraction.query.filter(JobExtraction.expires_at <= now()).delete(synchronize_session=False)
    db.session.commit()
    click.echo(f"Removed {count} expired extraction receipts.")
