"""Atomic, repeatable publication of Git-authored curriculum snapshots."""
from datetime import date, datetime, timezone
import hashlib
import json

import click
from flask import current_app
from flask.cli import with_appcontext
from marshmallow import ValidationError
from sqlalchemy import or_, select, text, tuple_
from sqlalchemy.orm import Session

from project.database import db
from project.learning.content_schema import learner_view, load_catalog, validate_catalog
from project.models import ContentRevision, CurriculumItem


class ContentConflict(ValueError):
    """An immutable version or stable identity was reused inconsistently."""


def content_checksum(item, schema_version=1):
    canonical = json.dumps({"schema_version": schema_version, "item": item},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def import_catalog(document, *, dry_run=True, publish=False, reviewed_by=None, reviewed_on=None):
    """Own a separate transaction; never commit unrelated caller/session changes.

    A PostgreSQL transaction lock serializes these rare, operator-triggered catalog
    writes, including concurrent first imports. Ordinary reading/review is unlocked.
    Payloads are insert-only. Omitting an item never deletes it or its history.
    """
    catalog = validate_catalog(document)
    from project.services import learning_service
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    for item in catalog["items"]:
        if item["kind"] == "concept" and learning_service.load_note(notes_dir, item["id"]) is not None:
            raise ValidationError(f"Concept ID is reserved by a legacy note: {item['id']}.")
    if publish:
        if not isinstance(reviewed_by, str) or not reviewed_by.strip() or len(reviewed_by) > 120:
            raise ValidationError("Publication requires the human reviewer's name (up to 120 characters).")
        if type(reviewed_on) is not date or reviewed_on > datetime.now(timezone.utc).date():
            raise ValidationError("Publication requires a human review date no later than today.")
    elif reviewed_by is not None or reviewed_on is not None:
        raise ValidationError("Review attestation is only recorded when publishing.")
    if db.engine.dialect.name != "postgresql":
        raise RuntimeError("Curriculum imports require PostgreSQL; use validate-curriculum for file-only checks.")

    report = {"items": len(catalog["items"]), "inserted": 0, "published": 0, "dry_run": dry_run}
    with Session(db.engine) as session, session.begin():
        # Fixed application namespace + operation ID; released on commit or rollback.
        session.execute(text("SELECT pg_advisory_xact_lock(1427870284, 1)"))
        for item in sorted(catalog["items"], key=lambda entry: entry["id"]):
            identity = session.get(CurriculumItem, item["id"])
            if identity is None:
                identity = CurriculumItem(id=item["id"], kind=item["kind"])
                session.add(identity)
                session.flush()
            elif identity.kind != item["kind"]:
                raise ContentConflict(f"Cannot change the kind of {item['id']}.")

            revision = session.get(ContentRevision, (item["id"], item["version"]))
            checksum = content_checksum(item, catalog["schema_version"])
            if revision is not None and revision.checksum != checksum:
                raise ContentConflict(f"{item['id']} v{item['version']} changed; increment its version.")
            if revision is None:
                revision = ContentRevision(item_id=item["id"], version=item["version"],
                    schema_version=catalog["schema_version"], checksum=checksum,
                    payload=item, imported_at=datetime.now(timezone.utc))
                session.add(revision)
                report["inserted"] += 1
            if publish:
                latest = session.scalar(select(ContentRevision.version).where(
                    ContentRevision.item_id == item["id"], ContentRevision.published_at.is_not(None)
                ).order_by(ContentRevision.version.desc()).limit(1))
                if latest is not None and item["version"] < latest:
                    raise ContentConflict(f"Cannot republish {item['id']} behind published version {latest}.")
                if revision.published_at is None:
                    revision.published_at = datetime.now(timezone.utc)
                    revision.reviewed_by = reviewed_by.strip()
                    revision.reviewed_on = reviewed_on
                    report["published"] += 1
        session.flush()
        if dry_run:
            session.rollback()
    return report


def learner_visibility():
    """Publication by default; the isolated pilot may allow exact approved drafts.

    Only the guarded local entry point sets this allowlist after checking database
    identity and its private approval file. No environment toggle grants access.
    Matching the checksum prevents an approved version from authorizing new text.
    This changes visibility only: learner projections still exclude private material.
    """
    published = ContentRevision.published_at.is_not(None)
    drafts = current_app.config.get("LEARNING_LOCAL_DRAFT_REVISIONS")
    if current_app.config.get("LEARNING_LOCAL_PILOT") and drafts:
        return or_(published, tuple_(ContentRevision.item_id, ContentRevision.version,
                                     ContentRevision.checksum).in_(drafts))
    return published


def published_learner_item(item_id, *, version=None, reveal_answer=False):
    """Read published content or an explicitly approved local draft through the learner projection."""
    query = select(ContentRevision).where(ContentRevision.item_id == item_id,
        learner_visibility())
    if version is not None:
        query = query.where(ContentRevision.version == version)
    revision = db.session.scalar(query.order_by(ContentRevision.version.desc()).limit(1))
    if revision is None:
        return None
    result = learner_view(revision.payload, reveal_answer=reveal_answer)
    result["schema_version"] = revision.schema_version
    if revision.published_at is None:
        result["local_draft"] = True
    return result


def published_concepts():
    """Latest published concepts, with no private exercise snapshots in the result."""
    revisions = db.session.scalars(select(ContentRevision).join(CurriculumItem).where(
        CurriculumItem.kind == "concept", learner_visibility()
    ).order_by(ContentRevision.item_id, ContentRevision.version.desc()))
    latest = {}
    for revision in revisions:
        if revision.item_id not in latest:
            latest[revision.item_id] = learner_view(revision.payload)
            if revision.published_at is None:
                latest[revision.item_id]["local_draft"] = True
    return list(latest.values())


def published_review_question(concept_id, question_id, *, version=None, notes_dir=None, reveal_answer=False):
    """Adapt a public question to the shared scheduler; never load an exercise."""
    from project.services import learning_service
    if notes_dir is None:
        notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    if learning_service.load_note(notes_dir, concept_id) is not None:
        raise learning_service.ConflictError("Concept ID conflicts with a legacy note.")
    question = published_learner_item(question_id, version=version, reveal_answer=reveal_answer)
    if (question is None or question["kind"] != "question"
            or question["content"]["concept_id"] != concept_id):
        raise learning_service.NotFoundError("question not found")
    body = question["content"]
    result = dict(card_id=question["id"], note_id=concept_id, note_title=question["title"],
        prompt=body["prompt"], tags=[], content_version=question["version"],
        remediation_section_id=body["remediation_section_id"])
    if reveal_answer:
        result.update(answer=body["answer"], explanation=body["explanation"])
    return result


def concept_review_queue(concept, *, user_id):
    from project.services.learning_service import due_cards_for_user, progress_map
    from project.services.concept_progress_service import progress
    cards = [published_review_question(concept["id"], question_id)
             for question_id in concept["content"]["review_question_ids"]]
    if progress(user_id, concept["id"]) is None:
        # Preserve already-started cards; discovering a concept creates no new
        # review obligations. Explicit one-off ratings remain supported.
        started = progress_map([card["card_id"] for card in cards], user_id)
        cards = [card for card in cards if card["card_id"] in started]
    return due_cards_for_user(cards, user_id=user_id)


@click.command("validate-curriculum")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
def validate_curriculum(path):
    """Check content, references and Markdown paths without database access."""
    try:
        catalog = load_catalog(path)
    except (ValidationError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Valid catalog: {len(catalog['items'])} items. No database changes.")


@click.command("import-curriculum")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--apply", is_flag=True, help="Commit changes. Omit for a transaction that rolls back.")
@click.option("--publish", is_flag=True, help="Attest human review and publish the entire validated batch.")
@click.option("--reviewed-by", help="Name of the human who reviewed this exact content.")
@click.option("--reviewed-on", type=click.DateTime(formats=["%Y-%m-%d"]))
@with_appcontext
def import_curriculum(path, apply, publish, reviewed_by, reviewed_on):
    """Import immutable revisions; safe dry run by default. Requires migrated PostgreSQL."""
    try:
        report = import_catalog(load_catalog(path), dry_run=not apply, publish=publish,
            reviewed_by=reviewed_by, reviewed_on=reviewed_on.date() if reviewed_on else None)
    except (ValidationError, OSError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(report, sort_keys=True))
