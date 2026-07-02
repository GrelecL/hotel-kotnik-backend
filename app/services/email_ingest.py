import asyncio
import email
import email.utils
import logging
from datetime import datetime, timezone
from email.header import decode_header
from imaplib import IMAP4_SSL

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import AsyncSessionLocal
from app.models.admin_settings import AdminSettings
from app.models.email_message import EmailMessage, ParseStatus
from app.models.event_log import EventLog, EventType
from app.models.reservation import Reservation, ReservationStatus
from app.models.room_category import RoomCategory
from app.services import crypto, parser, room_assignment, tourist_tax as tax_service
from app.services.cancellation_detect import detect_cancellation
from app.core.websocket import manager

logger = logging.getLogger(__name__)


def _decode_header_value(raw: str) -> str:
    parts = decode_header(raw)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_body(msg: email.message.Message) -> str:
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode(charset, errors="replace"))
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(body_parts)


async def _get_admin_settings(db: AsyncSession) -> AdminSettings | None:
    result = await db.execute(select(AdminSettings).where(AdminSettings.id == 1))
    return result.scalar_one_or_none()


async def _resolve_category_id(db: AsyncSession, category_name: str | None) -> int | None:
    if not category_name:
        return None
    result = await db.execute(
        select(RoomCategory).where(RoomCategory.name.ilike(f"%{category_name}%"))
    )
    cat = result.scalars().first()
    return cat.id if cat else None


def _compute_tourist_tax(res: Reservation, admin: AdminSettings) -> None:
    res.tourist_tax_total = tax_service.calculate_tourist_tax(
        checkin=res.checkin,
        checkout=res.checkout,
        guests_adults=res.guests_adults,
        guests_children=res.guests_children,
        children_ages=res.children_ages,
        tax_rate=admin.tourist_tax_rate,
        child_exempt_age=admin.tourist_tax_child_exempt_age,
        child_discount_pct=admin.tourist_tax_child_discount_pct,
    )


async def _process_email(
    db: AsyncSession,
    uid: str,
    msg: email.message.Message,
    admin: AdminSettings,
) -> None:
    subject = _decode_header_value(msg.get("Subject", ""))
    from_addr = msg.get("From", "")
    date_str = msg.get("Date", "")
    try:
        received_at = email.utils.parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        received_at = datetime.now(timezone.utc)

    body = _get_body(msg)
    source = parser.detect_source(from_addr, subject)

    # Dedup: skip already processed UID
    existing_check = await db.execute(
        select(EmailMessage).where(EmailMessage.imap_uid == uid)
    )
    if existing_check.scalar_one_or_none():
        return

    email_msg = EmailMessage(
        source=source,
        raw_subject=subject,
        raw_body=body,
        received_at=received_at,
        parse_status=ParseStatus.manual_review,
        imap_uid=uid,
    )
    db.add(email_msg)
    await db.flush()

    # Try parsing
    try:
        parsed = await parser.parse_email(source, subject, body)
    except Exception as exc:
        logger.exception("Parser error for uid %s: %s", uid, exc)
        parsed = None

    if not parsed or not parsed.get("guest_name") or not parsed.get("checkin"):
        await db.commit()
        return

    email_msg.parsed_json = parsed
    email_msg.parse_status = ParseStatus.success

    is_cancel = await detect_cancellation(source, subject, body)

    external_ref = parsed.get("external_ref")
    existing_res: Reservation | None = None
    if external_ref:
        res_q = await db.execute(
            select(Reservation).where(
                Reservation.external_ref == external_ref,
                Reservation.source == source,
            )
        )
        existing_res = res_q.scalar_one_or_none()

    # --- Cancellation of known reservation ---
    if existing_res and is_cancel:
        existing_res.status = ReservationStatus.cancelled
        existing_res.assigned_room_id = None
        existing_res.raw_email_id = email_msg.id
        db.add(EventLog(
            reservation_id=existing_res.id,
            event_type=EventType.cancelled,
            detail={"email_uid": uid},
        ))
        await db.commit()
        await manager.broadcast("reservation.cancelled", {"id": existing_res.id})
        return

    # --- Cancellation with no matching reservation → manual review ---
    if is_cancel and not existing_res:
        email_msg.parse_status = ParseStatus.manual_review
        await db.commit()
        return

    # --- Update of existing reservation ---
    if existing_res and not is_cancel:
        import datetime as dt
        if parsed.get("guest_name"):
            existing_res.guest_name = parsed["guest_name"]
        if parsed.get("guests_adults") is not None:
            existing_res.guests_adults = parsed["guests_adults"]
        if parsed.get("guests_children") is not None:
            existing_res.guests_children = parsed["guests_children"]
        if parsed.get("children_ages") is not None:
            existing_res.children_ages = parsed["children_ages"]
        if parsed.get("board_type"):
            existing_res.board_type = parsed["board_type"]
        if parsed.get("price_total") is not None:
            existing_res.price_total = parsed["price_total"]
        if parsed.get("price_currency"):
            existing_res.price_currency = parsed["price_currency"]

        # Only update dates/room if recepcija hasn't manually overridden
        if not existing_res.manual_override:
            if parsed.get("checkin"):
                existing_res.checkin = dt.date.fromisoformat(parsed["checkin"])
            if parsed.get("checkout"):
                existing_res.checkout = dt.date.fromisoformat(parsed["checkout"])

        _compute_tourist_tax(existing_res, admin)
        existing_res.raw_email_id = email_msg.id
        db.add(EventLog(
            reservation_id=existing_res.id,
            event_type=EventType.modified,
            detail={"email_uid": uid},
        ))
        await db.commit()
        await manager.broadcast("reservation.updated", {"id": existing_res.id})
        return

    # --- New reservation ---
    import datetime as dt
    category_id = await _resolve_category_id(db, parsed.get("room_category"))
    checkin = dt.date.fromisoformat(parsed["checkin"])
    checkout = dt.date.fromisoformat(parsed["checkout"])

    reservation = Reservation(
        external_ref=external_ref,
        source=source,
        guest_name=parsed["guest_name"],
        checkin=checkin,
        checkout=checkout,
        room_category_id=category_id,
        guests_adults=parsed.get("guests_adults") or 1,
        guests_children=parsed.get("guests_children") or 0,
        children_ages=parsed.get("children_ages"),
        board_type=parsed.get("board_type") or "none",
        price_total=parsed.get("price_total"),
        price_currency=parsed.get("price_currency") or "EUR",
        status=ReservationStatus.confirmed,
        raw_email_id=email_msg.id,
    )
    _compute_tourist_tax(reservation, admin)
    db.add(reservation)
    await db.flush()

    db.add(EventLog(
        reservation_id=reservation.id,
        event_type=EventType.new,
        detail={"source": source, "email_uid": uid},
    ))

    # Room assignment
    if category_id and reservation.status == ReservationStatus.confirmed:
        room = await room_assignment.find_available_room(db, category_id, checkin, checkout)
        if room:
            reservation.assigned_room_id = room.id
            db.add(EventLog(
                reservation_id=reservation.id,
                room_id=room.id,
                event_type=EventType.assigned,
                detail={},
            ))
        else:
            reservation.status = ReservationStatus.unassigned
            await manager.broadcast("room.unassigned_alert", {
                "reservation_id": reservation.id,
                "guest_name": reservation.guest_name,
                "checkin": checkin.isoformat(),
                "checkout": checkout.isoformat(),
            })

    await db.commit()
    await manager.broadcast("reservation.new", {"id": reservation.id})


