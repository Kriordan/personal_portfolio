"""Channel-bound watched workflow, confirmed membership and move receipts.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("youtube_connection", sa.Column("granted_scopes", sa.JSON()))
    op.add_column("youtube_connection", sa.Column("channel_id", sa.String(255)))
    op.create_table("library_workflow",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(36), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("source_playlist_id", sa.String(), sa.ForeignKey("playlist.id"), nullable=False),
        sa.Column("destination_playlist_id", sa.String(), sa.ForeignKey("playlist.id"), nullable=False),
        sa.Column("membership_checked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="ck_library_workflow_singleton"),
    )
    op.create_table("library_watched_membership",
        sa.Column("video_url_id", sa.String(255), primary_key=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("library_move",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        *[sa.Column(name, sa.String(255), nullable=False) for name in (
            "channel_id", "source_playlist_id", "destination_playlist_id", "source_entry_id",
            "video_url_id", "video_title", "source_title", "destination_title")],
        sa.Column("destination_entry_id", sa.String(255)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("removal_request_id", sa.String(36)),
        sa.Column("error", sa.String(255)),
    )
    for name in ("owner_id", "source_entry_id", "status"):
        op.create_index(f"ix_library_move_{name}", "library_move", [name])


def downgrade():
    op.drop_table("library_move")
    op.drop_table("library_watched_membership")
    op.drop_table("library_workflow")
    op.drop_column("youtube_connection", "channel_id")
    op.drop_column("youtube_connection", "granted_scopes")
