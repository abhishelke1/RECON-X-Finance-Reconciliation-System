"""Audit log model for immutable action tracking. APPEND-ONLY — no updates or deletes."""
import uuid
from datetime import datetime

from sqlalchemy import String, JSON, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class AuditLog(BaseModel):
    """Immutable audit log entry. This table is APPEND-ONLY."""
    __tablename__ = "audit_logs"

    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)

    action: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
