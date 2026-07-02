from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class AdminSettings(Base):
    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tourist_tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("0.00")
    )
    tourist_tax_child_exempt_age: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7
    )
    tourist_tax_child_discount_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50
    )
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int] = mapped_column(Integer, nullable=False, default=993)
    imap_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    pos_printer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    a4_printer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