def _fetch_emails_sync(
    host: str, port: int, user: str, password: str, folder: str
) -> list[tuple[str, bytes]]:
    """
    Fetches UNSEEN emails using BODY.PEEK[] (does NOT mark as Seen).
    Returns list of (uid_str, raw_bytes).
    """
    with IMAP4_SSL(host, port) as imap:
        imap.login(user, password)
        imap.select(folder)
        _, data = imap.uid("search", None, "UNSEEN")
        uids = data[0].split()
        results = []
        for uid in uids:
            _, msg_data = imap.uid("fetch", uid, "(BODY.PEEK[])")
            raw = msg_data[0][1]
            results.append((uid.decode(), raw))
        return results


async def email_poll_loop() -> None:
    logger.info("Email poll loop started (interval=%ds)", settings.email_poll_interval)
    while True:
        try:
            await _poll_once()
        except Exception as exc:
            logger.exception("Email poll cycle failed: %s", exc)
        await asyncio.sleep(settings.email_poll_interval)


async def _poll_once() -> None:
    async with AsyncSessionLocal() as db:
        admin = await _get_admin_settings(db)
        if not admin or not admin.imap_host or not admin.imap_user:
            logger.debug("IMAP not configured, skipping poll")
            return
        if not admin.imap_password_encrypted:
            logger.warning("IMAP password not set, skipping poll")
            return
        try:
            password = crypto.decrypt_password(admin.imap_password_encrypted)
        except Exception as exc:
            logger.error("Failed to decrypt IMAP password: %s", exc)
            return
        host, port, user = admin.imap_host, admin.imap_port, admin.imap_user

    loop = asyncio.get_event_loop()
    try:
        raw_emails = await loop.run_in_executor(
            None,
            _fetch_emails_sync,
            host, port, user, password, settings.email_inbox_folder,
        )
    except Exception as exc:
        logger.error("IMAP fetch failed: %s", exc)
        return

    if raw_emails:
        logger.info("Fetched %d new emails", len(raw_emails))

    for uid, raw in raw_emails:
        msg = email.message_from_bytes(raw)
        try:
            async with AsyncSessionLocal() as db:
                admin = await _get_admin_settings(db)
                if admin:
                    await _process_email(db, uid, msg, admin)
        except Exception as exc:
            logger.exception("Failed processing email uid=%s: %s", uid, exc)
