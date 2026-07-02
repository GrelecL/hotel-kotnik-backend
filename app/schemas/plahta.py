from datetime import date
from pydantic import BaseModel


class ReservationBar(BaseModel):
    reservation_id: int
    guest_name: str
    checkin: date
    checkout: date
    status: str
    board_type: str


class BlockBar(BaseModel):
    block_id: int
    date_from: date
    date_to: date
    reason: str | None


class PlahataRow(BaseModel):
    room_id: int
    room_number: str
    floor: int
    category_id: int
    category_name: str
    reservations: list[ReservationBar]
    blocks: list[BlockBar]


class PlahataResponse(BaseModel):
    from_date: date
    to_date: date
    rows: list[PlahataRow]
