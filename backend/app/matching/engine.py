"""Matching Engine Orchestrator for RECON-X.

Coordinates execution across Level 1 (Exact), Level 2 (Composite),
Level 3 (Attribute), and Level 4 (Fuzzy), followed by conflict resolution.
"""
from decimal import Decimal
from typing import Sequence

from app.matching.exact_id import ExactIDMatcher
from app.matching.composite_key import CompositeKeyMatcher
from app.matching.attribute import AttributeMatcher
from app.matching.fuzzy import FuzzyMatcher
from app.matching.conflict_resolver import ConflictResolver
from app.matching.scorer import MatchStatus, ScoredMatch
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry


class MatchingEngine:
    """Deterministic, 4-tier financial transaction matching orchestrator."""

    def __init__(
        self,
        exact_matcher: ExactIDMatcher | None = None,
        composite_matcher: CompositeKeyMatcher | None = None,
        attribute_matcher: AttributeMatcher | None = None,
        fuzzy_matcher: FuzzyMatcher | None = None,
        conflict_resolver: ConflictResolver | None = None,
    ):
        self.exact_matcher = exact_matcher or ExactIDMatcher()
        self.composite_matcher = composite_matcher or CompositeKeyMatcher()
        self.attribute_matcher = attribute_matcher or AttributeMatcher()
        self.fuzzy_matcher = fuzzy_matcher or FuzzyMatcher()
        self.conflict_resolver = conflict_resolver or ConflictResolver()

    def run_matching(
        self,
        payments: Sequence[Payment],
        orders: Sequence[Order] = (),
        ledger_entries: Sequence[LedgerEntry] = (),
        refunds: Sequence[Refund] = (),
        chargebacks: Sequence[Chargeback] = (),
        settlements: Sequence[Settlement] = (),
    ) -> list[ScoredMatch]:
        """
        Executes L1 -> L2 -> L3 -> L4 cascade, resolves conflicts, and generates
        UNMATCHED records for any remaining payments or ledger entries.
        """
        all_matches: list[ScoredMatch] = []
        matched_payment_source_ids: set[str] = set()
        matched_ledger_source_ids: set[str] = set()

        # Tier 1: Exact ID matching
        l1_matches, p1_ids, l1_ids = self.exact_matcher.match_records(
            payments=payments,
            orders=orders,
            ledger_entries=ledger_entries,
            refunds=refunds,
            chargebacks=chargebacks,
            settlements=settlements,
        )
        all_matches.extend(l1_matches)
        matched_payment_source_ids.update(p1_ids)
        matched_ledger_source_ids.update(l1_ids)

        # Filter remaining pools for L2
        rem_payments_l2 = [p for p in payments if p.source_id not in matched_payment_source_ids]
        rem_ledgers_l2 = [l for l in ledger_entries if l.source_id not in matched_ledger_source_ids]

        # Tier 2: Composite key matching (merchant + exact amount + date proximity + customer/receipt)
        if rem_payments_l2 and rem_ledgers_l2:
            l2_matches, p2_ids, l2_ids = self.composite_matcher.match_records(
                unmatched_payments=rem_payments_l2,
                unmatched_ledger_entries=rem_ledgers_l2,
                orders=orders,
            )
            all_matches.extend(l2_matches)
            matched_payment_source_ids.update(p2_ids)
            matched_ledger_source_ids.update(l2_ids)

        # Filter remaining pools for L3
        rem_payments_l3 = [p for p in payments if p.source_id not in matched_payment_source_ids]
        rem_ledgers_l3 = [l for l in ledger_entries if l.source_id not in matched_ledger_source_ids]

        # Tier 3: Attribute matching (amount within fee/tax tolerance or clearing window delay)
        if rem_payments_l3 and rem_ledgers_l3:
            l3_matches, p3_ids, l3_ids = self.attribute_matcher.match_records(
                unmatched_payments=rem_payments_l3,
                unmatched_ledger_entries=rem_ledgers_l3,
            )
            all_matches.extend(l3_matches)
            matched_payment_source_ids.update(p3_ids)
            matched_ledger_source_ids.update(l3_ids)

        # Filter remaining pools for L4
        rem_payments_l4 = [p for p in payments if p.source_id not in matched_payment_source_ids]
        rem_ledgers_l4 = [l for l in ledger_entries if l.source_id not in matched_ledger_source_ids]

        # Tier 4: Fuzzy matching (text similarity + amount proximity)
        if rem_payments_l4 and rem_ledgers_l4:
            l4_matches, p4_ids, l4_ids = self.fuzzy_matcher.match_records(
                unmatched_payments=rem_payments_l4,
                unmatched_ledger_entries=rem_ledgers_l4,
            )
            all_matches.extend(l4_matches)
            matched_payment_source_ids.update(p4_ids)
            matched_ledger_source_ids.update(l4_ids)

        # Conflict Resolution
        resolved_matches = self.conflict_resolver.resolve_conflicts(all_matches)

        # Track completely unmatched payments
        for p in payments:
            if p.source_id not in matched_payment_source_ids:
                resolved_matches.append(
                    ScoredMatch(
                        match_status=MatchStatus.UNMATCHED,
                        confidence=Decimal("0.0000"),
                        reasons=["No matching order, settlement, or ledger record found across L1-L4"],
                        payment_id=p.id,
                        expected_amount=p.amount,
                        actual_amount=None,
                        variance=p.amount,
                        level="UNMATCHED",
                        metadata={"source_id": p.source_id, "entity_type": "payment"},
                    )
                )

        # Track completely unmatched ledger entries (unreconciled merchant deposits / adjustments)
        for l in ledger_entries:
            if l.source_id not in matched_ledger_source_ids:
                resolved_matches.append(
                    ScoredMatch(
                        match_status=MatchStatus.UNMATCHED,
                        confidence=Decimal("0.0000"),
                        reasons=["Orphan ledger entry: No corresponding payment or settlement matched across L1-L4"],
                        ledger_entry_id=l.id,
                        expected_amount=None,
                        actual_amount=l.amount,
                        variance=l.amount,
                        level="UNMATCHED",
                        metadata={"source_id": l.source_id, "entity_type": "ledger_entry"},
                    )
                )

        return resolved_matches
