"""Financial reconciliation state classifier.

Classifies matched and unmatched records into 10 deterministic reconciliation states:
- MATCHED
- MATCHED_AFTER_FEES
- TIMING_DIFFERENCE
- REFUND_RELATED
- CHARGEBACK_RELATED
- PARTIAL_SETTLEMENT
- DUPLICATE
- MISSING_RECORD
- AMOUNT_MISMATCH
- UNKNOWN_EXCEPTION
"""
from datetime import timedelta
from decimal import Decimal
from enum import Enum

from app.matching.scorer import MatchStatus, ScoredMatch
from app.models.payment import Payment
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.reconciliation.calculator import CalculationResult


class ReconStatus(str, Enum):
    MATCHED = "MATCHED"
    MATCHED_AFTER_FEES = "MATCHED_AFTER_FEES"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    REFUND_RELATED = "REFUND_RELATED"
    CHARGEBACK_RELATED = "CHARGEBACK_RELATED"
    PARTIAL_SETTLEMENT = "PARTIAL_SETTLEMENT"
    DUPLICATE = "DUPLICATE"
    MISSING_RECORD = "MISSING_RECORD"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    UNKNOWN_EXCEPTION = "UNKNOWN_EXCEPTION"


class ReconciliationClassifier:
    """Deterministic rules classifier for reconciliation positions."""

    def __init__(self, timing_threshold_hours: int = 72):
        self.timing_threshold = timedelta(hours=timing_threshold_hours)

    def classify(
        self,
        match: ScoredMatch,
        calc: CalculationResult,
        payment: Payment | None = None,
        ledger_entry: LedgerEntry | None = None,
        refund: Refund | None = None,
        chargeback: Chargeback | None = None,
        settlement: Settlement | None = None,
    ) -> tuple[ReconStatus, str]:
        """
        Deterministically assigns one of the 10 states along with an explanatory justification.
        """
        # 1. Check if completely missing in one ledger/system
        if match.match_status == MatchStatus.UNMATCHED or (payment and not ledger_entry) or (ledger_entry and not payment):
            if payment and not ledger_entry:
                return (
                    ReconStatus.MISSING_RECORD,
                    f"Payment {payment.source_id} ({payment.amount} INR) captured on Razorpay but missing in merchant general ledger.",
                )
            elif ledger_entry and not payment:
                return (
                    ReconStatus.MISSING_RECORD,
                    f"Orphan ledger entry {ledger_entry.source_id} ({ledger_entry.amount} INR) has no corresponding Razorpay payment record.",
                )
            return (ReconStatus.MISSING_RECORD, "Record unmatched across both systems.")

        # 2. Check for duplicate flags or conflict status
        if match.match_status == MatchStatus.CONFLICT:
            return (
                ReconStatus.UNKNOWN_EXCEPTION,
                f"Conflicting match candidate: multiple records competed with ambiguous confidence.",
            )

        # 3. Check for Refund-related discrepancy
        if refund and calc.refund_deducted > Decimal("0.0000"):
            if abs(calc.variance) <= Decimal("0.0500"):
                return (
                    ReconStatus.REFUND_RELATED,
                    f"Reconciled via customer refund: {refund.source_id} for {refund.amount} INR against payment gross {calc.gross_amount} INR.",
                )
            else:
                return (
                    ReconStatus.REFUND_RELATED,
                    f"Partial refund exception: refund {refund.source_id} ({refund.amount} INR) does not fully account for variance of {calc.variance} INR.",
                )

        # 4. Check for Chargeback/Dispute-related discrepancy
        if chargeback and calc.chargeback_deducted > Decimal("0.0000"):
            return (
                ReconStatus.CHARGEBACK_RELATED,
                f"Dispute deduction: Chargeback {chargeback.source_id} of {chargeback.amount} INR held against payment {payment.source_id}.",
            )

        # 5. Check for Timing Difference (e.g. weekend or bank batch clearance delay >= 24h)
        if payment and ledger_entry and calc.variance == Decimal("0.0000"):
            time_diff = abs(payment.payment_timestamp - ledger_entry.entry_timestamp)
            if time_diff >= timedelta(hours=24):
                return (
                    ReconStatus.TIMING_DIFFERENCE,
                    f"Timing difference: settled with {time_diff.days} days, {time_diff.seconds // 3600} hours bank clearance delay.",
                )

        # 6. Check Exact Zero-Variance Matched (same-day or within 24h, no fees)
        if calc.variance == Decimal("0.0000") and calc.fee_deducted == Decimal("0.0000") and calc.tax_deducted == Decimal("0.0000"):
            return (
                ReconStatus.MATCHED,
                f"Fully reconciled: payment {payment.source_id} exactly equals ledger amount {ledger_entry.amount} INR.",
            )

        # 7. Check Matched After Fees (within 24h, Fee + Tax explains difference)
        if calc.variance == Decimal("0.0000") and (calc.fee_deducted > Decimal("0.0000") or calc.tax_deducted > Decimal("0.0000")):
            return (
                ReconStatus.MATCHED_AFTER_FEES,
                f"Reconciled after gateway fees: gross {calc.gross_amount} INR - fee {calc.fee_deducted} INR - tax {calc.tax_deducted} INR matches ledger net {calc.actual_amount} INR.",
            )

        # 8. Check for Partial Settlement (e.g. ledger amount is a positive fraction of expected)
        if calc.actual_amount > Decimal("0") and calc.actual_amount < calc.expected_amount:
            pct = (calc.actual_amount / calc.expected_amount) * Decimal("100")
            return (
                ReconStatus.PARTIAL_SETTLEMENT,
                f"Partial settlement: {calc.actual_amount} INR settled out of expected {calc.expected_amount} INR ({pct:.1f}%).",
            )

        # 9. Amount Mismatch (unexplained numerical difference)
        if calc.variance != Decimal("0.0000"):
            return (
                ReconStatus.AMOUNT_MISMATCH,
                f"Amount mismatch: Expected {calc.expected_amount} INR, Actual {calc.actual_amount} INR, Variance {calc.variance} INR.",
            )

        return (
            ReconStatus.UNKNOWN_EXCEPTION,
            f"Unclassified reconciliation exception with variance {calc.variance} INR.",
        )
