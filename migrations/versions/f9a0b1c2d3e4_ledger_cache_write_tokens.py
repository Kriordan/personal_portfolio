"""Record cache-write tokens in the Learning AI ledger.

GPT-6 and GPT-6.1 models bill tokens written to the prompt cache at their own rate, and each
charge's cost already includes them. This column lets the token counts explain the cost.
Additive: earlier rows keep NULL, like rows settled without trustworthy usage.
"""
from alembic import op
import sqlalchemy as sa

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("learning_ai_charge", sa.Column("cache_write_tokens", sa.Integer()))


def downgrade():
    op.drop_column("learning_ai_charge", "cache_write_tokens")
