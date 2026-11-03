"""Keep learner responses separate from immutable generated feedback."""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None
OPERATIONS = "'start', 'save', 'send', 'pause', 'resume', 'reply', 'submit', 'feedback'"


def upgrade():
    op.create_table("practice_feedback_annotation",
        sa.Column("feedback_request_id", sa.String(36), primary_key=True),
        sa.Column("finding_id", sa.String(16), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feedback_request_id"], ["practice_feedback.request_id"],
                                ondelete="CASCADE", name="fk_feedback_annotation_feedback"),
        sa.CheckConstraint("decision IN ('unreviewed', 'agree', 'disagree')", name="ck_feedback_annotation_decision"),
        sa.CheckConstraint("revision > 0", name="ck_feedback_annotation_revision"),
        sa.CheckConstraint("length(note) <= 2000", name="ck_feedback_annotation_note"))
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt", f"operation IN ({OPERATIONS}, 'annotate')")


def downgrade():
    op.drop_table("practice_feedback_annotation")
    op.execute("DELETE FROM practice_receipt WHERE operation = 'annotate'")
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt", f"operation IN ({OPERATIONS})")
