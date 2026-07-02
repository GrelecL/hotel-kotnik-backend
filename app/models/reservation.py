import enum
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    Integer, String, Date, DateTime, Boolean, Numeric, Text,
    ForeignKey, Enum as SAEnum, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class ReservationSource(str, enum.Enum):
    cubilis = "cubilis"
    booking = "booking"
    direct_guest = "direct_guest"
    walk_in = "walk_in"
    other = "other"


class BoardType(str, enum.Enum):
    none = "none"
    breakfast = "breakfast"
    half_board = "half_board"
    full_board = "full_board"


class ReservationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    unassigned = "unassigned"


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("external_ref", "source", name="uq_reservation_external_ref_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[ReservationSource] = mapped_column(
        SAEnum(ReservationSource, name="reservation_source"), nullable=False
    )
    guest_name: Mapped[str] = mapped_column(String(200), nullable=False)
    checkin: Mapped[date] = mapped_column(Date, nullable=False)
    checkout: Mapped[date] = mapped_column(Date, nullable=False)
    room_category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("room_categories.id"), nullable=True
    )
    assigned_room_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("rooms.id"), nullable=True
    )
    guests_adults: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    guests_children: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    children_ages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    board_type: Mapped[BoardType] = mapped_column(
        SAEnum(BoardType, name="board_type"), nullable=False, default=BoardType.none
    )
    price_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    tourist_tax_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[ReservationStatus] = mapped_column(
        SAEnum(ReservationStatus, name="reservation_status"),
        nullable=False,
        default=ReservationStatus.pending,
    )
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_email_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("email_messages.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    room_category: Mapped["RoomCategory"] = relationship(
        "RoomCategory", back_populates="reservations"
    )
    assigned_room: Mapped["Room"] = relationship("Room", back_populates="reservations")
    raw_email: Mapped["EmailMessage | None"] = relationship("EmailMessage", back_populates="reservation")
    events: Mapped[list["EventLog"]] = relationship("EventLog", back_populates="reservation")
