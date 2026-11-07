"""Independent, dated self-assessments; no changes to existing progress."""
from alembic import op
import sqlalchemy as sa

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None
DIMENSIONS = ("recognition", "understanding", "application", "judgment")


def upgrade():
    op.create_table("concept_self_assessment",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.String(128), sa.ForeignKey("curriculum_item.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("scale_version", sa.Integer(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        *[sa.Column(name, sa.String(16), nullable=True) for name in DIMENSIONS],
        sa.UniqueConstraint("user_id", "request_id", name="uq_self_assessment_request"),
        sa.ForeignKeyConstraint(["concept_id", "content_version"],
            ["content_revision.item_id", "content_revision.version"], name="fk_self_assessment_content"),
        sa.CheckConstraint("revision > 0 AND scale_version = 1", name="ck_self_assessment_revision"),
        sa.CheckConstraint("kind IN ('checkin', 'clear')", name="ck_self_assessment_kind"),
        sa.CheckConstraint("(kind = 'checkin' AND content_version IS NOT NULL) OR "
                           "(kind = 'clear' AND content_version IS NULL)", name="ck_self_assessment_content"),
        *[sa.CheckConstraint(
            f"((kind = 'clear' OR deleted) AND {name} IS NULL) OR "
            f"(kind = 'checkin' AND NOT deleted AND {name} IS NOT NULL AND "
            f"{name} IN ('not_assessed', 'not_yet', 'with_help', 'without_help'))",
            name=f"ck_self_assessment_{name}") for name in DIMENSIONS])


def downgrade():
    op.drop_table("concept_self_assessment")
