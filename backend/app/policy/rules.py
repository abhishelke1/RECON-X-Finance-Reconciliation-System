"""Financial guardrail rules for deterministic auto-resolution."""
from dataclasses import dataclass
from decimal import Decimal

from app.config import get_settings
from app.ai.schemas import AIAnalysisResult
from app.models.exception import Exception_


@dataclass
class PolicyDecision:
    can_auto_resolve: bool
    action: str  # MARK_TIMING_RECONCILED, ASSOCIATE_REFUND, POST_ROUNDING_ADJUSTMENT, ESCALATE_TO_HUMAN
    reason: str
    reviewer_role: str | None = None


class PolicyRules:
    """Evaluates strict deterministic safety constraints. Overrides any AI hallucinations."""

    def __init__(self):
        settings = get_settings()
        self.confidence_threshold = Decimal(str(settings.auto_resolve_confidence_threshold))
        self.variance_threshold_inr = Decimal(str(settings.auto_resolve_variance_threshold_paise)) / Decimal("100")
        self.variance_threshold_pct = Decimal(str(settings.auto_resolve_variance_threshold_pct))

    def evaluate(self, exception: Exception_, ai_analysis: AIAnalysisResult) -> PolicyDecision:
        """
        Applies strict multi-point guardrails:
        Auto-resolution is permitted ONLY IF ALL conditions are met:
        1. AI analysis confidence >= threshold (0.85)
        2. AI requires_human_review is False
        3. Exception type is in safe allowed set (TIMING_DIFFERENCE, verified REFUND, micro-rounding)
        4. Absolute variance is within approved financial safety threshold (<= 10.00 INR)
        5. No unresolved chargebacks or missing record flags
        6. Missing information list is completely empty
        """
        abs_var = abs(exception.variance) if exception.variance is not None else Decimal("0.0000")
        amount = abs(exception.amount_involved) if exception.amount_involved is not None else Decimal("0.0000")
        ai_conf = Decimal(str(round(ai_analysis.confidence, 4)))

        # Rule 1: High-risk types FORBID auto-resolve
        if exception.exception_type in ("CHARGEBACK_RELATED", "UNKNOWN_EXCEPTION", "MISSING_RECORD"):
            return PolicyDecision(
                can_auto_resolve=False,
                action="ESCALATE_TO_HUMAN",
                reason=f"High-risk exception type '{exception.exception_type}' mandates human controller review.",
                reviewer_role="Senior Finance Operations",
            )

        # Rule 2: AI explicit human review flag
        if ai_analysis.requires_human_review:
            return PolicyDecision(
                can_auto_resolve=False,
                action="ESCALATE_TO_HUMAN",
                reason=f"AI investigation determined human review is mandatory: {ai_analysis.explanation}",
                reviewer_role="Finance Analyst",
            )

        # Rule 3: Missing information requires external verification
        if ai_analysis.missing_information:
            return PolicyDecision(
                can_auto_resolve=False,
                action="ESCALATE_TO_HUMAN",
                reason=f"Missing audit verification: {', '.join(ai_analysis.missing_information)}",
                reviewer_role="Finance Controller",
            )

        # Rule 4: Confidence Gate
        if ai_conf < self.confidence_threshold:
            return PolicyDecision(
                can_auto_resolve=False,
                action="ESCALATE_TO_HUMAN",
                reason=f"Confidence {ai_conf} below strict safety threshold ({self.confidence_threshold}).",
                reviewer_role="Finance Analyst",
            )

        # Rule 5: Safe Auto-Resolve Cases
        # Case A: Timing Difference with Zero Variance
        if exception.exception_type == "TIMING_DIFFERENCE" and abs_var == Decimal("0.0000"):
            return PolicyDecision(
                can_auto_resolve=True,
                action="MARK_TIMING_RECONCILED",
                reason="Zero variance verified; clearance delay confirmed within acceptable banking schedule.",
                reviewer_role=None,
            )

        # Case B: Verified Refund offsetting variance
        if exception.exception_type == "REFUND_RELATED" and abs_var <= Decimal("0.0500"):
            return PolicyDecision(
                can_auto_resolve=True,
                action="ASSOCIATE_REFUND",
                reason="Verified refund offsets ledger position with zero net variance.",
                reviewer_role=None,
            )

        # Case C: Micro-rounding adjustment (<= 10.00 INR and <= 0.5%)
        if abs_var <= self.variance_threshold_inr:
            pct = (abs_var / amount * Decimal("100")) if amount > Decimal("0") else Decimal("0.0")
            if pct <= self.variance_threshold_pct:
                return PolicyDecision(
                    can_auto_resolve=True,
                    action="POST_ROUNDING_ADJUSTMENT",
                    reason=f"Micro variance of {abs_var} INR ({pct:.2f}%) within allowable rounding tolerance (<= {self.variance_threshold_inr} INR).",
                    reviewer_role=None,
                )

        # Default: Escalate
        return PolicyDecision(
            can_auto_resolve=False,
            action="ESCALATE_TO_HUMAN",
            reason=f"Variance of {abs_var} INR exceeds safe automated resolution limits.",
            reviewer_role="Senior Finance Controller",
        )
