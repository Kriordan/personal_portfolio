"""Add invite-only signup fields and site invitations

Revision ID: b7f9c1d2e3f4
Revises: a1b2c3d4e5f6
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7f9c1d2e3f4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Add new user fields
    op.add_column(
        "user",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user",
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "user",
        sa.Column("email_verification_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_user_email_verification_token"),
        "user",
        ["email_verification_token"],
        unique=True,
    )

    # Create site_invitation table
    op.create_table(
        "site_invitation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["invited_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_site_invitation_email"), "site_invitation", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_site_invitation_token"), "site_invitation", ["token"], unique=True
    )

    # Grandfather existing users
    op.execute('UPDATE "user" SET email_verified = TRUE, is_admin = TRUE')

    # Remove server defaults after backfill
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("is_admin", server_default=None)
        batch_op.alter_column("email_verified", server_default=None)


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_email_verification_token"))
        batch_op.drop_column("email_verification_expires_at")
        batch_op.drop_column("email_verification_token")
        batch_op.drop_column("email_verified")
        batch_op.drop_column("is_admin")

    op.drop_index(op.f("ix_site_invitation_token"), table_name="site_invitation")
    op.drop_index(op.f("ix_site_invitation_email"), table_name="site_invitation")
    op.drop_table("site_invitation")
