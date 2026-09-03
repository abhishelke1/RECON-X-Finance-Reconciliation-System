"""Level 1 matching: Deterministic exact identifier matching."""
from decimal import Decimal
from typing import Sequence

from app.matching.scorer import MatchStatus, ScoredMatch
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry


class ExactIDMatcher:
    """Performs 100% deterministic matching based on unique system identifiers."""

    def match_records(
        self,
        payments: Sequence[Payment],
        orders: Sequence[Order],
        ledger_entries: Sequence[LedgerEntry],
        refunds: Sequence[Refund] = (),
        chargebacks: Sequence[Chargeback] = (),
        settlements: Sequence[Settlement] = (),
    ) -> tuple[list[ScoredMatch], set[str], set[str]]:
        """
        Matches entities where exact IDs correlate directly:
        - payment.order_source_id == order.source_id
        - ledger.reference_id == payment.source_id or order.source_id or order.receipt
        - refund.payment_source_id == payment.source_id
        - chargeback.payment_source_id == payment.source_id

        Returns:
            (matches, matched_payment_source_ids, matched_ledger_source_ids)
        """
        matches: list[ScoredMatch] = []
        matched_payment_ids: set[str] = set()
        matched_ledger_ids: set[str] = set()

        # Build lookup indices for fast O(1) matching
        order_by_source_id: dict[str, Order] = {o.source_id: o for o in orders if o.source_id}
        order_by_receipt: dict[str, Order] = {o.receipt: o for o in orders if o.receipt}
        
        refunds_by_payment_source: dict[str, list[Refund]] = {}
        for r in refunds:
            if r.payment_source_id:
                refunds_by_payment_source.setdefault(r.payment_source_id, []).append(r)

        chargebacks_by_payment_source: dict[str, list[Chargeback]] = {}
        for c in chargebacks:
            if c.payment_source_id:
                chargebacks_by_payment_source.setdefault(c.payment_source_id, []).append(c)

        # Index ledger entries by reference_id
        ledger_by_ref: dict[str, list[LedgerEntry]] = {}
        for le in ledger_entries:
            if le.reference_id:
                ledger_by_ref.setdefault(le.reference_id, []).append(le)

        for payment in payments:
            reasons: list[str] = []
            matched_order: Order | None = None
            matched_ledger: LedgerEntry | None = None
            matched_refund: Refund | None = None
            matched_chargeback: Chargeback | None = None

            # 1. Match payment to order
            if payment.order_source_id and payment.order_source_id in order_by_source_id:
                matched_order = order_by_source_id[payment.order_source_id]
                reasons.append(f"Exact order_id match: {payment.order_source_id}")

            # 2. Check refunds
            if payment.source_id in refunds_by_payment_source:
                rfnds = refunds_by_payment_source[payment.source_id]
                if rfnds:
                    matched_refund = rfnds[0]
                    reasons.append(f"Exact refund payment_id link: {matched_refund.source_id}")

            # 3. Check chargebacks
            if payment.source_id in chargebacks_by_payment_source:
                cbks = chargebacks_by_payment_source[payment.source_id]
                if cbks:
                    matched_chargeback = cbks[0]
                    reasons.append(f"Exact chargeback payment_id link: {matched_chargeback.source_id}")

            # 4. Match payment to ledger
            # Try payment.source_id (e.g. pay_xxx)
            if payment.source_id in ledger_by_ref:
                cands = [le for le in ledger_by_ref[payment.source_id] if le.source_id not in matched_ledger_ids]
                if cands:
                    matched_ledger = cands[0]
                    reasons.append(f"Exact ledger reference_id match to payment: {payment.source_id}")
            # Or try payment.order_source_id
            elif payment.order_source_id and payment.order_source_id in ledger_by_ref:
                cands = [le for le in ledger_by_ref[payment.order_source_id] if le.source_id not in matched_ledger_ids]
                if cands:
                    matched_ledger = cands[0]
                    reasons.append(f"Exact ledger reference_id match to order: {payment.order_source_id}")
            # Or try order.receipt
            elif matched_order and matched_order.receipt and matched_order.receipt in ledger_by_ref:
                cands = [le for le in ledger_by_ref[matched_order.receipt] if le.source_id not in matched_ledger_ids]
                if cands:
                    matched_ledger = cands[0]
                    reasons.append(f"Exact ledger reference_id match to order receipt: {matched_order.receipt}")

            # If we matched ledger or order or refund/chargeback, form an L1 match
            if matched_ledger or matched_order or matched_refund or matched_chargeback:
                expected = payment.amount
                actual = matched_ledger.amount if matched_ledger else (matched_order.amount if matched_order else payment.amount)
                variance = actual - expected if (actual is not None and expected is not None) else Decimal("0.0000")

                # If matched with ledger, consider it a complete payment-to-ledger match
                if matched_ledger:
                    matched_ledger_ids.add(matched_ledger.source_id)

                matched_payment_ids.add(payment.source_id)

                matches.append(
                    ScoredMatch(
                        match_status=MatchStatus.EXACT,
                        confidence=Decimal("1.0000"),
                        reasons=reasons,
                        payment_id=payment.id,
                        order_id=matched_order.id if matched_order else None,
                        refund_id=matched_refund.id if matched_refund else None,
                        chargeback_id=matched_chargeback.id if matched_chargeback else None,
                        ledger_entry_id=matched_ledger.id if matched_ledger else None,
                        expected_amount=expected,
                        actual_amount=actual,
                        variance=variance,
                        level="L1_EXACT",
                        metadata={"source_id": payment.source_id},
                    )
                )

        return matches, matched_payment_ids, matched_ledger_ids
