from datetime import date
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.reservation import Reservation, ReservationStatus


async def find_available_room(
    db: AsyncSession,
    category_id: int,
    checkin: date,
    checkout: date,
    exclude_reservation_id: int | None = None,
) -> Room | None:
    """First-fit: returns first room of given category free for the date range."""

    # Rooms occupied by active reservations overlapping [checkin, checkout)
    occupied_by_reservation = (
        select(Reservation.assigned_room_id)
        .where(
            and_(
                Reservation.assigned_room_id.isnot(None),
                Reservation.status.notin_(
                    [ReservationStatus.cancelled]
                ),
                Reservation.checkin < checkout,
                Reservation.checkout > checkin,
                *(
                    [Reservation.id != exclude_reservation_id]
                    if exclude_reservation_id
                    else []
                ),
            )
        )
    )

    # Rooms blocked for the date range
    occupied_by_block = (
        select(RoomBlock.room_id)
        .where(
            and_(
                RoomBlock.date_from < checkout,
                RoomBlock.date_to > checkin,
            )
        )
    )

    result = await db.execute(
        select(Room)
        .where(
            and_(
                Room.category_id == category_id,
                Room.id.notin_(occupied_by_reservation),
                Room.id.notin_(occupied_by_block),
            )
        )
        .order_by(Room.floor, Room.number)
        .limit(1)
    )
    return result.scalar_one_or_none()
