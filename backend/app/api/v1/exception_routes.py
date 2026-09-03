"""Exception management and human-in-the-loop review routes."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.exception import Exception_, ExceptionEvidence
from app.models.decision import Decision
from app.investigation.evidence_collector import EvidenceCollector
from app.ai.analyst import AIAnalyst
from app.policy.engine import PolicyEngine
from app.policy.actions import ResolutionActions
from app.audit.logger import AuditLogger

router = APIRouter()


# --- Pydantic Schemas ---

class ExceptionSummaryResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    match_id: uuid.UUID | None
    merchant_id: uuid.UUID
    exception_type: str
    severity: str
    status: str
    amount_involved: float | None
    variance: float | None
    description: str
    assigned_to: str | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExceptionDetailResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    match_id: uuid.UUID | None
    merchant_id: uuid.UUID
    exception_type: str
    severity: str
    status: str
    amount_involved: float | None
    variance: float | None
    description: str
    ai_analysis: dict[str, Any] | None
    policy_result: dict[str, Any] | None
    assigned_to: str | None
    resolved_at: datetime | None
    resolution_notes: str | None
    evidence_graph: dict[str, Any]
    decisions: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class HumanReviewActionRequest(BaseModel):
    reviewer: str = "controller@merchant.com"
    notes: str | None = None
    reason: str | None = None


# --- Endpoints ---

@router.get("/exceptions", response_model=list[ExceptionSummaryResponse])
async def list_exceptions(
    merchant_id: uuid.UUID | None = Query(None),
    run_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Lists exceptions with optional filters by status, severity, merchant, or run."""
    stmt = select(Exception_).order_by(Exception_.created_at.desc())
    if merchant_id:
        stmt = stmt.where(Exception_.merchant_id == merchant_id)
    if run_id:
        stmt = stmt.where(Exception_.run_id == run_id)
    if status_filter:
        stmt = stmt.where(Exception_.status == status_filter)
    if severity:
        stmt = stmt.where(Exception_.severity == severity)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/exceptions/{exception_id}", response_model=ExceptionDetailResponse)
