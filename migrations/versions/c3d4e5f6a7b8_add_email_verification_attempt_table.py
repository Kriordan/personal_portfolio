"""Add email verification attempt table

Revision ID: c3d4e5f6a7b8
Revises: b7f9c1d2e3f4
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b7f9c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_verification_attempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("email_verification_attempt") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_email_verification_attempt_email"),
            ["email"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("email_verification_attempt") as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_verification_attempt_email"))

    op.drop_table("email_verification_attempt")
