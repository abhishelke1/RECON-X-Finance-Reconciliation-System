"""Settlement model for tracking settlement records."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Settlement(BaseModel):
    """Represents a settlement record from Razorpay."""
    __tablename__ = "settlements"

    merchant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("merchants.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    fees: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    tax: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String, nullable=False)

    utr: Mapped[str | None] = mapped_column(String, nullable=True)
    settlement_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_id", "source_system", name="uix_settlement_source"),
    )
