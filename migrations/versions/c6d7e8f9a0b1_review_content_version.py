"""Pin curriculum reviews while leaving legacy review records unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("review_log", sa.Column("content_version", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_review_log_content_revision", "review_log", "content_revision",
                          ["card_id", "content_version"], ["item_id", "version"])


def downgrade():
    op.drop_constraint("fk_review_log_content_revision", "review_log", type_="foreignkey")
    op.drop_column("review_log", "content_version")
