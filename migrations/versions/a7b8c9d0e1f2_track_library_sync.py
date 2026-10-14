"""Track Library sync completion and YouTube playlist order.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "library_sync_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("summary", sa.JSON()),
        sa.Column("error", sa.String(255)),
    )
    op.create_index("ix_library_sync_run_status", "library_sync_run", ["status"])
    op.create_index("ix_library_sync_run_started_at", "library_sync_run", ["started_at"])
    op.add_column("video", sa.Column("position", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("video", "position")
    op.drop_table("library_sync_run")
