"""Opt-in study and saved reading position, independent of review and practice."""
from datetime import datetime, timezone

from sqlalchemy import select, update

from project.database import db
from project.models import User, UserConceptProgress
from project.services import curriculum_service
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError


def published_concept(concept_id, *, version=None):
    item = curriculum_service.published_learner_item(concept_id, version=version)
    if item is None or item["kind"] != "concept":
        raise NotFoundError("Concept not found.")
    return item


def _iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _view(row):
    if row is None:
        return None
    return dict(concept_id=row.concept_id, enrolled_at=_iso(row.enrolled_at), updated_at=_iso(row.updated_at),
                revision=row.revision, reading_version=row.reading_version, reading_section=row.reading_section)


def progress(user_id, concept_id):
    return _view(db.session.get(UserConceptProgress, (user_id, concept_id)))


def resume_section(concept, saved):
    """Prefer a surviving stable section ID; removed sections fall back to the start."""
    return next((section for section in concept["content"]["sections"]
                 if saved and section["id"] == saved["reading_section"]), None)


def _lock_user(user_id):
    # The parent exists even on first enrollment. Use the existing rating lock
    # order; reads stay unlocked and no scheduler or practice rows are changed.
    if db.engine.dialect.name == "sqlite":
        db.session.execute(update(User).where(User.id == user_id).values(id=User.id))
    else:
        db.session.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()


def _current(user_id, concept_id):
    return db.session.scalar(select(UserConceptProgress).where(
        UserConceptProgress.user_id == user_id, UserConceptProgress.concept_id == concept_id
    ).execution_options(populate_existing=True))


def enroll(user_id, concept_id):
    """Idempotent by (user, concept). Retrying never resets an existing bookmark."""
    try:
        published_concept(concept_id)
        _lock_user(user_id)
        row = _current(user_id, concept_id)
        if row is None:
            now = datetime.now(timezone.utc)
            row = UserConceptProgress(user_id=user_id, concept_id=concept_id,
                                      enrolled_at=now, updated_at=now, revision=1)
            db.session.add(row)
            db.session.flush()
        result = _view(row)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def save_position(user_id, concept_id, *, content_version, section_id, expected_revision, request_id):
    from project.services.learning_service import validate_request_id
    for value in (content_version, expected_revision):
        if type(value) is not int or not 1 <= value < 2147483647:
            raise ValidationError("Invalid content version or progress revision.")
    validate_request_id(request_id)
    if not isinstance(section_id, str) or not 1 <= len(section_id) <= 128:
        raise ValidationError("Invalid section.")
    try:
        concept = published_concept(concept_id, version=content_version)
        if section_id not in {section["id"] for section in concept["content"]["sections"]}:
            raise ValidationError("Section does not belong to this lesson version.")
        _lock_user(user_id)
        row = _current(user_id, concept_id)
        if row is None:
            raise ConflictError("Start learning this concept before saving a reading position.")
        if row.last_request_id == request_id:
            if (row.reading_version, row.reading_section, row.revision - 1) != (
                    content_version, section_id, expected_revision):
                raise ConflictError("This request ID was already used for a different reading position.")
        else:
            if row.revision != expected_revision:
                raise ConflictError("Your reading position changed elsewhere. Reload before saving another position.")
            row.reading_version, row.reading_section = content_version, section_id
            row.last_request_id = request_id
            row.revision += 1
            row.updated_at = datetime.now(timezone.utc)
        result = _view(row)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise
