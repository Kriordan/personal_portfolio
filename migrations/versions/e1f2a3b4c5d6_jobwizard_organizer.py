"""Private saved jobs, mutation receipts and optional capture attempts.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("jobs") as batch:
        for name in ("saved_at", "updated_at", "archived_at"):
            batch.add_column(sa.Column(name, sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("job_mutation_receipt",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("job_capture",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(32)),
        sa.Column("object_key", sa.String(200)),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
    )
    op.create_index("ix_job_capture_job_id", "job_capture", ["job_id"])
    op.create_index("ix_job_capture_user_id", "job_capture", ["user_id"])


def downgrade():
    op.drop_table("job_capture")
    op.drop_table("job_mutation_receipt")
    with op.batch_alter_table("jobs") as batch:
        for name in ("revision", "archived_at", "updated_at", "saved_at"):
            batch.drop_column(name)
