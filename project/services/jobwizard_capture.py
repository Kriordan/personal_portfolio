"""Durable optional captures; authorization precedes status or image delivery."""
import json
import os
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from project.database import db
from project.jobwizard.capture_lock import capture_lock
from project.jobwizard.capture_worker import bucket, s3_client
from project.models import Job, JobCapture
from project.services.jobwizard_service import (
    ConflictError, StaleJobError, ValidationError, get_job_for_user, iso, now, validate_request_id,
)

TTL = 900


def configured():
    return bool(os.getenv("APILEAP_ACCESS_KEY") and bucket())


def image_origins():
    from project.jobwizard.capture_worker import region
    name = bucket()
    return [f"https://{name}.s3.{region()}.amazonaws.com", f"https://{name}.s3.amazonaws.com"] if name else []


def _run_capture(url, key):
    completed = subprocess.run([sys.executable, "-m", "project.jobwizard.capture_worker"],
        input=json.dumps({"url": url, "key": key}), capture_output=True, text=True, timeout=22,
        cwd=Path(__file__).resolve().parents[2], env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"})
    if completed.returncode:
        raise RuntimeError("capture failed")
    result = json.loads(completed.stdout)
    if (result.get("object_key") != key or type(result.get("width")) is not int
            or type(result.get("height")) is not int or not 0 < result["width"] * result["height"] <= 24_000_000):
        raise RuntimeError("invalid artifact")
    return result


def _recover(job_id):
    JobCapture.query.filter_by(job_id=job_id, status="running").update({
        "status": "interrupted", "error_code": "interrupted", "finished_at": now(),
    }, synchronize_session=False)
    db.session.commit()
    db.session.expire_all()


def _serialize(attempt):
    if not attempt:
        return None
    return dict(id=attempt.id, status=attempt.status, started_at=iso(attempt.started_at),
                finished_at=iso(attempt.finished_at), error_code=attempt.error_code)


def _snapshot(job, requested=None):
    base = JobCapture.query.filter_by(job_id=job.id, user_id=job.user_id)
    latest = base.order_by(JobCapture.started_at.desc(), JobCapture.id.desc()).first()
    available = base.filter_by(status="succeeded").order_by(JobCapture.finished_at.desc(), JobCapture.id.desc()).first()
    image = None
    if available and re.fullmatch(r"j/[a-f0-9]{32}\.png", available.object_key or "") and bucket():
        try:
            url = s3_client().generate_presigned_url("get_object", Params={"Bucket": bucket(),
                "Key": available.object_key, "ResponseCacheControl": "private, no-store"}, ExpiresIn=TTL)
            image = dict(url=url, expires_at=iso(now() + timedelta(seconds=TTL)), width=available.width,
                height=available.height, captured_at=iso(available.finished_at), outdated=available.source_url != job.listing_url)
        except Exception:
            # Metadata remains readable when signing is unavailable. Never log credentials.
            image = None
    attempt = base.filter_by(id=requested).first() if requested else None
    return dict(latest=_serialize(latest), requested=_serialize(attempt), image=image,
                legacy_unavailable=bool(job.listing_image and not available), configured=configured())


def capture_status(*, user_id, job_id, request_id=None):
    job = get_job_for_user(user_id=user_id, job_id=job_id)
    if request_id:
        validate_request_id(request_id)
    with capture_lock(job_id) as fence:
        if fence:
            fence()
            _recover(job_id)
        job = get_job_for_user(user_id=user_id, job_id=job_id)
        result = _snapshot(job, request_id)
        result["busy"] = fence is None and bool(result["latest"] and result["latest"]["status"] == "running")
        return result


def capture_job(*, user_id, job_id, payload):
    if not isinstance(payload, dict) or set(payload) != {"request_id", "expected_revision"}:
        raise ValidationError()
    request_id = validate_request_id(payload["request_id"])
    revision = payload["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise ValidationError()
    job = get_job_for_user(user_id=user_id, job_id=job_id)
    with capture_lock(job_id) as fence:
        if not fence:
            return capture_status_without_lock(job, request_id)
        fence()
        _recover(job_id)
        previous = db.session.get(JobCapture, request_id)
        if previous:
            if previous.user_id != user_id or previous.job_id != job_id or previous.source_revision != revision:
                raise ConflictError()
            return _snapshot(job, request_id)
        job = get_job_for_user(user_id=user_id, job_id=job_id)
        if job.revision != revision:
            raise StaleJobError()
        if not configured():
            return {**_snapshot(job), "unavailable": True}
        attempt = JobCapture(id=request_id, user_id=user_id, job_id=job_id,
            source_url=job.listing_url, source_revision=revision, status="running", started_at=now())
        db.session.add(attempt)
        fence()
        db.session.commit()
        try:
            artifact = _run_capture(attempt.source_url, f"j/{uuid4().hex}.png")
            fence()
            # Preserve the original source; a later URL edit is represented as outdated.
            job = get_job_for_user(user_id=user_id, job_id=job_id)
            attempt = db.session.get(JobCapture, request_id)
            attempt.status = "succeeded"
            attempt.object_key = artifact["object_key"]
            attempt.width, attempt.height = artifact["width"], artifact["height"]
            attempt.finished_at = now()
            fence()
            db.session.commit()
        except Exception:
            db.session.rollback()
            fence()  # A lost lock must never be reacquired or used to publish a result.
            attempt = db.session.get(JobCapture, request_id)
            attempt.status = "failed"
            attempt.error_code = "capture_failed"
            attempt.finished_at = now()
            db.session.commit()
        return _snapshot(get_job_for_user(user_id=user_id, job_id=job_id), request_id)


def capture_status_without_lock(job, request_id):
    return {**_snapshot(job, request_id), "busy": True}
