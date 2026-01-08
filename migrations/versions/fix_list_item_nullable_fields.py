"""Make quantity and notes nullable in list_item

Revision ID: fix_list_item_nullable
Revises: dd2d0ccc81f2
Create Date: 2026-01-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_list_item_nullable'
down_revision = 'dd2d0ccc81f2'
branch_labels = None
depends_on = None


def upgrade():
    # Make quantity and notes nullable
    with op.batch_alter_table('list_item') as batch_op:
        batch_op.alter_column('quantity',
                              existing_type=sa.String(length=32),
                              nullable=True)
        batch_op.alter_column('notes',
                              existing_type=sa.Text(),
                              nullable=True)


def downgrade():
    # Revert to non-nullable (will fail if there are NULL values)
    with op.batch_alter_table('list_item') as batch_op:
        batch_op.alter_column('quantity',
                              existing_type=sa.String(length=32),
                              nullable=False)
        batch_op.alter_column('notes',
                              existing_type=sa.Text(),
                              nullable=False)

