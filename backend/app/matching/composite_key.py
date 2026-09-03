"""Level 2 matching: Composite key matching (merchant + exact amount + date proximity + customer/reference)."""
from datetime import timedelta
from decimal import Decimal
from typing import Sequence

from app.matching.scorer import MatchStatus, ScoredMatch
from app.models.payment import Payment
from app.models.ledger_entry import LedgerEntry
from app.models.order import Order


class CompositeKeyMatcher:
    """Matches unmatched records using multi-attribute composite keys with strict constraints."""

    def __init__(self, time_window_hours: int = 48):
        self.time_window = timedelta(hours=time_window_hours)

    def match_records(
        self,
        unmatched_payments: Sequence[Payment],
        unmatched_ledger_entries: Sequence[LedgerEntry],
        orders: Sequence[Order] = (),
    ) -> tuple[list[ScoredMatch], set[str], set[str]]:
        """
        Attempts to match remaining payments with ledger entries based on:
        1. Identical merchant_id
        2. Exact amount (to 4 decimal places)
        3. Transaction timestamps within allowable window (default 48 hours)
        4. Customer contact / description correlation

        Returns:
            (matches, new_matched_payment_ids, new_matched_ledger_ids)
        """
        matches: list[ScoredMatch] = []
        matched_payment_ids: set[str] = set()
        matched_ledger_ids: set[str] = set()

        order_by_source_id = {o.source_id: o for o in orders if o.source_id}

        # Candidate ledger entries pool
        available_ledgers = [l for l in unmatched_ledger_entries]

        for payment in unmatched_payments:
            if payment.source_id in matched_payment_ids:
                continue

            best_candidate: LedgerEntry | None = None
            candidate_reasons: list[str] = []
            highest_score = Decimal("0.0")

            for ledger in available_ledgers:
                if ledger.source_id in matched_ledger_ids:
                    continue

                if payment.merchant_id != ledger.merchant_id:
                    continue

                # Condition 1: Exact Amount Match
                if payment.amount != ledger.amount:
                    continue

                # Condition 2: Date Window check
                time_diff = abs(payment.payment_timestamp - ledger.entry_timestamp)
                if time_diff > self.time_window:
                    continue

                # Base score for exact amount within date window
                score = Decimal("0.9000")
                reasons = [
                    f"Composite key: Exact amount {payment.amount} INR",
                    f"Date proximity: {time_diff.total_seconds() / 3600:.1f} hours apart (limit {self.time_window.total_seconds() / 3600}h)",
                ]

                # Secondary bonus: customer info or description matching
                desc = (ledger.description or "").lower()
                matched_secondary = False

                if payment.customer_email and payment.customer_email.lower() in desc:
                    score += Decimal("0.0500")
                    reasons.append(f"Customer email found in ledger description: {payment.customer_email}")
                    matched_secondary = True

                if payment.customer_phone and payment.customer_phone in desc:
                    score += Decimal("0.0500")
                    reasons.append(f"Customer phone found in ledger description: {payment.customer_phone}")
                    matched_secondary = True

                if payment.order_source_id and payment.order_source_id.lower() in desc:
                    score += Decimal("0.0500")
                    reasons.append(f"Order ID embedded in ledger description: {payment.order_source_id}")
                    matched_secondary = True

                # Prefer candidate with highest score, or closest timestamp
                if score > highest_score:
                    highest_score = min(score, Decimal("0.9500"))
                    best_candidate = ledger
                    candidate_reasons = reasons

            if best_candidate and highest_score >= Decimal("0.9000"):
                matched_payment_ids.add(payment.source_id)
                matched_ledger_ids.add(best_candidate.source_id)

                # Link order if available
                matched_order = order_by_source_id.get(payment.order_source_id) if payment.order_source_id else None

                matches.append(
                    ScoredMatch(
                        match_status=MatchStatus.HIGH_CONFIDENCE,
                        confidence=highest_score,
                        reasons=candidate_reasons,
                        payment_id=payment.id,
                        order_id=matched_order.id if matched_order else None,
                        ledger_entry_id=best_candidate.id,
                        expected_amount=payment.amount,
                        actual_amount=best_candidate.amount,
                        variance=best_candidate.amount - payment.amount,
                        level="L2_COMPOSITE",
                        metadata={
                            "payment_source_id": payment.source_id,
                            "ledger_source_id": best_candidate.source_id,
                        },
                    )
                )

        return matches, matched_payment_ids, matched_ledger_ids
