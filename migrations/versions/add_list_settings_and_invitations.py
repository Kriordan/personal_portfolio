"""Add list settings and invitations

Revision ID: a1b2c3d4e5f6
Revises: 6ea635fe0a53
Create Date: 2026-01-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '6ea635fe0a53'
branch_labels = None
depends_on = None


def upgrade():
    # Add completed_display_mode column to custom_list
    op.add_column(
        'custom_list',
        sa.Column('completed_display_mode', sa.String(32), nullable=True, server_default='category_section')
    )
    
    # Add created_at and updated_at columns to custom_list
    op.add_column(
        'custom_list',
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'custom_list',
        sa.Column('updated_at', sa.DateTime(), nullable=True)
    )

    # Create list_invitation table
    op.create_table(
        'list_invitation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(120), nullable=False),
        sa.Column('list_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['list_id'], ['custom_list.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for list_invitation
    op.create_index(op.f('ix_list_invitation_email'), 'list_invitation', ['email'], unique=False)
    op.create_index(op.f('ix_list_invitation_token'), 'list_invitation', ['token'], unique=True)


def downgrade():
    # Drop list_invitation table and indexes
    op.drop_index(op.f('ix_list_invitation_token'), table_name='list_invitation')
    op.drop_index(op.f('ix_list_invitation_email'), table_name='list_invitation')
    op.drop_table('list_invitation')
    
    # Remove columns from custom_list
    op.drop_column('custom_list', 'updated_at')
    op.drop_column('custom_list', 'created_at')
    op.drop_column('custom_list', 'completed_display_mode')

