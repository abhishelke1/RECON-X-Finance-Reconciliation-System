"""Ledger entry model for general ledger / accounting records."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class LedgerEntry(BaseModel):
    """Represents a ledger/accounting entry from merchant ERP systems."""
    __tablename__ = "ledger_entries"

    merchant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("merchants.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)

    entry_type: Mapped[str] = mapped_column(String, nullable=False)  # debit/credit
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")

    account_code: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_id", "source_system", name="uix_ledger_source"),
    )
