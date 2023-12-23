"""Add image_url to gift

Revision ID: cdabbdd159d3
Revises: 8ae27db58cde
Create Date: 2023-12-13 21:11:09.787908

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cdabbdd159d3'
down_revision = '8ae27db58cde'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('gift', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_url', sa.String(length=140), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('gift', schema=None) as batch_op:
        batch_op.drop_column('image_url')

    # ### end Alembic commands ###
