"""Pydantic schemas for AI investigation output."""
from pydantic import BaseModel, ConfigDict, Field


class AIAnalysisResult(BaseModel):
    """Structured, machine-verifiable root cause analysis produced by AI or fallback."""
    model_config = ConfigDict(extra="ignore")

    classification: str = Field(
        ...,
        description="Categorization of the discrepancy (e.g., TIMING_DIFFERENCE, FEE_DISCREPANCY, REFUND_UNACCOUNTED, CHARGEBACK_HOLD, MISSING_PAYMENT, MISSING_LEDGER, AMOUNT_MISMATCH)"
    )
    explanation: str = Field(
        ...,
        description="Concise, factual financial narrative explaining the mathematical/operational root cause"
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Exact identifiers, amounts, or timestamps from the dossier proving the explanation"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
    recommended_action: str = Field(
        ...,
        description="Recommended resolution action (e.g., AUTO_RESOLVE_TIMING, POST_FEE_ADJUSTMENT, HOLD_FOR_SETTLEMENT, ESCALATE_TO_HUMAN, WRITE_OFF)"
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Any missing reports or external bank confirmations required to reach 100% certainty"
    )
    requires_human_review: bool = Field(
        ...,
        description="True if human intervention is mandatory; False if deterministic policy allows auto-resolution"
    )
