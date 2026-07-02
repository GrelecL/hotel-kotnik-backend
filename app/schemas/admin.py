from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class AdminSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tourist_tax_rate: Decimal
    tourist_tax_child_exempt_age: int
    tourist_tax_child_discount_pct: int
    imap_host: str | None
    imap_port: int
    imap_user: str | None
    pos_printer_name: str | None
    a4_printer_name: str | None


class AdminSettingsPatch(BaseModel):
    pin: str  # current PIN required to make changes
    tourist_tax_rate: Decimal | None = None
    tourist_tax_child_exempt_age: int | None = None
    tourist_tax_child_discount_pct: int | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    imap_password: str | None = None  # plaintext, encrypted before storage
    pos_printer_name: str | None = None
    a4_printer_name: str | None = None
    new_pin: str | None = None


class PinVerifyRequest(BaseModel):
    pin: str


class PinVerifyResponse(BaseModel):
    valid: bool
