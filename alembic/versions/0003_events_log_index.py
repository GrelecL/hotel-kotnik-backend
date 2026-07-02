"""Add index on events_log.reservation_id for fast audit log queries

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_events_log_reservation_id", "events_log", ["reservation_id"])
    op.create_index("ix_events_log_created_at", "events_log", ["created_at"])
    op.create_index("ix_email_messages_received_at", "email_messages", ["received_at"])
    op.create_index("ix_email_messages_parse_status", "email_messages", ["parse_status"])


def downgrade() -> None:
    op.drop_index("ix_events_log_reservation_id", "events_log")
    op.drop_index("ix_events_log_created_at", "events_log")
    op.drop_index("ix_email_messages_received_at", "email_messages")
    op.drop_index("ix_email_messages_parse_status", "email_messages")
