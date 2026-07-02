from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("room_categories.id"), nullable=False
    )

    category: Mapped["RoomCategory"] = relationship("RoomCategory", back_populates="rooms")
    blocks: Mapped[list["RoomBlock"]] = relationship("RoomBlock", back_populates="room")
    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation", back_populates="assigned_room"
    )
