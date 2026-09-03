"""Reconciliation API routes for triggering and inspecting reconciliation runs."""
from datetime import datetime
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.merchant import Merchant
from app.models.reconciliation import ReconciliationRun, ReconciliationMatch
from app.models.exception import Exception_
from app.reconciliation.engine import ReconciliationEngine

router = APIRouter()


class ReconciliationRunRequest(BaseModel):
    merchant_id: uuid.UUID
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    parameters: dict[str, Any] | None = None


class ReconciliationRunResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    total_records: int
    matched_records: int
    unmatched_records: int
    exceptions_found: int
    auto_resolved: int
    human_review: int
    processing_time_ms: int | None
    parameters: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class ReconciliationMatchResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    payment_id: uuid.UUID | None
    order_id: uuid.UUID | None
    settlement_id: uuid.UUID | None
    ledger_entry_id: uuid.UUID | None
    match_status: str
    match_confidence: float
    match_reasons: list[str] | None
    expected_amount: float | None
    actual_amount: float | None
    variance: float | None
    recon_status: str

    model_config = ConfigDict(from_attributes=True)


@router.post("/reconciliation/run", response_model=ReconciliationRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_reconciliation(
    request: ReconciliationRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Triggers an atomic financial reconciliation run across all ingested data sources."""
    merchant = await db.get(Merchant, request.merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    engine = ReconciliationEngine()
    try:
        run = await engine.run_reconciliation(
            db=db,
            merchant_id=request.merchant_id,
            from_timestamp=request.from_timestamp,
            to_timestamp=request.to_timestamp,
            parameters=request.parameters,
        )
        return run
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Reconciliation run failed: {str(e)}")


@router.get("/reconciliation/{run_id}", response_model=ReconciliationRunResponse)
async def get_reconciliation_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetches details and metrics of a reconciliation run."""
    run = await db.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")
    return run


@router.get("/reconciliation", response_model=list[ReconciliationRunResponse])
async def list_reconciliation_runs(
    merchant_id: uuid.UUID = Query(..., description="Merchant ID"),
    db: AsyncSession = Depends(get_db),
):
    """Lists all reconciliation runs executed for a merchant."""
    stmt = (
        select(ReconciliationRun)
        .where(ReconciliationRun.merchant_id == merchant_id)
        .order_by(ReconciliationRun.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/reconciliation/{run_id}/matches", response_model=list[ReconciliationMatchResponse])
async def get_run_matches(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetches all matched records associated with a reconciliation run."""
    stmt = select(ReconciliationMatch).where(ReconciliationMatch.run_id == run_id)
    result = await db.execute(stmt)
    return result.scalars().all()
