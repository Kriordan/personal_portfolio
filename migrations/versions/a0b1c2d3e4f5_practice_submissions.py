"""Allow idempotent submission receipts; snapshots use existing session records."""
from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None

OPERATIONS = "'start', 'save', 'send', 'pause', 'resume', 'reply'"


def upgrade():
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt",
                               f"operation IN ({OPERATIONS}, 'submit')")


def downgrade():
    # Earlier code cannot replay this operation. Keep snapshots and artifact history.
    op.execute("DELETE FROM practice_receipt WHERE operation = 'submit'")
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt", f"operation IN ({OPERATIONS})")
