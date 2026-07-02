from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.room_category import RoomCategory
from app.models.reservation import Reservation, ReservationStatus
from app.schemas.plahta import BlockBar, PlahataResponse, PlahataRow, ReservationBar

router = APIRouter(prefix="/plahta", tags=["plahta"])


@router.get("", response_model=PlahataResponse)
async def get_plahta(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
):
    rooms_result = await db.execute(
        select(Room).order_by(Room.floor, Room.number)
    )
    rooms = rooms_result.scalars().all()

    category_ids = {r.category_id for r in rooms}
    cats_result = await db.execute(
        select(RoomCategory).where(RoomCategory.id.in_(category_ids))
    )
    cats = {c.id: c for c in cats_result.scalars().all()}

    reservations_result = await db.execute(
        select(Reservation).where(
            and_(
                Reservation.assigned_room_id.isnot(None),
                Reservation.status.notin_([ReservationStatus.cancelled]),
                Reservation.checkin < to_date,
                Reservation.checkout > from_date,
            )
        )
    )
    reservations = reservations_result.scalars().all()
    res_by_room: dict[int, list[Reservation]] = {}
    for r in reservations:
        res_by_room.setdefault(r.assigned_room_id, []).append(r)

    blocks_result = await db.execute(
        select(RoomBlock).where(
            and_(
                RoomBlock.date_from < to_date,
                RoomBlock.date_to > from_date,
            )
        )
    )
    blocks = blocks_result.scalars().all()
    blocks_by_room: dict[int, list[RoomBlock]] = {}
    for b in blocks:
        blocks_by_room.setdefault(b.room_id, []).append(b)

    rows = []
    for room in rooms:
        cat = cats.get(room.category_id)
        room_reservations = [
            ReservationBar(
                reservation_id=r.id,
                guest_name=r.guest_name,
                checkin=r.checkin,
                checkout=r.checkout,
                status=r.status,
                board_type=r.board_type,
            )
            for r in res_by_room.get(room.id, [])
        ]
        room_blocks = [
            BlockBar(block_id=b.id, date_from=b.date_from, date_to=b.date_to, reason=b.reason)
            for b in blocks_by_room.get(room.id, [])
        ]
        rows.append(PlahataRow(
            room_id=room.id,
            room_number=room.number,
            floor=room.floor,
            category_id=room.category_id,
            category_name=cat.name if cat else "",
            reservations=room_reservations,
            blocks=room_blocks,
        ))

    return PlahataResponse(from_date=from_date, to_date=to_date, rows=rows)
