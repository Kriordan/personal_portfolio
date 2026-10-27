"""Verified lottery metadata, dated snapshots and independent refresh receipts."""
from alembic import op
import sqlalchemy as sa

revision = "a4b5c6d7e8f9"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("lottery_game_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("game_number", sa.String(16), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.UniqueConstraint("state", "game_number"))
    op.create_table("lottery_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("source_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source", "digest"))
    op.create_index("ix_lottery_snapshot_source", "lottery_snapshot", ["source"])
    op.create_table("lottery_refresh_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.String(240)),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("lottery_snapshot.id", ondelete="SET NULL")),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("scheduled", sa.Boolean(), nullable=False),
        sa.Column("retry_not_before", sa.DateTime(timezone=True)))
    op.create_index("ix_lottery_refresh_run_source", "lottery_refresh_run", ["source"])


def downgrade():
    op.drop_table("lottery_refresh_run")
    op.drop_table("lottery_snapshot")
    op.drop_table("lottery_game_metadata")
