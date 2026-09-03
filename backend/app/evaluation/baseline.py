"""Naive baseline reconciliation algorithm for benchmark comparison."""
from decimal import Decimal
import time
from typing import Sequence

from app.models.payment import Payment
from app.models.ledger_entry import LedgerEntry


class BaselineMatchResult:
    def __init__(
        self,
        matched_pairs: list[tuple[str, str]],
        unmatched_payments: list[str],
        unmatched_ledgers: list[str],
        processing_time_ms: int,
    ):
        self.matched_pairs = matched_pairs
        self.unmatched_payments = unmatched_payments
        self.unmatched_ledgers = unmatched_ledgers
        self.processing_time_ms = processing_time_ms


class NaiveBaselineReconciler:
    """
    Simulates a traditional rule-based accounting script:
    - Matches only when ledger.reference_id == payment.source_id
    - AND payment.amount == ledger.amount exactly.
    - Fails on fee deductions, bank clearance delays, fuzzy names, or composite keys.
    """

    def reconcile(
        self,
        payments: Sequence[Payment],
        ledger_entries: Sequence[LedgerEntry],
    ) -> BaselineMatchResult:
        start_time = time.perf_counter()

        ledger_by_ref: dict[str, LedgerEntry] = {}
        for l in ledger_entries:
            if l.reference_id:
                ledger_by_ref[l.reference_id] = l

        matched_pairs: list[tuple[str, str]] = []
        matched_payment_ids: set[str] = set()
        matched_ledger_ids: set[str] = set()

        for p in payments:
            if p.source_id in ledger_by_ref:
                ledger = ledger_by_ref[p.source_id]
                # Requires 100% exact gross amount match
                if p.amount == ledger.amount and ledger.source_id not in matched_ledger_ids:
                    matched_pairs.append((p.source_id, ledger.source_id))
                    matched_payment_ids.add(p.source_id)
                    matched_ledger_ids.add(ledger.source_id)

        unmatched_payments = [p.source_id for p in payments if p.source_id not in matched_payment_ids]
        unmatched_ledgers = [l.source_id for l in ledger_entries if l.source_id not in matched_ledger_ids]

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return BaselineMatchResult(
            matched_pairs=matched_pairs,
            unmatched_payments=unmatched_payments,
            unmatched_ledgers=unmatched_ledgers,
            processing_time_ms=elapsed_ms,
        )
