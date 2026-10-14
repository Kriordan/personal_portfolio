"""Account-scoped rating receipts and revision-checked review progress.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    duplicate = op.get_bind().execute(sa.text(
        "SELECT 1 FROM review_progress GROUP BY user_id, card_id HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Duplicate learning progress requires review before migration; no history was removed.")
    with op.batch_alter_table("review_progress") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="0"))
        batch.create_unique_constraint("uq_review_progress_user_card", ["user_id", "card_id"])
    op.create_table("review_receipt",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("review_receipt")
    with op.batch_alter_table("review_progress") as batch:
        batch.drop_constraint("uq_review_progress_user_card", type_="unique")
        batch.drop_column("revision")
