"""Evaluation run model for tracking benchmark results."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, Integer, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class EvaluationRun(BaseModel):
    """Tracks evaluation/benchmark results — metrics calculated from actual runs."""
    __tablename__ = "evaluation_runs"

    reconciliation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("reconciliation_runs.id"), nullable=True
    )

    dataset_name: Mapped[str] = mapped_column(String, nullable=False)
    dataset_size: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    matching_precision: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    matching_recall: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    matching_f1: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    false_match_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    unresolved_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    exception_classification_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    auto_resolution_precision: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    human_review_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
