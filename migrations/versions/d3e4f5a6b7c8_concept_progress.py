"""Explicit concept enrollment and revision-checked reading bookmarks."""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade():
    # No enrollment backfill and no changes to existing reviews or practice.
    op.create_table("user_concept_progress",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("concept_id", sa.String(128), sa.ForeignKey("curriculum_item.id"), primary_key=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reading_version", sa.Integer(), nullable=True),
        sa.Column("reading_section", sa.String(128), nullable=True),
        sa.Column("last_request_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["concept_id", "reading_version"],
            ["content_revision.item_id", "content_revision.version"], name="fk_concept_progress_reading"),
        sa.CheckConstraint("revision > 0", name="ck_concept_progress_revision"),
        sa.CheckConstraint(
            "(reading_version IS NULL AND reading_section IS NULL AND last_request_id IS NULL) OR "
            "(reading_version IS NOT NULL AND reading_section IS NOT NULL AND last_request_id IS NOT NULL)",
            name="ck_concept_progress_reading"))


def downgrade():
    op.drop_table("user_concept_progress")
