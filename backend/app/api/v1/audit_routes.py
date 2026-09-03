"""Audit trail API endpoints."""
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.audit.logger import AuditLogger

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    entity_type: str
    action: str
    actor: str
    timestamp: str
    details: dict[str, Any]
    request_id: str | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/audit/{entity_id}", response_model=list[AuditLogResponse])
async def get_audit_trail(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetches the complete, immutable chronological audit trail for any system entity."""
    logs = await AuditLogger.get_trail(db, entity_id)
    return [
        AuditLogResponse(
            id=log.id,
            entity_id=log.entity_id,
            entity_type=log.entity_type,
            action=log.action,
            actor=log.actor,
            timestamp=log.timestamp.isoformat(),
            details=log.details,
            request_id=log.request_id,
        )
        for log in logs
    ]
