"""Tests for Group 3: Transaction Matching Engine (L1 to L4, Scoring, Conflict Resolution)."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid

import pytest

from app.models.payment import Payment
from app.models.order import Order
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.matching.scorer import MatchStatus, ScoredMatch, compute_confidence_status
from app.matching.exact_id import ExactIDMatcher
from app.matching.composite_key import CompositeKeyMatcher
from app.matching.attribute import AttributeMatcher
from app.matching.fuzzy import FuzzyMatcher
from app.matching.conflict_resolver import ConflictResolver
from app.matching.engine import MatchingEngine


@pytest.fixture
def merchant_id():
    return uuid.uuid4()


@pytest.fixture
def base_time():
    return datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestScorer:
    """Tests for confidence scoring and status computation."""

    def test_compute_confidence_status(self):
        assert compute_confidence_status(Decimal("1.0000")) == MatchStatus.EXACT
        assert compute_confidence_status(Decimal("0.9900")) == MatchStatus.EXACT
        assert compute_confidence_status(Decimal("0.9200")) == MatchStatus.HIGH_CONFIDENCE
        assert compute_confidence_status(Decimal("0.8500")) == MatchStatus.HIGH_CONFIDENCE
        assert compute_confidence_status(Decimal("0.7000")) == MatchStatus.POSSIBLE
        assert compute_confidence_status(Decimal("0.4900")) == MatchStatus.UNMATCHED


class TestLevel1ExactMatching:
    """Tests for Level 1 exact identifier matching."""

    def test_exact_payment_to_order_match(self, merchant_id, base_time):
        matcher = ExactIDMatcher()

        payment = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="pay_001",
            source_system="razorpay",
            order_source_id="order_001",
            amount=Decimal("1500.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        order = Order(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="order_001",
            source_system="razorpay",
            amount=Decimal("1500.0000"),
            currency="INR",
            status="paid",
            order_timestamp=base_time - timedelta(minutes=5),
        )

        matches, p_ids, l_ids = matcher.match_records(
            payments=[payment],
            orders=[order],
            ledger_entries=[],
        )

        assert len(matches) == 1
        m = matches[0]
        assert m.match_status == MatchStatus.EXACT
        assert m.confidence == Decimal("1.0000")
        assert m.level == "L1_EXACT"
        assert m.payment_id == payment.id
        assert m.order_id == order.id
        assert "Exact order_id match: order_001" in m.reasons
        assert "pay_001" in p_ids

    def test_exact_payment_to_ledger_by_reference(self, merchant_id, base_time):
        matcher = ExactIDMatcher()

        payment = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="pay_002",
            source_system="razorpay",
            amount=Decimal("2000.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        ledger = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="led_002",
            source_system="erp",
            entry_type="credit",
            amount=Decimal("2000.0000"),
            currency="INR",
            reference_id="pay_002",
            entry_timestamp=base_time + timedelta(hours=1),
        )

        matches, p_ids, l_ids = matcher.match_records(
            payments=[payment],
            orders=[],
            ledger_entries=[ledger],
        )

        assert len(matches) == 1
        m = matches[0]
        assert m.match_status == MatchStatus.EXACT
        assert m.confidence == Decimal("1.0000")
        assert m.payment_id == payment.id
        assert m.ledger_entry_id == ledger.id
        assert "pay_002" in p_ids
        assert "led_002" in l_ids


class TestLevel2CompositeKeyMatching:
    """Tests for Level 2 composite key matching."""

    def test_composite_match_exact_amount_and_customer_phone(self, merchant_id, base_time):
        matcher = CompositeKeyMatcher(time_window_hours=48)

        payment = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="pay_comp_1",
            source_system="razorpay",
            amount=Decimal("4999.0000"),
            currency="INR",
            status="captured",
            customer_phone="+919876543210",
            payment_timestamp=base_time,
        )
        ledger = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="led_comp_1",
            source_system="tally",
            entry_type="credit",
            amount=Decimal("4999.0000"),
            currency="INR",
            description="UPI credit received from +919876543210",
            entry_timestamp=base_time + timedelta(hours=4),
        )

        matches, p_ids, l_ids = matcher.match_records(
            unmatched_payments=[payment],
            unmatched_ledger_entries=[ledger],
        )

        assert len(matches) == 1
        m = matches[0]
        assert m.match_status == MatchStatus.HIGH_CONFIDENCE
        assert m.confidence >= Decimal("0.9000")
        assert m.level == "L2_COMPOSITE"
        assert m.payment_id == payment.id
        assert m.ledger_entry_id == ledger.id


class TestLevel3AttributeMatching:
    """Tests for Level 3 attribute matching (fees, net settlements, clearing window)."""

    def test_attribute_match_net_settlement_after_fee(self, merchant_id, base_time):
        matcher = AttributeMatcher(max_days_window=7)

        # Gross 10,000 INR, Fee 200 INR, Tax 36 INR => Expected Net = 9,764 INR
        payment = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="pay_attr_1",
            source_system="razorpay",
            amount=Decimal("10000.0000"),
            fee=Decimal("200.0000"),
            tax=Decimal("36.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        ledger = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="led_attr_1",
            source_system="bank_statement",
            entry_type="credit",
            amount=Decimal("9764.0000"),
            currency="INR",
            description="Razorpay payout net credit",
            entry_timestamp=base_time + timedelta(days=2),
        )

        matches, p_ids, l_ids = matcher.match_records(
            unmatched_payments=[payment],
            unmatched_ledger_entries=[ledger],
        )

        assert len(matches) == 1
        m = matches[0]
        assert m.level == "L3_ATTRIBUTE"
        assert m.confidence >= Decimal("0.8500")
        assert m.payment_id == payment.id
        assert m.ledger_entry_id == ledger.id


class TestLevel4FuzzyMatching:
    """Tests for Level 4 probabilistic / fuzzy matching."""

    def test_fuzzy_match_customer_name(self, merchant_id, base_time):
        matcher = FuzzyMatcher(min_similarity=0.65)

        payment = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="pay_fuz_1",
            source_system="razorpay",
            customer_name="Siddharth Sharma",
            amount=Decimal("3500.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        ledger = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="led_fuz_1",
            source_system="erp",
            entry_type="credit",
            amount=Decimal("3500.0000"),
            currency="INR",
            description="Invoice payment recvd Siddharth S",
            entry_timestamp=base_time + timedelta(days=1),
        )

        matches, p_ids, l_ids = matcher.match_records(
            unmatched_payments=[payment],
            unmatched_ledger_entries=[ledger],
        )

        assert len(matches) == 1
        m = matches[0]
        assert m.match_status == MatchStatus.POSSIBLE
        assert Decimal("0.5000") <= m.confidence <= Decimal("0.7400")
        assert m.level == "L4_FUZZY"


class TestConflictResolution:
    """Tests for conflict detection and ambiguity resolution."""

    def test_competing_matches_resolved_or_flagged_conflict(self, merchant_id):
        resolver = ConflictResolver()
        ledger_id = uuid.uuid4()

        p1_id = uuid.uuid4()
        p2_id = uuid.uuid4()

        # Two matches claiming the same ledger entry with identical confidence
        m1 = ScoredMatch(
            match_status=MatchStatus.HIGH_CONFIDENCE,
            confidence=Decimal("0.9000"),
            payment_id=p1_id,
            ledger_entry_id=ledger_id,
            reasons=["Match 1"],
        )
        m2 = ScoredMatch(
            match_status=MatchStatus.HIGH_CONFIDENCE,
            confidence=Decimal("0.9000"),
            payment_id=p2_id,
            ledger_entry_id=ledger_id,
            reasons=["Match 2"],
        )

        resolved = resolver.resolve_conflicts([m1, m2])
        assert len(resolved) == 2
        # Both must be flagged as CONFLICT due to equal score ambiguity
        assert all(m.match_status == MatchStatus.CONFLICT for m in resolved)


class TestMatchingEngineOrchestration:
    """Tests for end-to-end cascading multi-tier matching engine."""

    def test_full_pipeline_cascading_and_unmatched(self, merchant_id, base_time):
        engine = MatchingEngine()

        # 1. P1 will match L1 with Order 1 & Ledger 1
        p1 = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="p1",
            source_system="razorpay",
            order_source_id="o1",
            amount=Decimal("100.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        o1 = Order(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="o1",
            source_system="razorpay",
            amount=Decimal("100.0000"),
            currency="INR",
            status="paid",
            order_timestamp=base_time,
        )
        l1 = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="l1",
            source_system="erp",
            reference_id="p1",
            entry_type="credit",
            amount=Decimal("100.0000"),
            currency="INR",
            entry_timestamp=base_time,
        )

        # 2. P2 will match L2 via composite key (amount + customer phone)
        p2 = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="p2",
            source_system="razorpay",
            amount=Decimal("500.0000"),
            currency="INR",
            status="captured",
            customer_phone="9998887770",
            payment_timestamp=base_time,
        )
        l2 = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="l2",
            source_system="erp",
            entry_type="credit",
            amount=Decimal("500.0000"),
            currency="INR",
            description="Cust 9998887770 deposit",
            entry_timestamp=base_time + timedelta(hours=2),
        )

        # 3. P3 is unmatched (no ledger or order)
        p3 = Payment(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="p3",
            source_system="razorpay",
            amount=Decimal("777.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )

        # 4. L4 is an orphan ledger entry
        l4 = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            source_id="l4",
            source_system="erp",
            entry_type="credit",
            amount=Decimal("9999.0000"),
            currency="INR",
            entry_timestamp=base_time,
        )

        results = engine.run_matching(
            payments=[p1, p2, p3],
            orders=[o1],
            ledger_entries=[l1, l2, l4],
        )

        # We expect 4 total records:
        # - L1 match for p1
        # - L2 match for p2
        # - UNMATCHED for p3
        # - UNMATCHED for l4
        assert len(results) == 4

        statuses = {r.level: r.match_status for r in results}
        assert statuses.get("L1_EXACT") == MatchStatus.EXACT
        assert statuses.get("L2_COMPOSITE") == MatchStatus.HIGH_CONFIDENCE

        unmatched_results = [r for r in results if r.match_status == MatchStatus.UNMATCHED]
        assert len(unmatched_results) == 2
