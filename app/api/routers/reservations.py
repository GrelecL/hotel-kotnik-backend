from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.admin_settings import AdminSettings
from app.models.event_log import EventLog, EventType
from app.models.reservation import Reservation, ReservationSource, ReservationStatus
from app.schemas.reservation import (
    ReassignRequest,
    ReservationOut,
    ReservationPatch,
    WalkInCreate,
)
from app.services import room_assignment
from app.services.tourist_tax import calculate_tourist_tax
from app.api.websocket import manager

router = APIRouter(prefix="/reservations", tags=["reservations"])


async def _get_admin(db: AsyncSession) -> AdminSettings:
    result = await db.execute(select(AdminSettings).where(AdminSettings.id == 1))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(500, "Admin settings not initialised")
    return admin


def _recompute_tax(res: Reservation, admin: AdminSettings) -> None:
    res.tourist_tax_total = calculate_tourist_tax(
        checkin=res.checkin,
        checkout=res.checkout,
        guests_adults=res.guests_adults,
        guests_children=res.guests_children,
        children_ages=res.children_ages,
        tax_rate=admin.tourist_tax_rate,
        child_exempt_age=admin.tourist_tax_child_exempt_age,
        child_discount_pct=admin.tourist_tax_child_discount_pct,
    )


@router.get("", response_model=list[ReservationOut])
async def list_reservations(
    from_date: date | None = None,
    to_date: date | None = None,
    status: ReservationStatus | None = None,
    guest: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Reservation)
    filters = []
    if from_date:
        filters.append(Reservation.checkout > from_date)
    if to_date:
        filters.append(Reservation.checkin < to_date)
    if status:
        filters.append(Reservation.status == status)
    if guest:
        filters.append(Reservation.guest_name.ilike(f"%{guest}%"))
    if filters:
        q = q.where(and_(*filters))
    q = q.order_by(Reservation.checkin.desc(), Reservation.guest_name)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{res_id}", response_model=ReservationOut)
async def get_reservation(res_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.get(Reservation, res_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    return res


@router.patch("/{res_id}", response_model=ReservationOut)
async def patch_reservation(
    res_id: int,
    body: ReservationPatch,
    db: AsyncSession = Depends(get_db),
):
    res = await db.get(Reservation, res_id)
    if not res:
        raise HTTPException(404, "Reservation not found")

    admin = await _get_admin(db)
    room_changed = False

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None:
            setattr(res, field, value)
            if field in ("assigned_room_id", "checkin", "checkout"):
                room_changed = True

    if res.checkout <= res.checkin:
        raise HTTPException(400, "checkout must be after checkin")

    if room_changed:
        res.manual_override = True

    _recompute_tax(res, admin)
    db.add(EventLog(reservation_id=res.id, event_type=EventType.modified, detail={}))
    await db.commit()
    await db.refresh(res)

    await manager.broadcast("reservation.updated", {"id": res.id})
    return res


@router.post("/walkin", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
async def create_walkin(body: WalkInCreate, db: AsyncSession = Depends(get_db)):
    admin = await _get_admin(db)

    res = Reservation(
        source=ReservationSource.walk_in,
        guest_name=body.guest_name,
        checkin=body.checkin,
        checkout=body.checkout,
        guests_adults=body.guests_adults,
        guests_children=body.guests_children,
        children_ages=body.children_ages,
        board_type=body.board_type,
        room_category_id=body.room_category_id,
        status=ReservationStatus.confirmed,
        manual_override=True,
    )

    _recompute_tax(res, admin)
    db.add(res)
    await db.flush()

    db.add(EventLog(reservation_id=res.id, event_type=EventType.new, detail={"source": "walk_in"}))

    if body.room_id:
        res.assigned_room_id = body.room_id
        db.add(EventLog(reservation_id=res.id, room_id=body.room_id, event_type=EventType.assigned, detail={"manual": True}))
    elif body.room_category_id:
        room = await room_assignment.find_available_room(
            db, body.room_category_id, body.checkin, body.checkout
        )
        if room:
            res.assigned_room_id = room.id
            db.add(EventLog(reservation_id=res.id, room_id=room.id, event_type=EventType.assigned, detail={}))
        else:
            res.status = ReservationStatus.unassigned
            await manager.broadcast("room.unassigned_alert", {
                "reservation_id": res.id,
                "guest_name": res.guest_name,
                "checkin": body.checkin.isoformat(),
                "checkout": body.checkout.isoformat(),
            })

    await db.commit()
    await db.refresh(res)

    await manager.broadcast("reservation.new", {"id": res.id})
    return res


@router.post("/{res_id}/cancel", response_model=ReservationOut)
async def cancel_reservation(res_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.get(Reservation, res_id)
    if not res:
        raise HTTPException(404, "Reservation not found")

    res.status = ReservationStatus.cancelled
    res.assigned_room_id = None
    db.add(EventLog(reservation_id=res.id, event_type=EventType.cancelled, detail={}))
    await db.commit()
    await db.refresh(res)

    await manager.broadcast("reservation.cancelled", {"id": res.id})
    return res


@router.patch("/{res_id}/reassign", response_model=ReservationOut)
async def reassign_reservation(
    res_id: int, body: ReassignRequest, db: AsyncSession = Depends(get_db)
):
    res = await db.get(Reservation, res_id)
    if not res:
        raise HTTPException(404, "Reservation not found")

    old_room = res.assigned_room_id
    res.assigned_room_id = body.room_id
    if body.checkin:
        res.checkin = body.checkin
    if body.checkout:
        res.checkout = body.checkout
    res.manual_override = True

    db.add(EventLog(
        reservation_id=res.id,
        room_id=body.room_id,
        event_type=EventType.reassigned,
        detail={"from_room": old_room, "to_room": body.room_id},
    ))
    await db.commit()
    await db.refresh(res)

    await manager.broadcast("reservation.updated", {"id": res.id, "reassigned": True})
    return res


class EventLogOut(BaseModel):
    id: int
    event_type: str
    room_id: int | None
    detail: dict | None
    created_at: datetime


@router.get("/{res_id}/events", response_model=list[EventLogOut])
async def get_reservation_events(res_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.get(Reservation, res_id)
    if not res:
        raise HTTPException(404, "Reservation not found")
    result = await db.execute(
        select(EventLog)
        .where(EventLog.reservation_id == res_id)
        .order_by(desc(EventLog.created_at))
    )
    return [
        EventLogOut(
            id=e.id,
            event_type=e.event_type,
            room_id=e.room_id,
            detail=e.detail,
            created_at=e.created_at,
        )
        for e in result.scalars().all()
    ]
