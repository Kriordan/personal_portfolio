"""Private extraction receipts and reviewed details; existing jobs stay intact."""
from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("accepted_details", sa.JSON(), nullable=True))
    op.create_table("job_extraction",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id")),
        sa.Column("source_revision", sa.Integer()),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("retry_of", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("summary_started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(32)),
        sa.Column("source", sa.JSON()), sa.Column("result", sa.JSON()), sa.Column("metrics", sa.JSON()),
    )
    op.create_index("ix_job_extraction_user_id", "job_extraction", ["user_id"])
    op.create_index("ix_job_extraction_expires_at", "job_extraction", ["expires_at"])


def downgrade():
    op.drop_table("job_extraction")
    op.drop_column("jobs", "accepted_details")
