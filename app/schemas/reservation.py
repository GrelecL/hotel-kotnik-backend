from datetime import date, datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, model_validator
from app.models.reservation import BoardType, ReservationSource, ReservationStatus


class ReservationBase(BaseModel):
    guest_name: str
    checkin: date
    checkout: date
    guests_adults: int = 1
    guests_children: int = 0
    children_ages: list[int] | None = None
    board_type: BoardType = BoardType.none
    price_total: Decimal | None = None
    price_currency: str = "EUR"
    notes: str | None = None
    room_category_id: int | None = None


class ReservationCreate(ReservationBase):
    source: ReservationSource = ReservationSource.walk_in
    assigned_room_id: int | None = None


class WalkInCreate(BaseModel):
    guest_name: str
    checkin: date
    checkout: date
    guests_adults: int = 1
    guests_children: int = 0
    children_ages: list[int] | None = None
    board_type: BoardType = BoardType.none
    room_id: int | None = None
    room_category_id: int | None = None

    @model_validator(mode="after")
    def check_dates_and_room(self) -> "WalkInCreate":
        if self.checkout <= self.checkin:
            raise ValueError("checkout must be after checkin")
        if self.room_id is None and self.room_category_id is None:
            raise ValueError("provide either room_id or room_category_id")
        return self


class ReservationPatch(BaseModel):
    guest_name: str | None = None
    checkin: date | None = None
    checkout: date | None = None
    guests_adults: int | None = None
    guests_children: int | None = None
    children_ages: list[int] | None = None
    board_type: BoardType | None = None
    price_total: Decimal | None = None
    price_currency: str | None = None
    notes: str | None = None
    assigned_room_id: int | None = None
    room_category_id: int | None = None
    status: ReservationStatus | None = None


class ReassignRequest(BaseModel):
    room_id: int
    checkin: date | None = None
    checkout: date | None = None


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_ref: str | None
    source: ReservationSource
    guest_name: str
    checkin: date
    checkout: date
    room_category_id: int | None
    assigned_room_id: int | None
    guests_adults: int
    guests_children: int
    children_ages: list[int] | None
    board_type: BoardType
    price_total: Decimal | None
    price_currency: str
    tourist_tax_total: Decimal | None
    status: ReservationStatus
    manual_override: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
