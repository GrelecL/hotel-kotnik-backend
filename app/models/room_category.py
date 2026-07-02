from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class RoomCategory(Base):
    __tablename__ = "room_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="category")
    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation", back_populates="room_category"
    )
