"""Immutable audit logging service for RECON-X."""
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogger:
    """Provides append-only recording and retrieval of audit events."""

    @staticmethod
    async def log_action(
        db: AsyncSession,
        entity_id: uuid.UUID,
        entity_type: str,
        action: str,
        actor: str,
        details: dict[str, Any],
        request_id: str | None = None,
    ) -> AuditLog:
        """
        Appends an immutable audit log entry. Never updates or deletes existing rows.
        """
        audit_entry = AuditLog(
            id=uuid.uuid4(),
            entity_id=entity_id,
            entity_type=entity_type,
            action=action,
            actor=actor,
            timestamp=datetime.now(timezone.utc),
            details=details,
            request_id=request_id,
        )
        db.add(audit_entry)
        await db.flush()
        return audit_entry

    @staticmethod
    async def get_trail(
        db: AsyncSession,
        entity_id: uuid.UUID,
    ) -> list[AuditLog]:
        """Retrieves chronological audit log records for an entity."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_id == entity_id)
            .order_by(AuditLog.timestamp.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
