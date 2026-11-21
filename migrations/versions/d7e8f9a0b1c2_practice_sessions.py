"""Add practice sessions: pinned exercises, ordered records, and immutable artifact revisions.

Additive only. Downgrading drops every practice session, artifact revision, message,
citation, and receipt; catalog and review tables are untouched.
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None

# Copied from project/curriculum_terms.py as of this migration.
FORMATS = "'text', 'markdown', 'pseudocode', 'sql', 'typescript', 'python', 'api-definition'"
LANGUAGES = "'text', 'markdown', 'pseudocode', 'sql', 'python', 'typescript', 'json', 'yaml'"
STYLES = "'interviewer', 'coach', 'collaborative', 'reviewer'"


def upgrade():
    op.create_table(
        "practice_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", name="fk_practice_session_user"), nullable=False),
        sa.Column("exercise_id", sa.String(128), nullable=False),
        sa.Column("exercise_version", sa.Integer(), nullable=False),
        sa.Column("interaction_style", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id", "exercise_version"],
                                ["content_revision.item_id", "content_revision.version"],
                                name="fk_practice_session_exercise"),
        sa.CheckConstraint(f"interaction_style IN ({STYLES})", name="ck_practice_session_style"),
        sa.CheckConstraint("status IN ('active', 'paused', 'completed')", name="ck_practice_session_status"),
    )
    op.create_index("ix_practice_session_user_exercise", "practice_session",
                    ["user_id", "exercise_id", "updated_at"])

    op.create_table(
        "artifact_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_session_id", sa.String(36),
                  sa.ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_artifact_revision_session"),
                  nullable=False),
        sa.Column("artifact_id", sa.String(128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("practice_session_id", "artifact_id", "revision", name="uq_artifact_revision_number"),
        sa.UniqueConstraint("practice_session_id", "id", name="uq_artifact_revision_session_id"),
        sa.CheckConstraint("revision > 0", name="ck_artifact_revision_revision"),
        sa.CheckConstraint(f"format IN ({FORMATS})", name="ck_artifact_revision_format"),
        sa.CheckConstraint(f"language IN ({LANGUAGES})", name="ck_artifact_revision_language"),
    )

    op.create_table(
        "session_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_session_id", sa.String(36),
                  sa.ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_session_message_session"),
                  nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("practice_session_id", "sequence", name="uq_session_message_sequence"),
        sa.UniqueConstraint("practice_session_id", "id", name="uq_session_message_session_id"),
        sa.CheckConstraint("sequence > 0", name="ck_session_message_sequence"),
        sa.CheckConstraint("role IN ('learner', 'interviewer', 'system')", name="ck_session_message_role"),
        sa.CheckConstraint("kind IN ('turn', 'brief', 'context', 'submission', 'assistance')",
                           name="ck_session_message_kind"),
        sa.CheckConstraint("modality IN ('text')", name="ck_session_message_modality"),
    )

    op.create_table(
        "session_message_artifact",
        sa.Column("message_id", sa.Integer(), primary_key=True),
        sa.Column("artifact_revision_id", sa.Integer(), primary_key=True),
        sa.Column("practice_session_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["practice_session_id", "message_id"],
                                ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_session_message_artifact_message"),
        sa.ForeignKeyConstraint(["practice_session_id", "artifact_revision_id"],
                                ["artifact_revision.practice_session_id", "artifact_revision.id"],
                                ondelete="CASCADE", name="fk_session_message_artifact_revision"),
    )

    op.create_table(
        "practice_receipt",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", name="fk_practice_receipt_user"),
                  primary_key=True),
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("practice_session_id", sa.String(36),
                  sa.ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_practice_receipt_session"),
                  nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("operation IN ('start', 'save', 'send', 'pause', 'resume')",
                           name="ck_practice_receipt_operation"),
    )
    op.create_index("ix_practice_receipt_practice_session_id", "practice_receipt", ["practice_session_id"])


def downgrade():
    op.drop_table("practice_receipt")
    op.drop_table("session_message_artifact")
    op.drop_table("session_message")
    op.drop_table("artifact_revision")
    op.drop_table("practice_session")
