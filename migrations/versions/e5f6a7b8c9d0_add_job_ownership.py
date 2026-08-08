"""Add per-user ownership to jobwizard jobs

Revision ID: e5f6a7b8c9d0
Revises: 1f2a3b4c5d6e
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "1f2a3b4c5d6e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    # Backfill existing jobs to the earliest admin user, falling back to the
    # earliest user. Jobs predating ownership were created by the site owner.
    op.execute(
        'UPDATE jobs SET user_id = ('
        'SELECT id FROM "user" ORDER BY is_admin DESC, id ASC LIMIT 1'
        ')'
    )
    # If no users exist there is nobody to own the rows; drop them so the
    # NOT NULL constraint can be applied.
    op.execute("DELETE FROM jobs WHERE user_id IS NULL")

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f("ix_jobs_user_id"), ["user_id"], unique=False)
        batch_op.create_foreign_key("fk_jobs_user_id_user", "user", ["user_id"], ["id"])


def downgrade():
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_jobs_user_id_user", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_jobs_user_id"))
        batch_op.drop_column("user_id")
