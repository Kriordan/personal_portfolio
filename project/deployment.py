"""Readiness checks and release tasks. Neither starts an AI worker or calls a provider."""
import os
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from flask import current_app
from flask_migrate import upgrade
from sqlalchemy import text

from project.database import db
from project.learning import hosted_pilot
from project.models import ContentRevision, User

ROOT = Path(__file__).resolve().parents[1]


def check_schema():
    config = Config()
    config.set_main_option("script_location", str(ROOT / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if db.session.execute(text("SELECT version_num FROM alembic_version")).scalars().all() != [head]:
        raise RuntimeError("Database schema does not match this release. Run the release migrations before serving.")


def check_hosted_pilot():
    if not current_app.config.get("LEARNING_HOSTED_PILOT"):
        return
    if db.engine.dialect.name != "postgresql":
        raise RuntimeError("The hosted Learning pilot requires PostgreSQL.")
    approval = hosted_pilot.validate_approval(current_app.config.get("LEARNING_HOSTED_APPROVAL"))
    from project.learning.access import allowed
    from project.services.curriculum_service import content_checksum
    user = db.session.get(User, approval["owner_id"], populate_existing=True)
    if not allowed(user):
        raise RuntimeError("The configured hosted owner is missing, changed, or unverified.")
    for item_id, version, checksum in approval["draft_revisions"]:
        revision = db.session.get(ContentRevision, (item_id, version))
        if (revision is None or revision.checksum != checksum
                or content_checksum(revision.payload, revision.schema_version) != checksum):
            raise RuntimeError("The hosted draft packet is missing or differs from its exact approval.")
    if current_app.config.get("LEARNING_AI_ENABLED") and not os.environ.get("LEARNING_OPENAI_API_KEY", "").strip():
        raise RuntimeError("Live Learning requires its dedicated provider key.")


def check_ready():
    try:
        check_schema()
        check_hosted_pilot()
    finally:
        db.session.remove()


def release():
    """Apply additive migrations, then the explicitly approved unpublished packet."""
    upgrade(directory=str(ROOT / "migrations"))
    if current_app.config.get("LEARNING_HOSTED_PILOT"):
        from project.learning.content_schema import load_catalog
        from project.services.curriculum_service import import_catalog
        # Validate before import; this never fabricates a human publication review.
        hosted_pilot.validate_approval(current_app.config.get("LEARNING_HOSTED_APPROVAL"))
        import_catalog(load_catalog(hosted_pilot.CATALOG), dry_run=False)
    check_ready()
