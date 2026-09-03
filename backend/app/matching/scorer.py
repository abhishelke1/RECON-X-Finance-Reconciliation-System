"""Confidence scoring and match status definitions for the matching engine."""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
import uuid


class MatchStatus(str, Enum):
    EXACT = "EXACT"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    POSSIBLE = "POSSIBLE"
    UNMATCHED = "UNMATCHED"
    CONFLICT = "CONFLICT"


@dataclass
class ScoredMatch:
    """Represents a matched set of entities with a confidence score and audit reasons."""
    match_status: MatchStatus
    confidence: Decimal  # 0.0000 to 1.0000
    reasons: list[str] = field(default_factory=list)
    
    # Entity references
    payment_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    settlement_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    refund_id: uuid.UUID | None = None
    chargeback_id: uuid.UUID | None = None
    ledger_entry_id: uuid.UUID | None = None

    # Financial details
    expected_amount: Decimal | None = None
    actual_amount: Decimal | None = None
    variance: Decimal | None = None
    level: str = "L0"  # L1_EXACT, L2_COMPOSITE, L3_ATTRIBUTE, L4_FUZZY

    metadata: dict[str, Any] = field(default_factory=dict)


def compute_confidence_status(confidence: Decimal) -> MatchStatus:
    """Classify confidence score into deterministic MatchStatus."""
    if confidence >= Decimal("0.99"):
        return MatchStatus.EXACT
    elif confidence >= Decimal("0.85"):
        return MatchStatus.HIGH_CONFIDENCE
    elif confidence >= Decimal("0.50"):
        return MatchStatus.POSSIBLE
    else:
        return MatchStatus.UNMATCHED
