"""Owner-authored snapshots with explicit saves, history, and deletion.

No enrollment, scheduler, practice, feedback or AI mutation belongs here.
The existing user row serializes first saves as well as later writes; a separate
revision sequence prevents reading autosaves from making a check-in stale.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update

from project.database import db
from project.learning.self_assessment import DIMENSIONS, RATINGS, SCALE_VERSION
from project.models import ConceptSelfAssessment, CurriculumItem
from project.services import concept_progress_service as progress
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError

FIELDS = tuple(d[0] for d in DIMENSIONS)
VALUES = frozenset(r[0] for r in RATINGS)
PAGE_SIZE = 10
MAX_INT = 2147483647


class AssessmentConflict(ConflictError):
    def __init__(self, revision, current):
        super().__init__("A newer self-assessment change was saved. Compare it with your choices before saving a new check-in.")
        self.revision, self.current = revision, current


def _dto(row):
    if row is None or row.kind == "clear" or row.deleted:
        return None
    return dict(revision=row.revision, content_version=row.content_version, scale_version=row.scale_version,
                created_at=progress._iso(row.created_at), ratings={key: getattr(row, key) for key in FIELDS})


def _owned(user_id, concept_id):
    return select(ConceptSelfAssessment).where(ConceptSelfAssessment.user_id == user_id,
                                               ConceptSelfAssessment.concept_id == concept_id)


def _latest(user_id, concept_id):
    return db.session.scalar(_owned(user_id, concept_id).order_by(ConceptSelfAssessment.revision.desc()).limit(1)
                             .execution_options(populate_existing=True))


def concept_for_reader(user_id, concept_id):
    """Existing personal history stays readable/removable if publication is withdrawn."""
    try:
        return progress.published_concept(concept_id)
    except NotFoundError:
        identity = db.session.get(CurriculumItem, concept_id)
        if identity is None or identity.kind != "concept" or _latest(user_id, concept_id) is None:
            raise
        return None


def history(user_id, concept_id, *, before=None):
    if before is not None and (type(before) is not int or not 1 <= before <= MAX_INT):
        raise ValidationError("Invalid history cursor.")
    concept_for_reader(user_id, concept_id)
    latest = _latest(user_id, concept_id)
    query = _owned(user_id, concept_id).where(ConceptSelfAssessment.kind == "checkin",
                                               ConceptSelfAssessment.deleted.is_(False))
    if before is not None:
        query = query.where(ConceptSelfAssessment.revision < before)
    rows = list(db.session.scalars(query.order_by(ConceptSelfAssessment.revision.desc()).limit(PAGE_SIZE + 1)))
    return dict(concept_id=concept_id, revision=latest.revision if latest else 0, current=_dto(latest),
                entries=[_dto(row) for row in rows[:PAGE_SIZE]],
                next_before=rows[PAGE_SIZE - 1].revision if len(rows) > PAGE_SIZE else None)


def _validate_request(expected_revision, request_id):
    from project.services.learning_service import validate_request_id
    validate_request_id(request_id)
    if type(expected_revision) is not int or not 0 <= expected_revision < MAX_INT:
        raise ValidationError("Invalid self-assessment revision.")


def _replay(user_id, request_id):
    return db.session.scalar(select(ConceptSelfAssessment).where(
        ConceptSelfAssessment.user_id == user_id, ConceptSelfAssessment.request_id == request_id)
        .execution_options(populate_existing=True))


def _check_current(user_id, concept_id, expected_revision):
    latest = _latest(user_id, concept_id)
    revision = latest.revision if latest else 0
    if revision != expected_revision:
        raise AssessmentConflict(revision, _dto(latest))


def save(user_id, concept_id, *, content_version, ratings, expected_revision, request_id):
    _validate_request(expected_revision, request_id)
    if type(content_version) is not int or not 1 <= content_version <= MAX_INT:
        raise ValidationError("Invalid lesson version.")
    if (not isinstance(ratings, dict) or set(ratings) != set(FIELDS)
            or any(not isinstance(value, str) or value not in VALUES for value in ratings.values())):
        raise ValidationError("Choose a listed response for each area, or leave it Not assessed.")
    try:
        progress._lock_user(user_id)
        replay = _replay(user_id, request_id)
        if replay is not None:
            if (replay.concept_id != concept_id or replay.kind != "checkin" or replay.deleted
                    or replay.revision != expected_revision + 1 or replay.content_version != content_version
                    or any(getattr(replay, key) != ratings[key] for key in FIELDS)):
                raise ConflictError("This request ID belongs to a different or deleted check-in.")
            result = _dto(replay)
        else:
            progress.published_concept(concept_id, version=content_version)
            _check_current(user_id, concept_id, expected_revision)
            row = ConceptSelfAssessment(user_id=user_id, concept_id=concept_id, revision=expected_revision + 1,
                request_id=request_id, kind="checkin", scale_version=SCALE_VERSION, content_version=content_version,
                created_at=datetime.now(timezone.utc), deleted=False, **ratings)
            db.session.add(row)
            result = _dto(row)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def clear_history(user_id, concept_id, *, expected_revision, request_id):
    """Remove ratings, retain replay fencing, and never erase newer work on retry."""
    _validate_request(expected_revision, request_id)
    try:
        progress._lock_user(user_id)
        replay = _replay(user_id, request_id)
        if replay is not None:
            if (replay.concept_id != concept_id or replay.kind != "clear"
                    or replay.revision != expected_revision + 1):
                raise ConflictError("This request ID belongs to a different operation.")
            revision = replay.revision
        else:
            concept_for_reader(user_id, concept_id)
            _check_current(user_id, concept_id, expected_revision)
            db.session.execute(update(ConceptSelfAssessment).where(
                ConceptSelfAssessment.user_id == user_id, ConceptSelfAssessment.concept_id == concept_id,
                ConceptSelfAssessment.kind == "checkin").values(deleted=True, **{key: None for key in FIELDS}))
            revision = expected_revision + 1
            db.session.add(ConceptSelfAssessment(user_id=user_id, concept_id=concept_id, revision=revision,
                request_id=request_id, kind="clear", scale_version=SCALE_VERSION, created_at=datetime.now(timezone.utc),
                deleted=False))
        db.session.commit()
        return dict(revision=revision, cleared_through=revision - 1)
    except Exception:
        db.session.rollback()
        raise
