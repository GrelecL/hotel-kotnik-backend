from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.reservation import Reservation, ReservationStatus, BoardType
from app.schemas.reservation import ReservationOut

router = APIRouter(prefix="/reports", tags=["reports"])


class HousekeepingRow(BaseModel):
    reservation_id: int
    room_id: int
    guest_name: str
    action: str  # "checkout" | "stay" | "arrival"
    checkin: date
    checkout: date
    board_type: str
    guests_adults: int
    guests_children: int


class KitchenMealCount(BaseModel):
    date: date
    breakfast: int   # board_type: breakfast + half_board + full_board
    lunch: int       # board_type: full_board only
    dinner: int      # board_type: half_board + full_board


@router.get("/housekeeping", response_model=list[HousekeepingRow])
async def housekeeping(
    report_date: date = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reservation).where(
            and_(
                Reservation.assigned_room_id.isnot(None),
                Reservation.status.notin_([ReservationStatus.cancelled]),
                Reservation.checkin <= report_date,
                Reservation.checkout >= report_date,
            )
        ).order_by(Reservation.assigned_room_id)
    )
    rows = []
    for res in result.scalars().all():
        if res.checkout == report_date:
            action = "checkout"
        elif res.checkin == report_date:
            action = "arrival"
        else:
            action = "stay"
        rows.append(HousekeepingRow(
            reservation_id=res.id,
            room_id=res.assigned_room_id,
            guest_name=res.guest_name,
            action=action,
            checkin=res.checkin,
            checkout=res.checkout,
            board_type=res.board_type,
            guests_adults=res.guests_adults,
            guests_children=res.guests_children,
        ))
    return rows


@router.get("/kitchen", response_model=list[KitchenMealCount])
async def kitchen(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reservation).where(
            and_(
                Reservation.status.notin_([ReservationStatus.cancelled]),
                Reservation.board_type != BoardType.none,
                Reservation.checkin < to_date,
                Reservation.checkout > from_date,
            )
        )
    )
    reservations = result.scalars().all()

    daily: dict[date, dict[str, int]] = defaultdict(lambda: {"breakfast": 0, "lunch": 0, "dinner": 0})

    for res in reservations:
        guests = res.guests_adults + res.guests_children
        cur = max(res.checkin, from_date)
        end = min(res.checkout, to_date)
        while cur < end:
            if res.board_type in (BoardType.breakfast, BoardType.half_board, BoardType.full_board):
                daily[cur]["breakfast"] += guests
            if res.board_type == BoardType.full_board:
                daily[cur]["lunch"] += guests
            if res.board_type in (BoardType.half_board, BoardType.full_board):
                daily[cur]["dinner"] += guests
            cur += timedelta(days=1)

    output = []
    cur = from_date
    while cur < to_date:
        d = daily[cur]
        output.append(KitchenMealCount(date=cur, **d))
        cur += timedelta(days=1)
    return output


@router.get("/arrivals", response_model=list[ReservationOut])
async def arrivals(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reservation).where(
            and_(
                Reservation.checkin >= from_date,
                Reservation.checkin < to_date,
                Reservation.status.notin_([ReservationStatus.cancelled]),
            )
        ).order_by(Reservation.checkin, Reservation.guest_name)
    )
    return result.scalars().all()
