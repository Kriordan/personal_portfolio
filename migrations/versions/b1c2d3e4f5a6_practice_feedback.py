"""Persist validated snapshot feedback using the existing AI request/ledger lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None
OPERATIONS = "'start', 'save', 'send', 'pause', 'resume', 'reply', 'submit'"


def upgrade():
    op.create_unique_constraint("uq_ai_request_session_id", "ai_request", ["practice_session_id", "id"])
    op.create_table("practice_feedback",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("practice_session_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["practice_session_id", "request_id"], ["ai_request.practice_session_id", "ai_request.id"],
                                ondelete="CASCADE", name="fk_practice_feedback_request"),
        sa.ForeignKeyConstraint(["practice_session_id", "submission_id"], ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_practice_feedback_submission"),
        sa.UniqueConstraint("submission_id", name="uq_practice_feedback_submission"))
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt", f"operation IN ({OPERATIONS}, 'feedback')")


def downgrade():
    op.drop_table("practice_feedback")
    op.execute("DELETE FROM practice_receipt WHERE operation = 'feedback'")
    op.execute("DELETE FROM ai_request WHERE kind = 'feedback'")
    op.drop_constraint("uq_ai_request_session_id", "ai_request", type_="unique")
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt", f"operation IN ({OPERATIONS})")
