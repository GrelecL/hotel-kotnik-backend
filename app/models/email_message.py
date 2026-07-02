import enum
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, Enum as SAEnum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class ParseStatus(str, enum.Enum):
    success = "success"
    failed = "failed"
    manual_review = "manual_review"


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    parse_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus, name="parse_status"),
        nullable=False,
        default=ParseStatus.manual_review,
    )
    parsed_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    imap_uid: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    reservation: Mapped["Reservation | None"] = relationship(
        "Reservation", back_populates="raw_email"
    )
