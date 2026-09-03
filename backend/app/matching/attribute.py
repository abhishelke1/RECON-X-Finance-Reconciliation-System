"""Level 3 matching: Strong attribute matching (amount within fee tolerance, settlement clearing window)."""
from datetime import timedelta
from decimal import Decimal
from typing import Sequence

from app.matching.scorer import MatchStatus, ScoredMatch
from app.models.payment import Payment
from app.models.ledger_entry import LedgerEntry


class AttributeMatcher:
    """Matches transactions where amounts differ by fee deductions or timestamps span clearing windows."""

    def __init__(self, max_days_window: int = 7, max_fee_pct: Decimal = Decimal("0.05")):
        self.time_window = timedelta(days=max_days_window)
        self.max_fee_pct = max_fee_pct

    def match_records(
        self,
        unmatched_payments: Sequence[Payment],
        unmatched_ledger_entries: Sequence[LedgerEntry],
    ) -> tuple[list[ScoredMatch], set[str], set[str]]:
        """
        Attempts to match when:
        1. Net amount (Payment Gross - Fee - Tax) == Ledger Amount (within 0.05 tolerance)
        2. Exact amount across an extended bank clearing window (e.g., T+2 or weekend delays up to 7 days)
        3. Variance is within reasonable gateway MDR fee range (<= 5%)

        Returns:
            (matches, new_matched_payment_ids, new_matched_ledger_ids)
        """
        matches: list[ScoredMatch] = []
        matched_payment_ids: set[str] = set()
        matched_ledger_ids: set[str] = set()

        for payment in unmatched_payments:
            if payment.source_id in matched_payment_ids:
                continue

            best_candidate: LedgerEntry | None = None
            best_reasons: list[str] = []
            best_score = Decimal("0.0")

            # Calculate expected net if fees are known
            net_amount = payment.amount
            if payment.fee is not None:
                net_amount -= payment.fee
                if payment.tax is not None:
                    net_amount -= payment.tax

            for ledger in unmatched_ledger_entries:
                if ledger.source_id in matched_ledger_ids:
                    continue

                if payment.merchant_id != ledger.merchant_id:
                    continue

                time_diff = abs(payment.payment_timestamp - ledger.entry_timestamp)
                if time_diff > self.time_window:
                    continue

                diff = abs(payment.amount - ledger.amount)
                net_diff = abs(net_amount - ledger.amount)

                # Scenario A: Ledger recorded Net Settlement Amount (Gross - Fee - Tax)
                if payment.fee is not None and net_diff <= Decimal("0.0500"):
                    score = Decimal("0.8800")
                    reasons = [
                        f"Attribute match: Ledger amount {ledger.amount} matches Payment net {net_amount} (fee={payment.fee}, tax={payment.tax})",
                        f"Timing difference: {time_diff.days} days, {time_diff.seconds // 3600} hours",
                    ]
                    if score > best_score:
                        best_score = score
                        best_candidate = ledger
                        best_reasons = reasons
                    continue

                # Scenario B: Exact amount but wider bank settlement clearing delay (up to 7 days)
                if diff == Decimal("0.0000") and time_diff > timedelta(hours=48):
                    score = Decimal("0.8500")
                    reasons = [
                        f"Attribute match: Exact amount {payment.amount} INR across extended clearing delay",
                        f"Cleared in {time_diff.days} days, {time_diff.seconds // 3600} hours",
                    ]
                    if score > best_score:
                        best_score = score
                        best_candidate = ledger
                        best_reasons = reasons
                    continue

                # Scenario C: Amount differs within standard gateway MDR fee bounds (<= 3%)
                if payment.amount > Decimal("0") and (diff / payment.amount) <= self.max_fee_pct:
                    fee_pct = (diff / payment.amount) * Decimal("100")
                    score = Decimal("0.7800")
                    reasons = [
                        f"Attribute match: Amount variance {diff} INR ({fee_pct:.2f}%) within standard fee tolerance",
                        f"Timestamp delta: {time_diff.days} days",
                    ]
                    if score > best_score:
                        best_score = score
                        best_candidate = ledger
                        best_reasons = reasons

            if best_candidate and best_score >= Decimal("0.7500"):
                matched_payment_ids.add(payment.source_id)
                matched_ledger_ids.add(best_candidate.source_id)

                matches.append(
                    ScoredMatch(
                        match_status=MatchStatus.HIGH_CONFIDENCE if best_score >= Decimal("0.85") else MatchStatus.POSSIBLE,
                        confidence=best_score,
                        reasons=best_reasons,
                        payment_id=payment.id,
                        ledger_entry_id=best_candidate.id,
                        expected_amount=payment.amount,
                        actual_amount=best_candidate.amount,
                        variance=best_candidate.amount - payment.amount,
                        level="L3_ATTRIBUTE",
                        metadata={
                            "payment_source_id": payment.source_id,
                            "ledger_source_id": best_candidate.source_id,
                            "net_amount": str(net_amount),
                        },
                    )
                )

        return matches, matched_payment_ids, matched_ledger_ids
