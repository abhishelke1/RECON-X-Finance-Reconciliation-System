"""Reconciliation run and match models."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class ReconciliationRun(BaseModel):
    """Represents a single reconciliation run/batch."""
    __tablename__ = "reconciliation_runs"

    merchant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("merchants.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exceptions_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_resolved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ReconciliationMatch(BaseModel):
    """Represents a matched set of records across data sources."""
    __tablename__ = "reconciliation_matches"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("reconciliation_runs.id"), nullable=False)

    payment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payments.id"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("orders.id"), nullable=True)
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("settlements.id"), nullable=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("invoices.id"), nullable=True)
    refund_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("refunds.id"), nullable=True)
    chargeback_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("chargebacks.id"), nullable=True)
    ledger_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ledger_entries.id"), nullable=True)

    match_status: Mapped[str] = mapped_column(String, nullable=False)
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    match_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)

    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    actual_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    variance: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    recon_status: Mapped[str] = mapped_column(String, nullable=False)
