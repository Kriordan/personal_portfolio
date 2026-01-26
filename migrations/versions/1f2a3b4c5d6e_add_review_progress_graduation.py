"""Add review progress graduation fields

Revision ID: 1f2a3b4c5d6e
Revises: 01b6b2a3c6ef
Create Date: 2026-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f2a3b4c5d6e"
down_revision = "01b6b2a3c6ef"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("review_progress", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_suspended",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column("graduated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.alter_column("is_suspended", server_default=None)


def downgrade():
    with op.batch_alter_table("review_progress", schema=None) as batch_op:
        batch_op.drop_column("graduated_at")
        batch_op.drop_column("is_suspended")
