"""Add durable AI replies for practice sessions and a content-free spending ledger.

Additive apart from the receipt operation list, which gains 'reply'. Downgrading drops
every AI request, every spending record, and the receipts of reply requests; practice
sessions, their messages, and their artifacts stay.
"""
from alembic import op
import sqlalchemy as sa

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None

# Copied from project/models.py as of this migration.
STATUSES = "'pending', 'running', 'completed', 'failed', 'interrupted', 'cancelled'"
LIVE = "status IN ('pending', 'running')"
OPERATIONS = "'start', 'save', 'send', 'pause', 'resume'"


def upgrade():
    op.add_column("practice_session", sa.Column("profile_version", sa.String(32), nullable=False,
                                                server_default="interviewer-1"))

    op.create_table(
        "ai_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("practice_session_id", sa.String(36),
                  sa.ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_ai_request_session"),
                  nullable=False),
        sa.Column("turn_message_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(32)),
        sa.Column("context_from_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("profile_version", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("selector_model", sa.String(64), nullable=False),
        sa.Column("claim_token", sa.String(64)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("reply_message_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["practice_session_id", "turn_message_id"],
                                ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_ai_request_turn"),
        sa.ForeignKeyConstraint(["practice_session_id", "reply_message_id"],
                                ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_ai_request_reply"),
        sa.CheckConstraint("kind IN ('reply', 'feedback')", name="ck_ai_request_kind"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_ai_request_status"),
        sa.CheckConstraint("context_from_sequence > 0", name="ck_ai_request_context_from"),
    )
    op.create_index("uq_ai_request_live", "ai_request", ["practice_session_id"], unique=True,
                    postgresql_where=sa.text(LIVE), sqlite_where=sa.text(LIVE))
    op.create_index("uq_ai_request_completed_turn", "ai_request", ["turn_message_id"], unique=True,
                    postgresql_where=sa.text("status = 'completed'"), sqlite_where=sa.text("status = 'completed'"))
    op.create_index("ix_ai_request_status_created", "ai_request", ["status", "created_at"])

    op.create_table(
        "learning_ai_charge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", name="fk_learning_ai_charge_user"),
                  nullable=False),
        sa.Column("reply_id", sa.String(36), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("service_tier", sa.String(16), nullable=False),
        sa.Column("pricing_version", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("reserved_microusd", sa.BigInteger(), nullable=False),
        sa.Column("cost_microusd", sa.BigInteger()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("cached_input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("purpose IN ('select', 'reply', 'feedback')", name="ck_learning_ai_charge_purpose"),
        sa.CheckConstraint("state IN ('reserved', 'settled', 'released')", name="ck_learning_ai_charge_state"),
        sa.CheckConstraint("reserved_microusd >= 0 AND (cost_microusd IS NULL OR cost_microusd >= 0)",
                           name="ck_learning_ai_charge_amounts"),
    )
    op.create_index("ix_learning_ai_charge_period", "learning_ai_charge", ["period"])

    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt",
                               f"operation IN ({OPERATIONS}, 'reply')")


def downgrade():
    op.execute("DELETE FROM practice_receipt WHERE operation = 'reply'")
    op.drop_constraint("ck_practice_receipt_operation", "practice_receipt", type_="check")
    op.create_check_constraint("ck_practice_receipt_operation", "practice_receipt", f"operation IN ({OPERATIONS})")
    op.drop_table("learning_ai_charge")
    op.drop_table("ai_request")
    op.drop_column("practice_session", "profile_version")
