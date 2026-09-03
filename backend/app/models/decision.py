"""Decision model for tracking resolution decisions."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, JSON, ForeignKey, Numeric, DateTime, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class Decision(BaseModel):
    """Represents a resolution decision (auto or human) for an exception."""
    __tablename__ = "decisions"

    exception_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("exceptions.id"), nullable=False)

    decision_type: Mapped[str] = mapped_column(String, nullable=False)
    decided_by: Mapped[str] = mapped_column(String, nullable=False)
    decision_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    input_evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    policy_evaluation: Mapped[dict] = mapped_column(JSON, nullable=False)
    ai_recommendation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    action_taken: Mapped[str] = mapped_column(String, nullable=False)
    before_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    after_state: Mapped[dict] = mapped_column(JSON, nullable=False)

    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
