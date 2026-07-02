import asyncio
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.admin_settings import AdminSettings
from app.models.email_message import EmailMessage, ParseStatus
from app.models.room import Room
from app.models.room_category import RoomCategory
from app.schemas.admin import AdminSettingsOut, AdminSettingsPatch, PinVerifyRequest, PinVerifyResponse
from app.schemas.room import RoomCreate, RoomOut, RoomPatch, RoomCategoryCreate, RoomCategoryOut
from app.services.crypto import decrypt_password, encrypt_password, hash_pin, verify_pin

router = APIRouter(prefix="/admin", tags=["admin"])


async def _get_admin(db: AsyncSession) -> AdminSettings:
    result = await db.execute(select(AdminSettings).where(AdminSettings.id == 1))
    admin = result.scalar_one_or_none()
    if not admin:
        admin = AdminSettings(id=1)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
    return admin


def _check_pin(pin: str, admin: AdminSettings) -> None:
    if not admin.pin_hash:
        return  # No PIN set yet - allow (initial setup)
    if not verify_pin(pin, admin.pin_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid PIN")


@router.post("/verify-pin", response_model=PinVerifyResponse)
async def verify_pin_endpoint(body: PinVerifyRequest, db: AsyncSession = Depends(get_db)):
    admin = await _get_admin(db)
    if not admin.pin_hash:
        return PinVerifyResponse(valid=True)
    return PinVerifyResponse(valid=verify_pin(body.pin, admin.pin_hash))


@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await _get_admin(db)


@router.patch("/settings", response_model=AdminSettingsOut)
async def patch_settings(body: AdminSettingsPatch, db: AsyncSession = Depends(get_db)):
    admin = await _get_admin(db)
    _check_pin(body.pin, admin)

    for field in (
        "tourist_tax_rate", "tourist_tax_child_exempt_age", "tourist_tax_child_discount_pct",
        "imap_host", "imap_port", "imap_user", "pos_printer_name", "a4_printer_name",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(admin, field, value)

    if body.imap_password is not None:
        admin.imap_password_encrypted = encrypt_password(body.imap_password)

    if body.new_pin is not None:
        admin.pin_hash = hash_pin(body.new_pin)

    await db.commit()
    await db.refresh(admin)
    return admin


# ---- Room Categories ----

@router.get("/room-categories", response_model=list[RoomCategoryOut])
async def list_room_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RoomCategory).order_by(RoomCategory.name))
    return result.scalars().all()


@router.post("/room-categories", response_model=RoomCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_room_category(body: RoomCategoryCreate, db: AsyncSession = Depends(get_db)):
    cat = RoomCategory(**body.model_dump())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.patch("/room-categories/{cat_id}", response_model=RoomCategoryOut)
async def patch_room_category(
    cat_id: int, body: RoomCategoryCreate, db: AsyncSession = Depends(get_db)
):
    cat = await db.get(RoomCategory, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/room-categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room_category(cat_id: int, db: AsyncSession = Depends(get_db)):
    cat = await db.get(RoomCategory, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    await db.delete(cat)
    await db.commit()


# ---- Rooms ----

@router.get("/rooms", response_model=list[RoomOut])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).order_by(Room.floor, Room.number))
    return result.scalars().all()


@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(body: RoomCreate, db: AsyncSession = Depends(get_db)):
    room = Room(**body.model_dump())
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomOut)
async def patch_room(room_id: int, body: RoomPatch, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(room, field, value)
    await db.commit()
    await db.refresh(room)
    return room


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    await db.delete(room)
    await db.commit()


# ---- Email messages ----

class EmailMessageOut(BaseModel):
    id: int
    source: str
    raw_subject: str | None
    received_at: str
    parse_status: str
    reservation_id: int | None


@router.get("/emails", response_model=list[EmailMessageOut])
async def list_emails(
    parse_status_filter: ParseStatus | None = Query(None, alias="parse_status"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    from app.models.reservation import Reservation as Res
    q = (
        select(
            EmailMessage.id,
            EmailMessage.source,
            EmailMessage.raw_subject,
            EmailMessage.received_at,
            EmailMessage.parse_status,
            Res.id.label("reservation_id"),
        )
        .outerjoin(Res, Res.raw_email_id == EmailMessage.id)
        .order_by(desc(EmailMessage.received_at))
        .limit(limit)
    )
    if parse_status_filter:
        q = q.where(EmailMessage.parse_status == parse_status_filter)
    result = await db.execute(q)
    return [
        EmailMessageOut(
            id=row.id,
            source=row.source,
            raw_subject=row.raw_subject,
            received_at=row.received_at.isoformat(),
            parse_status=row.parse_status,
            reservation_id=row.reservation_id,
        )
        for row in result.all()
    ]


class EmailDetailOut(BaseModel):
    id: int
    source: str
    raw_subject: str | None
    raw_body: str | None
    received_at: str
    parse_status: str
    parsed_json: dict | None
    reservation_id: int | None


@router.get("/emails/{email_id}", response_model=EmailDetailOut)
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)):
    from app.models.reservation import Reservation as Res
    em = await db.get(EmailMessage, email_id)
    if not em:
        raise HTTPException(404, "Email not found")
    res_q = await db.execute(select(Res.id).where(Res.raw_email_id == email_id))
    return EmailDetailOut(
        id=em.id,
        source=em.source,
        raw_subject=em.raw_subject,
        raw_body=em.raw_body,
        received_at=em.received_at.isoformat(),
        parse_status=em.parse_status,
        parsed_json=em.parsed_json,
        reservation_id=res_q.scalar_one_or_none(),
    )


class EmailPatchRequest(BaseModel):
    parse_status: ParseStatus | None = None
    reservation_id: int | None = None  # link to existing reservation manually


@router.patch("/emails/{email_id}", response_model=EmailMessageOut)
async def patch_email(
    email_id: int, body: EmailPatchRequest, db: AsyncSession = Depends(get_db)
):
    """Manual review: update parse_status and/or link to a reservation."""
    em = await db.get(EmailMessage, email_id)
    if not em:
        raise HTTPException(404, "Email not found")

    if body.parse_status is not None:
        em.parse_status = body.parse_status

    reservation_id = None
    if body.reservation_id is not None:
        from app.models.reservation import Reservation as _Res
        res = await db.get(_Res, body.reservation_id)
        if not res:
            raise HTTPException(404, "Reservation not found")
        res.raw_email_id = email_id
        reservation_id = body.reservation_id

    await db.commit()
    await db.refresh(em)

    # Re-fetch reservation_id via query
    from app.models.reservation import Reservation as Res
    res_q = await db.execute(
        select(Res.id).where(Res.raw_email_id == email_id)
    )
    linked_res_id = res_q.scalar_one_or_none()

    return EmailMessageOut(
        id=em.id,
        source=em.source,
        raw_subject=em.raw_subject,
        received_at=em.received_at.isoformat(),
        parse_status=em.parse_status,
        reservation_id=linked_res_id,
    )


@router.post("/email-sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_email_sync(background_tasks: BackgroundTasks):
    """Manually trigger an IMAP poll cycle (runs in background)."""
    from app.services.email_ingest import _poll_once
    background_tasks.add_task(_poll_once)
    return {"status": "sync triggered"}
