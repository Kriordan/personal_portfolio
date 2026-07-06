"""Business logic shared by jobwizard web and API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from project.database import db
from project.models import Job


class JobwizardServiceError(Exception):
    """Base jobwizard service exception."""


class NotFoundError(JobwizardServiceError):
    """Raised when a requested job does not exist."""


class ValidationError(JobwizardServiceError):
    """Raised when service input fails validation."""


def list_jobs() -> list[Job]:
    """Return all jobs."""
    return db.session.execute(db.select(Job)).scalars().all()


def get_job(job_id: int) -> Job:
    """Return a job by ID, raising if not found."""
    job = db.session.get(Job, job_id)
    if job is None:
        raise NotFoundError("job not found")
    return job


def create_job(
    *,
    title: str,
    company_name: str,
    listing_url: str,
    posted_date: datetime | None = None,
) -> Job:
    """Create a job, render its listing screenshot, and persist it."""
    cleaned_title = (title or "").strip()
    cleaned_company_name = (company_name or "").strip()
    cleaned_listing_url = (listing_url or "").strip()
    if not cleaned_title or not cleaned_company_name or not cleaned_listing_url:
        raise ValidationError("title, company_name, and listing_url are required")

    job = Job(
        title=cleaned_title,
        company_name=cleaned_company_name,
        listing_url=cleaned_listing_url,
        posted_date=posted_date or datetime.now(timezone.utc),
    )
    job.render_screenshot()
    db.session.add(job)
    db.session.commit()
    return job
