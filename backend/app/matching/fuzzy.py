"""Level 4 matching: Fuzzy and probabilistic matching on text similarity, amount proximity, and dates."""
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Sequence

from app.matching.scorer import MatchStatus, ScoredMatch
from app.models.payment import Payment
from app.models.ledger_entry import LedgerEntry


def string_similarity(needle: str | None, haystack: str | None) -> float:
    """
    Computes text similarity supporting both exact sequence ratio
    and sub-phrase / token similarity in financial descriptions.
    """
    if not needle or not haystack:
        return 0.0
    n = needle.strip().lower()
    h = haystack.strip().lower()

    # Direct ratio
    direct_ratio = SequenceMatcher(None, n, h).ratio()
    if direct_ratio >= 0.8:
        return direct_ratio

    # Substring containment
    if n in h:
        return 1.0

    # Token-level similarity: check words of needle against words of haystack
    n_tokens = [t.strip(".,") for t in n.split() if t.strip(".,")]
    h_tokens = [t.strip(".,") for t in h.split() if t.strip(".,")]
    if not n_tokens or not h_tokens:
        return direct_ratio

    token_scores: list[float] = []
    for nt in n_tokens:
        best_sim = 0.0
        for ht in h_tokens:
            sim = SequenceMatcher(None, nt, ht).ratio()
            # Initial match check (e.g. 's' matches 'sharma' or 'sharma' matches 's')
            if (len(ht) == 1 or len(nt) == 1) and nt[0] == ht[0]:
                sim = max(sim, 0.75)
            if sim > best_sim:
                best_sim = sim
        token_scores.append(best_sim)

    avg_token_score = sum(token_scores) / len(token_scores) if token_scores else 0.0
    return max(direct_ratio, avg_token_score)


class FuzzyMatcher:
    """Performs statistical/probabilistic matching using fuzzy string similarity and tolerance gates."""

    def __init__(self, min_similarity: float = 0.65, max_days: int = 14):
        self.min_similarity = min_similarity
        self.time_window = timedelta(days=max_days)

    def match_records(
        self,
        unmatched_payments: Sequence[Payment],
        unmatched_ledger_entries: Sequence[LedgerEntry],
    ) -> tuple[list[ScoredMatch], set[str], set[str]]:
        """
        Calculates similarity between customer/reference text and ledger descriptions,
        evaluating amount proximity and temporal proximity.

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
            best_score = Decimal("0.0")
            best_reasons: list[str] = []

            for ledger in unmatched_ledger_entries:
                if ledger.source_id in matched_ledger_ids:
                    continue

                if payment.merchant_id != ledger.merchant_id:
                    continue

                time_diff = abs(payment.payment_timestamp - ledger.entry_timestamp)
                if time_diff > self.time_window:
                    continue

                # Compare strings: customer name, email, or order_source_id vs ledger description/account
                text_targets = [ledger.description or "", ledger.account_code or "", ledger.reference_id or ""]
                combined_ledger_text = " ".join(text_targets).lower()

                sim_name = string_similarity(payment.customer_name, combined_ledger_text) if payment.customer_name else 0.0
                sim_email = string_similarity(payment.customer_email, combined_ledger_text) if payment.customer_email else 0.0
                sim_ref = string_similarity(payment.source_id, combined_ledger_text)
                sim_order = string_similarity(payment.order_source_id, combined_ledger_text) if payment.order_source_id else 0.0

                max_sim = max(sim_name, sim_email, sim_ref, sim_order)

                # Amount similarity: relative difference
                if payment.amount > Decimal("0"):
                    diff = abs(payment.amount - ledger.amount)
                    pct_diff = diff / payment.amount
                else:
                    pct_diff = Decimal("1.0")

                # If text is significantly similar and amount is close (within 10%)
                if max_sim >= self.min_similarity and pct_diff <= Decimal("0.10"):
                    # Score between 0.5000 and 0.7400
                    base_score = Decimal("0.5000") + (Decimal(str(round(max_sim, 4))) * Decimal("0.1500"))
                    if pct_diff <= Decimal("0.02"):
                        base_score += Decimal("0.0900")

                    score = min(base_score, Decimal("0.7400"))

                    reasons = [
                        f"Fuzzy match: Text similarity {max_sim * 100:.1f}% on customer/reference in description",
                        f"Amount variance: {diff} INR ({pct_diff * 100:.2f}%)",
                        f"Time difference: {time_diff.days} days",
                    ]

                    if score > best_score:
                        best_score = score
                        best_candidate = ledger
                        best_reasons = reasons

            if best_candidate and best_score >= Decimal("0.5000"):
                matched_payment_ids.add(payment.source_id)
                matched_ledger_ids.add(best_candidate.source_id)

                matches.append(
                    ScoredMatch(
                        match_status=MatchStatus.POSSIBLE,
                        confidence=best_score,
                        reasons=best_reasons,
                        payment_id=payment.id,
                        ledger_entry_id=best_candidate.id,
                        expected_amount=payment.amount,
                        actual_amount=best_candidate.amount,
                        variance=best_candidate.amount - payment.amount,
                        level="L4_FUZZY",
                        metadata={
                            "payment_source_id": payment.source_id,
                            "ledger_source_id": best_candidate.source_id,
                        },
                    )
                )

        return matches, matched_payment_ids, matched_ledger_ids
