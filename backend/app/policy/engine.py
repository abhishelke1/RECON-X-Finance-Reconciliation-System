"""Deterministic Policy Engine Orchestrator."""
from decimal import Decimal
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exception import Exception_
from app.models.decision import Decision
from app.ai.schemas import AIAnalysisResult
from app.policy.rules import PolicyRules, PolicyDecision
from app.policy.actions import ResolutionActions
from app.audit.logger import AuditLogger

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Evaluates guardrail policies and executes safe automated actions."""

    def __init__(self, rules: PolicyRules | None = None, actions: ResolutionActions | None = None):
        self.rules = rules or PolicyRules()
        self.actions = actions or ResolutionActions()

    async def evaluate_and_apply(
        self,
        db: AsyncSession,
        exception: Exception_,
        ai_analysis: AIAnalysisResult,
    ) -> tuple[PolicyDecision, Decision | None]:
        """
        Evaluates safety policies against an exception and AI findings:
        - If SAFE: automatically resolves the exception, logs decision & audit.
        - If RISKY / UNCERTAIN: routes to human controller review queue.
        """
        policy_decision = self.rules.evaluate(exception, ai_analysis)

        # Store policy evaluation on the exception model
        policy_dict = {
            "can_auto_resolve": policy_decision.can_auto_resolve,
            "action": policy_decision.action,
            "reason": policy_decision.reason,
            "reviewer_role": policy_decision.reviewer_role,
        }
        exception.policy_result = policy_dict
        exception.ai_analysis = ai_analysis.model_dump()

        executed_decision: Decision | None = None

        if policy_decision.can_auto_resolve:
            logger.info(
                "Exception %s qualifies for auto-resolution: %s (%s)",
                exception.id,
                policy_decision.action,
                policy_decision.reason,
            )
            executed_decision = await self.actions.execute_resolution(
                db=db,
                exception=exception,
                decision_type="auto_resolve",
                decided_by="system:policy_engine",
                action_name=policy_decision.action,
                reason=policy_decision.reason,
                policy_data=policy_dict,
                ai_recommendation=ai_analysis.model_dump(),
                confidence=Decimal(str(round(ai_analysis.confidence, 4))),
            )
        else:
            logger.info(
                "Exception %s routed to human review: %s",
                exception.id,
                policy_decision.reason,
            )
            exception.status = "human_review"
            await AuditLogger.log_action(
                db=db,
                entity_id=exception.id,
                entity_type="exception",
                action="escalated_to_human_review",
                actor="system:policy_engine",
                details={
                    "reason": policy_decision.reason,
                    "reviewer_role": policy_decision.reviewer_role,
                    "action_suggested": policy_decision.action,
                },
            )
            await db.commit()
            await db.refresh(exception)

        return policy_decision, executed_decision
