from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.room_category import RoomCategory
from app.models.reservation import Reservation, ReservationStatus
from app.models.event_log import EventLog, EventType
from app.schemas.room import BlockRequest, BlockOut, RoomStatusOut, RoomOut, RoomCategoryOut
from app.api.websocket import manager

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).order_by(Room.floor, Room.number))
    return result.scalars().all()


@router.get("/categories", response_model=list[RoomCategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RoomCategory).order_by(RoomCategory.name))
    return result.scalars().all()


@router.get("/status", response_model=list[RoomStatusOut])
async def rooms_status(db: AsyncSession = Depends(get_db)):
    today = date.today()

    rooms_result = await db.execute(select(Room).order_by(Room.floor, Room.number))
    rooms = rooms_result.scalars().all()
    room_ids = [r.id for r in rooms]

    # Bulk fetch: active blocks today
    blocks_result = await db.execute(
        select(RoomBlock).where(
            and_(
                RoomBlock.room_id.in_(room_ids),
                RoomBlock.date_from <= today,
                RoomBlock.date_to > today,
            )
        )
    )
    blocked_room_ids = {b.room_id for b in blocks_result.scalars().all()}

    # Bulk fetch: active reservations today (arrival day through night before checkout)
    res_result = await db.execute(
        select(Reservation).where(
            and_(
                Reservation.assigned_room_id.in_(room_ids),
                Reservation.status.notin_([ReservationStatus.cancelled]),
                Reservation.checkin <= today,
                Reservation.checkout >= today,
            )
        )
    )
    # room_id → first matching reservation (shouldn't be multiple, but defensive)
    res_by_room: dict[int, Reservation] = {}
    for res in res_result.scalars().all():
        if res.assigned_room_id not in res_by_room:
            res_by_room[res.assigned_room_id] = res

    output = []
    for room in rooms:
        if room.id in blocked_room_ids:
            output.append(RoomStatusOut(
                id=room.id, number=room.number, floor=room.floor,
                category_id=room.category_id, status="blocked",
            ))
            continue

        res = res_by_room.get(room.id)
        if res:
            if res.checkin == today and res.checkout == today:
                # Same-day turnaround: show as arrival (edge case)
                room_status = "arrival"
            elif res.checkin == today:
                room_status = "arrival"
            elif res.checkout == today:
                room_status = "departure"
            else:
                room_status = "occupied"
            output.append(RoomStatusOut(
                id=room.id, number=room.number, floor=room.floor,
                category_id=room.category_id, status=room_status,
                guest_name=res.guest_name, reservation_id=res.id, checkout=res.checkout,
            ))
        else:
            output.append(RoomStatusOut(
                id=room.id, number=room.number, floor=room.floor,
                category_id=room.category_id, status="free",
            ))

    return output


@router.get("/blocks", response_model=list[BlockOut])
async def list_blocks(
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    q = select(RoomBlock).where(RoomBlock.date_to >= (from_date or today))
    if to_date:
        q = q.where(RoomBlock.date_from < to_date)
    q = q.order_by(RoomBlock.date_from)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/{room_id}/block", response_model=BlockOut, status_code=status.HTTP_201_CREATED)
async def block_room(room_id: int, body: BlockRequest, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    if body.date_from >= body.date_to:
        raise HTTPException(400, "date_from must be before date_to")

    block = RoomBlock(
        room_id=room_id,
        date_from=body.date_from,
        date_to=body.date_to,
        reason=body.reason,
    )
    db.add(block)
    db.add(EventLog(room_id=room_id, event_type=EventType.blocked, detail={"reason": body.reason}))
    await db.commit()
    await db.refresh(block)

    await manager.broadcast("room.blocked", {"room_id": room_id, "date_from": body.date_from.isoformat(), "date_to": body.date_to.isoformat()})
    return block


@router.delete("/{room_id}/block/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(room_id: int, block_id: int, db: AsyncSession = Depends(get_db)):
    block = await db.get(RoomBlock, block_id)
    if not block or block.room_id != room_id:
        raise HTTPException(404, "Block not found")
    await db.delete(block)
    db.add(EventLog(room_id=room_id, event_type=EventType.unblocked, detail={"block_id": block_id}))
    await db.commit()
    await manager.broadcast("room.unblocked", {"room_id": room_id, "block_id": block_id})


@router.post("/{room_id}/unblock", status_code=status.HTTP_200_OK)
async def unblock_room(room_id: int, db: AsyncSession = Depends(get_db)):
    """Remove ALL future/active blocks for a room (convenience endpoint for GUI)."""
    today = date.today()
    result = await db.execute(
        select(RoomBlock).where(
            and_(RoomBlock.room_id == room_id, RoomBlock.date_to >= today)
        )
    )
    blocks = result.scalars().all()
    if not blocks:
        raise HTTPException(404, "No active block found for this room")

    for block in blocks:
        await db.delete(block)
    db.add(EventLog(room_id=room_id, event_type=EventType.unblocked, detail={}))
    await db.commit()

    await manager.broadcast("room.unblocked", {"room_id": room_id})
    return {"unblocked": len(blocks)}
