"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "room_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
    )

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("room_categories.id"), nullable=False),
    )

    op.create_table(
        "room_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("raw_subject", sa.Text(), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "parse_status",
            sa.Enum("success", "failed", "manual_review", name="parse_status"),
            nullable=False,
            server_default="manual_review",
        ),
        sa.Column("parsed_json", postgresql.JSONB(), nullable=True),
        sa.Column("imap_uid", sa.String(100), nullable=True, unique=True),
    )

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_ref", sa.String(200), nullable=True),
        sa.Column(
            "source",
            sa.Enum("cubilis", "booking", "direct_guest", "walk_in", "other", name="reservation_source"),
            nullable=False,
        ),
        sa.Column("guest_name", sa.String(200), nullable=False),
        sa.Column("checkin", sa.Date(), nullable=False),
        sa.Column("checkout", sa.Date(), nullable=False),
        sa.Column("room_category_id", sa.Integer(), sa.ForeignKey("room_categories.id"), nullable=True),
        sa.Column("assigned_room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=True),
        sa.Column("guests_adults", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("guests_children", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("children_ages", postgresql.JSONB(), nullable=True),
        sa.Column(
            "board_type",
            sa.Enum("none", "breakfast", "half_board", "full_board", name="board_type"),
            nullable=False,
            server_default="none",
        ),
        sa.Column("price_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("price_currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("tourist_tax_total", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "cancelled", "unassigned", name="reservation_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_email_id", sa.Integer(), sa.ForeignKey("email_messages.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("external_ref", "source", name="uq_reservation_external_ref_source"),
    )

    op.create_table(
        "events_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id"), nullable=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum("new", "modified", "cancelled", "assigned", "reassigned", "blocked", "unblocked", name="event_type"),
            nullable=False,
        ),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pin_hash", sa.String(255), nullable=True),
        sa.Column("tourist_tax_rate", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("tourist_tax_child_exempt_age", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("tourist_tax_child_discount_pct", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("imap_host", sa.String(255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("imap_user", sa.String(255), nullable=True),
        sa.Column("imap_password_encrypted", sa.Text(), nullable=True),
        sa.Column("pos_printer_name", sa.String(255), nullable=True),
        sa.Column("a4_printer_name", sa.String(255), nullable=True),
    )

    # Seed single admin_settings row
    op.execute("INSERT INTO admin_settings (id) VALUES (1)")

    # Index for fast room availability queries
    op.create_index("ix_reservations_checkin_checkout", "reservations", ["checkin", "checkout"])
    op.create_index("ix_reservations_assigned_room", "reservations", ["assigned_room_id"])
    op.create_index("ix_room_blocks_room_dates", "room_blocks", ["room_id", "date_from", "date_to"])


def downgrade() -> None:
    op.drop_table("events_log")
    op.drop_table("admin_settings")
    op.drop_table("reservations")
    op.drop_table("email_messages")
    op.drop_table("room_blocks")
    op.drop_table("rooms")
    op.drop_table("room_categories")
    op.execute("DROP TYPE IF EXISTS event_type")
    op.execute("DROP TYPE IF EXISTS reservation_status")
    op.execute("DROP TYPE IF EXISTS board_type")
    op.execute("DROP TYPE IF EXISTS reservation_source")
    op.execute("DROP TYPE IF EXISTS parse_status")
