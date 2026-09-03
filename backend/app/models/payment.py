"""Payment model for tracking payment records from various sources."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, UniqueConstraint, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Payment(BaseModel):
    """Represents a payment record from Razorpay or external systems."""
    __tablename__ = "payments"

    merchant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("merchants.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)
    order_source_id: Mapped[str | None] = mapped_column(String, nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    tax: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str | None] = mapped_column(String, nullable=True)

    customer_email: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)

    payment_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_id", "source_system", name="uix_payment_source"),
        Index("ix_payment_merchant_id", "merchant_id"),
        Index("ix_payment_status", "status"),
        Index("ix_payment_timestamp", "payment_timestamp"),
    )
