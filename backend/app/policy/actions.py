"""Execution actions for automated and human reconciliation resolutions."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exception import Exception_
from app.models.decision import Decision
from app.audit.logger import AuditLogger


class ResolutionActions:
    """Safely transitions exception states and records immutable decision logs."""

    @staticmethod
    async def execute_resolution(
        db: AsyncSession,
        exception: Exception_,
        decision_type: str,  # "auto_resolve", "human_approve", "human_reject", "human_request_info", "human_false_positive"
        decided_by: str,  # "system:policy_engine" or user email/id
        action_name: str,
        reason: str,
        policy_data: dict[str, Any],
        ai_recommendation: dict[str, Any] | None = None,
        confidence: Decimal | None = None,
        notes: str | None = None,
    ) -> Decision:
        """
        Transitions the Exception_ model, creates a Decision record, and logs an AuditLog entry.
        """
        before_state = {
            "status": exception.status,
            "resolved_at": exception.resolved_at.isoformat() if exception.resolved_at else None,
            "assigned_to": exception.assigned_to,
        }

        # Apply state transition
        now = datetime.now(timezone.utc)
        if decision_type == "auto_resolve":
            exception.status = "auto_resolved"
            exception.resolved_at = now
            exception.resolution_notes = f"Auto-resolved via policy action: {action_name}. Reason: {reason}"
        elif decision_type == "human_approve":
            exception.status = "approved"
            exception.resolved_at = now
            exception.resolution_notes = notes or f"Human approved action: {action_name}"
            exception.assigned_to = decided_by
        elif decision_type == "human_reject":
            exception.status = "rejected"
            exception.resolved_at = now
            exception.resolution_notes = notes or "Human rejected recommended resolution"
            exception.assigned_to = decided_by
        elif decision_type == "human_request_info":
            exception.status = "investigating"
            exception.resolution_notes = notes or "Information requested from merchant operations"
            exception.assigned_to = decided_by
        elif decision_type == "human_false_positive":
            exception.status = "false_positive"
            exception.resolved_at = now
            exception.resolution_notes = notes or "Flagged as false positive"
            exception.assigned_to = decided_by

        after_state = {
            "status": exception.status,
            "resolved_at": exception.resolved_at.isoformat() if exception.resolved_at else None,
            "assigned_to": exception.assigned_to,
        }

        # Create Decision row
        decision = Decision(
            id=uuid.uuid4(),
            exception_id=exception.id,
            decision_type=decision_type,
            decided_by=decided_by,
            decision_timestamp=now,
            input_evidence=exception.ai_analysis or {},
            policy_evaluation=policy_data,
            ai_recommendation=ai_recommendation,
            action_taken=action_name,
            before_state=before_state,
            after_state=after_state,
            confidence=confidence,
            reason=reason,
        )
        db.add(decision)

        # Record immutable audit log
        await AuditLogger.log_action(
            db=db,
            entity_id=exception.id,
            entity_type="exception",
            action=f"exception_{decision_type}",
            actor=decided_by,
            details={
                "action": action_name,
                "reason": reason,
                "decision_id": str(decision.id),
                "before_status": before_state["status"],
                "after_status": after_state["status"],
            },
        )

        await db.commit()
        await db.refresh(exception)
        await db.refresh(decision)

        return decision
