"""Exception and evidence models for tracking reconciliation exceptions."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Exception_(BaseModel):
    """Represents a reconciliation exception requiring investigation."""
    __tablename__ = "exceptions"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("reconciliation_runs.id"), nullable=False)
    match_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("reconciliation_matches.id"), nullable=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("merchants.id"), nullable=False)

    exception_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    amount_involved: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    variance: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExceptionEvidence(BaseModel):
    """Evidence linked to an exception for investigation."""
    __tablename__ = "exception_evidence"

    exception_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("exceptions.id"), nullable=False)

    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    record_type: Mapped[str] = mapped_column(String, nullable=False)

    data_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    relationship: Mapped[str | None] = mapped_column(String, nullable=True)