async def get_exception_detail(
    exception_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves comprehensive exception dossier including causality graph and past decisions."""
    exc = await db.get(Exception_, exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    collector = EvidenceCollector()
    graph = await collector.collect_evidence(db, exception_id)

    # Fetch decisions
    dec_stmt = (
        select(Decision)
        .where(Decision.exception_id == exception_id)
        .order_by(Decision.decision_timestamp.asc())
    )
    decisions = (await db.execute(dec_stmt)).scalars().all()

    return ExceptionDetailResponse(
        id=exc.id,
        run_id=exc.run_id,
        match_id=exc.match_id,
        merchant_id=exc.merchant_id,
        exception_type=exc.exception_type,
        severity=exc.severity,
        status=exc.status,
        amount_involved=float(exc.amount_involved) if exc.amount_involved is not None else None,
        variance=float(exc.variance) if exc.variance is not None else None,
        description=exc.description,
        ai_analysis=exc.ai_analysis,
        policy_result=exc.policy_result,
        assigned_to=exc.assigned_to,
        resolved_at=exc.resolved_at,
        resolution_notes=exc.resolution_notes,
        evidence_graph=graph.to_dict(),
        decisions=[
            {
                "id": str(d.id),
                "decision_type": d.decision_type,
                "decided_by": d.decided_by,
                "timestamp": d.decision_timestamp.isoformat(),
                "action_taken": d.action_taken,
                "reason": d.reason,
                "confidence": float(d.confidence) if d.confidence is not None else None,
            }
            for d in decisions
        ],
    )


@router.post("/exceptions/{exception_id}/investigate")
async def investigate_exception(
    exception_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Executes AI root-cause investigation and applies policy guardrails."""
    exc = await db.get(Exception_, exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    collector = EvidenceCollector()
    graph = await collector.collect_evidence(db, exception_id)

    analyst = AIAnalyst()
    ai_analysis = await analyst.analyze_exception(exc, graph)

    policy_engine = PolicyEngine()
    policy_decision, decision_record = await policy_engine.evaluate_and_apply(
        db=db,
        exception=exc,
        ai_analysis=ai_analysis,
    )

    return {
        "exception_id": str(exc.id),
        "status": exc.status,
        "ai_analysis": ai_analysis.model_dump(),
        "policy_decision": {
            "can_auto_resolve": policy_decision.can_auto_resolve,
            "action": policy_decision.action,
            "reason": policy_decision.reason,
            "reviewer_role": policy_decision.reviewer_role,
        },
        "auto_resolved": policy_decision.can_auto_resolve,
        "decision_id": str(decision_record.id) if decision_record else None,
    }


@router.post("/exceptions/{exception_id}/approve")
async def human_approve_exception(
    exception_id: uuid.UUID,
    request: HumanReviewActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human controller approves resolution recommendation."""
    exc = await db.get(Exception_, exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    actions = ResolutionActions()
    action_name = exc.policy_result.get("action", "MANUAL_APPROVAL") if exc.policy_result else "MANUAL_APPROVAL"

    decision = await actions.execute_resolution(
        db=db,
        exception=exc,
        decision_type="human_approve",
        decided_by=request.reviewer,
        action_name=action_name,
        reason=request.reason or "Controller approved recommended resolution",
        policy_data=exc.policy_result or {},
        ai_recommendation=exc.ai_analysis,
        notes=request.notes,
    )

    return {"status": "approved", "exception_id": str(exc.id), "decision_id": str(decision.id)}


@router.post("/exceptions/{exception_id}/reject")
async def human_reject_exception(
    exception_id: uuid.UUID,
    request: HumanReviewActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human controller rejects resolution recommendation."""
    exc = await db.get(Exception_, exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    actions = ResolutionActions()
    decision = await actions.execute_resolution(
        db=db,
        exception=exc,
        decision_type="human_reject",
        decided_by=request.reviewer,
        action_name="REJECTED_BY_HUMAN",
        reason=request.reason or "Controller rejected proposed resolution",
        policy_data=exc.policy_result or {},
        ai_recommendation=exc.ai_analysis,
        notes=request.notes,
    )

    return {"status": "rejected", "exception_id": str(exc.id), "decision_id": str(decision.id)}


@router.post("/exceptions/{exception_id}/request-info")
async def human_request_info(
    exception_id: uuid.UUID,
    request: HumanReviewActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human controller requests external documentation or information."""
    exc = await db.get(Exception_, exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    actions = ResolutionActions()
    decision = await actions.execute_resolution(
        db=db,
        exception=exc,
        decision_type="human_request_info",
        decided_by=request.reviewer,
        action_name="REQUEST_INFORMATION",
        reason=request.reason or "Additional banking/ERP documentation requested",
        policy_data=exc.policy_result or {},
        ai_recommendation=exc.ai_analysis,
        notes=request.notes,
    )

    return {"status": "investigating", "exception_id": str(exc.id), "decision_id": str(decision.id)}


@router.post("/exceptions/{exception_id}/false-positive")
async def human_mark_false_positive(
    exception_id: uuid.UUID,
    request: HumanReviewActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human controller marks an exception as a false alarm."""
    exc = await db.get(Exception_, exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    actions = ResolutionActions()
    decision = await actions.execute_resolution(
        db=db,
        exception=exc,
        decision_type="human_false_positive",
        decided_by=request.reviewer,
        action_name="CLOSE_AS_FALSE_POSITIVE",
        reason=request.reason or "Controller identified false positive",
        policy_data=exc.policy_result or {},
        ai_recommendation=exc.ai_analysis,
        notes=request.notes,
    )

    return {"status": "false_positive", "exception_id": str(exc.id), "decision_id": str(decision.id)}
