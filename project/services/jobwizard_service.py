"""Owner-scoped saved jobs. Text saves never contact screenshot providers."""
from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select, update

from project.database import db
from project.models import Job, JobMutationReceipt, User


class JobwizardServiceError(Exception):
    pass


class NotFoundError(JobwizardServiceError):
    pass


class ValidationError(JobwizardServiceError):
    def __init__(self, message="invalid job", *, fields=None):
        super().__init__(message)
        self.fields = fields or {}


class ConflictError(JobwizardServiceError):
    pass


class StaleJobError(ConflictError):
    pass


def now():
    return datetime.now(timezone.utc)


def iso(value):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat() if value else None


def safe_listing_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048 or re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return False
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.port == 0):
            return False
        host = parsed.hostname.rstrip(".")
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            labels = host.encode("idna").decode("ascii").split(".")
            return all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label) for label in labels)
    except (ValueError, UnicodeError):
        return False


def validate_request_id(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("invalid request ID") from None
    return value


def job_fields(payload, *, existing=None):
    errors, cleaned = {}, {}
    for key, maximum in (("title", 200), ("company_name", 200), ("listing_url", 2048)):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors[key] = "required"
            continue
        cleaned[key] = value.strip()
        # Historical oversized values can survive an unrelated edit, never truncation.
        unchanged = existing is not None and value == getattr(existing, key)
        if len(cleaned[key]) > maximum and not unchanged:
            errors[key] = "too_long"
        if key == "listing_url" and not unchanged and not safe_listing_url(cleaned[key]):
            errors[key] = "invalid_url"
    if errors:
        raise ValidationError(fields=errors)
    return cleaned


def serialize_job(job, *, detail=True):
    result = {
        "id": job.id, "title": job.title, "company_name": job.company_name,
        "listing_url": job.listing_url, "listing_image": job.listing_image or "",
        "posted_date": iso(job.posted_date), "user_id": job.user_id,
        "saved_at": iso(job.saved_at), "updated_at": iso(job.updated_at),
        "archived_at": iso(job.archived_at), "revision": job.revision,
        "can_open_listing": safe_listing_url(job.listing_url),
    }
    if detail:
        result["accepted_details"] = ({**job.accepted_details,
            "outdated": job.accepted_details["source_url"] != job.listing_url} if job.accepted_details else None)
    return result


def list_jobs_for_user(user_id):
    return db.session.execute(select(Job).where(Job.user_id == user_id).order_by(Job.id.desc())).scalars().all()


def get_job_for_user(*, user_id, job_id):
    job = db.session.execute(select(Job).where(Job.id == job_id, Job.user_id == user_id).execution_options(populate_existing=True)).scalar_one_or_none()
    if job is None:
        raise NotFoundError()
    return job


def mutation_receipt(user_id, request_id):
    validate_request_id(request_id)
    receipt = db.session.get(JobMutationReceipt, (user_id, request_id))
    return receipt.response if receipt else None


def _owner_lock(user_id):
    if db.session.get_bind().dialect.name == "sqlite":
        db.session.execute(update(User).where(User.id == user_id).values(id=User.id))
    else:
        db.session.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()


def mutate_job(*, user_id, payload, job_id=None, posted_date=None):
    """Serialize an owner's writes; commit the result and receipt in one transaction."""
    if not isinstance(payload, dict):
        raise ValidationError()
    allowed = {"request_id", "title", "company_name", "listing_url", "reviewed_details"}
    if job_id is not None:
        allowed |= {"expected_revision", "archived"}
    if set(payload) - allowed:
        raise ValidationError()
    request_id = payload.get("request_id")
    if request_id is not None:
        validate_request_id(request_id)
    expected = payload.get("expected_revision")
    if job_id is not None and (type(expected) is not int or not 0 <= expected <= 2_147_483_647):
        raise ValidationError()
    frozen = {"job_id": job_id, "input": {key: value for key, value in payload.items() if key != "request_id"}}
    try:
        _owner_lock(user_id)
        if request_id:
            receipt = db.session.get(JobMutationReceipt, (user_id, request_id))
            if receipt:
                if receipt.payload != frozen:
                    raise ConflictError()
                result = receipt.response
                db.session.commit()
                return result
        if job_id is None:
            values = job_fields(payload)
            job = Job(**values, user_id=user_id, posted_date=posted_date or now())
            job.saved_at = now()
            job.updated_at = job.saved_at
            job.revision = 0
            db.session.add(job)
            db.session.flush()
        else:
            job = get_job_for_user(user_id=user_id, job_id=job_id)
            if job.revision != expected:
                raise StaleJobError()
            fields = {key: payload[key] for key in ("title", "company_name", "listing_url") if key in payload}
            if fields:
                complete = {key: fields.get(key, getattr(job, key)) for key in ("title", "company_name", "listing_url")}
                values = job_fields(complete, existing=job)
            else:
                values = {}
            if "archived" in payload:
                if type(payload["archived"]) is not bool:
                    raise ValidationError()
                values["archived_at"] = (job.archived_at or now()) if payload["archived"] else None
            if not values and "reviewed_details" not in payload:
                raise ValidationError()
            values.update(revision=expected + 1, updated_at=now())
            changed = db.session.execute(update(Job).where(Job.id == job.id, Job.user_id == user_id, Job.revision == expected).values(**values))
            if changed.rowcount != 1:
                raise StaleJobError()
            db.session.refresh(job)
        if "reviewed_details" in payload:
            from project.services.jobwizard_extraction import accept
            job.accepted_details = accept(user_id=user_id, job=job,
                review=payload["reviewed_details"], original_job_id=job_id)
        result = {"job": serialize_job(job), "request_id": request_id}
        if request_id:
            db.session.add(JobMutationReceipt(user_id=user_id, request_id=request_id,
                payload=frozen, response=result, created_at=now()))
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def create_job_for_user(*, user_id, title, company_name, listing_url, posted_date=None):
    result = mutate_job(user_id=user_id, payload=dict(title=title, company_name=company_name, listing_url=listing_url), posted_date=posted_date)
    return get_job_for_user(user_id=user_id, job_id=result["job"]["id"])
