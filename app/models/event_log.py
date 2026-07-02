import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class EventType(str, enum.Enum):
    new = "new"
    modified = "modified"
    cancelled = "cancelled"
    assigned = "assigned"
    reassigned = "reassigned"
    blocked = "blocked"
    unblocked = "unblocked"


class EventLog(Base):
    __tablename__ = "events_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reservation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("reservations.id"), nullable=True
    )
    room_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("rooms.id"), nullable=True
    )
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="event_type"), nullable=False
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="events")
