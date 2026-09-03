"""Deterministic fallback analyst for zero-LLM reliability and resilience."""
from decimal import Decimal
from typing import Any

from app.ai.schemas import AIAnalysisResult
from app.investigation.evidence_graph import EvidenceGraph


class DeterministicFallbackAnalyst:
    """Rules-based root cause analyzer used when LLMs are offline, rate-limited, or unconfigured."""

    @staticmethod
    def analyze(
        exception_type: str,
        amount_involved: Decimal | None,
        variance: Decimal | None,
        evidence_graph: EvidenceGraph,
    ) -> AIAnalysisResult:
        """
        Synthesizes structured root-cause analysis purely using deterministic business logic.
        Ensures 100% uptime and resilience against network or AI outages.
        """
        abs_var = abs(variance) if variance is not None else Decimal("0.0000")
        evidence_ids = [n.id for n in evidence_graph.nodes]

        # Case 1: Timing difference
        if exception_type == "TIMING_DIFFERENCE":
            return AIAnalysisResult(
                classification="TIMING_DIFFERENCE",
                explanation=(
                    "Transaction records balance with zero financial variance. The discrepancy was caused "
                    "by standard banking clearance and settlement cutoff timing across different operating days."
                ),
                supporting_evidence=evidence_ids[:3],
                confidence=0.92,
                recommended_action="AUTO_RESOLVE_TIMING",
                missing_information=[],
                requires_human_review=False,
            )

        # Case 2: Refund related
        elif exception_type == "REFUND_RELATED":
            has_refund_node = any(n.entity_type == "refund" for n in evidence_graph.nodes)
            if has_refund_node and abs_var <= Decimal("0.0500"):
                return AIAnalysisResult(
                    classification="REFUND_ACCOUNTED",
                    explanation="Variance is fully accounted for by a verified customer refund in the audit chain.",
                    supporting_evidence=evidence_ids[:3],
                    confidence=0.90,
                    recommended_action="MATCH_REFUND",
                    missing_information=[],
                    requires_human_review=False,
                )
            else:
                return AIAnalysisResult(
                    classification="PARTIAL_REFUND_DISCREPANCY",
                    explanation="A refund was located, but does not fully offset the observed transaction variance.",
                    supporting_evidence=evidence_ids[:3],
                    confidence=0.75,
                    recommended_action="ESCALATE_TO_HUMAN",
                    missing_information=["Bank settlement debit confirmation"],
                    requires_human_review=True,
                )

        # Case 3: Chargeback / Dispute
        elif exception_type == "CHARGEBACK_RELATED":
            return AIAnalysisResult(
                classification="CHARGEBACK_HOLD",
                explanation="Card issuer has placed a dispute hold on these funds. Requires merchant dispute defense or acceptance.",
                supporting_evidence=evidence_ids[:3],
                confidence=0.88,
                recommended_action="ESCALATE_TO_HUMAN",
                missing_information=["Dispute contest deadline", "Customer proof of fulfillment"],
                requires_human_review=True,
            )

        # Case 4: Missing Record
        elif exception_type == "MISSING_RECORD":
            has_payment = any(n.entity_type == "payment" for n in evidence_graph.nodes)
            if has_payment:
                explanation = "Payment successfully captured on Razorpay, but missing entirely from merchant ERP/GL ledger."
                classification = "MISSING_IN_LEDGER"
            else:
                explanation = "Unmatched bank/ledger credit received with no corresponding Razorpay payment identifier."
                classification = "ORPHAN_LEDGER_DEPOSIT"

            return AIAnalysisResult(
                classification=classification,
                explanation=explanation,
                supporting_evidence=evidence_ids[:2],
                confidence=0.85,
                recommended_action="INVESTIGATE_MISSING",
                missing_information=["ERP journal entry batch log"],
                requires_human_review=True,
            )

        # Case 5: Amount Mismatch
        elif exception_type == "AMOUNT_MISMATCH":
            return AIAnalysisResult(
                classification="AMOUNT_MISMATCH",
                explanation=f"Unexplained balance variance of {variance} INR detected between source records.",
                supporting_evidence=evidence_ids[:2],
                confidence=0.70,
                recommended_action="ESCALATE_TO_HUMAN",
                missing_information=["Fee schedule amendment", "TDS/Tax certificate"],
                requires_human_review=True,
            )

        # Default Case: Unknown
        return AIAnalysisResult(
            classification="UNKNOWN_EXCEPTION",
            explanation=f"Reconciliation exception of type '{exception_type}' with variance {variance} INR requires manual inspection.",
            supporting_evidence=evidence_ids[:2],
            confidence=0.50,
            recommended_action="ESCALATE_TO_HUMAN",
            missing_information=["Full audit trail log"],
            requires_human_review=True,
        )
