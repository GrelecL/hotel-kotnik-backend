from datetime import date
from pydantic import BaseModel, ConfigDict


class RoomCategoryBase(BaseModel):
    name: str
    capacity: int


class RoomCategoryCreate(RoomCategoryBase):
    pass


class RoomCategoryOut(RoomCategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RoomBase(BaseModel):
    number: str
    floor: int
    category_id: int


class RoomCreate(RoomBase):
    pass


class RoomPatch(BaseModel):
    number: str | None = None
    floor: int | None = None
    category_id: int | None = None


class RoomOut(RoomBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RoomStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    floor: int
    category_id: int
    # "free" | "occupied" | "blocked" | "arrival" | "departure"
    status: str
    guest_name: str | None = None
    reservation_id: int | None = None
    checkout: date | None = None


class BlockRequest(BaseModel):
    date_from: date
    date_to: date
    reason: str | None = None


class BlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    room_id: int
    date_from: date
    date_to: date
    reason: str | None
