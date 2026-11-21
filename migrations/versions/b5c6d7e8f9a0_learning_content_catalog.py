"""Add the versioned curriculum without modifying legacy notes or review history."""
from alembic import op
import sqlalchemy as sa

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "curriculum_item",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.CheckConstraint("kind IN ('concept', 'question', 'exercise')", name="ck_curriculum_item_kind"),
    )
    op.create_table(
        "content_revision",
        sa.Column("item_id", sa.String(128), sa.ForeignKey("curriculum_item.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(120)),
        sa.Column("reviewed_on", sa.Date()),
        sa.CheckConstraint("version > 0", name="ck_content_revision_version"),
        sa.CheckConstraint("schema_version > 0", name="ck_content_revision_schema_version"),
        sa.CheckConstraint(
            "(published_at IS NULL AND reviewed_by IS NULL AND reviewed_on IS NULL) OR "
            "(published_at IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_on IS NOT NULL)",
            name="ck_content_revision_review",
        ),
    )


def downgrade():
    op.drop_table("content_revision")
    op.drop_table("curriculum_item")
