"""Personal Library playlist pins.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "library_pin",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("playlist_id", sa.String(), sa.ForeignKey("playlist.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("library_pin")
