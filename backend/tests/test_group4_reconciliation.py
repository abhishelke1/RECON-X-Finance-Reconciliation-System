"""Tests for Group 4: Reconciliation Engine (Calculator, Classifier, Exceptions, Run Orchestrator, API)."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.models.reconciliation import ReconciliationRun, ReconciliationMatch
from app.models.exception import Exception_, ExceptionEvidence
from app.models.audit_log import AuditLog

from app.matching.scorer import MatchStatus, ScoredMatch
from app.reconciliation.calculator import ReconciliationCalculator
from app.reconciliation.classifier import ReconciliationClassifier, ReconStatus
from app.reconciliation.exception_generator import ExceptionGenerator
from app.reconciliation.engine import ReconciliationEngine


@pytest.fixture
def merchant_id():
    return uuid.uuid4()


@pytest.fixture
def base_time():
    return datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)


class TestReconciliationCalculator:
    """Tests for exact financial calculations."""

    def test_calculate_net_with_fees_and_taxes(self, merchant_id, base_time):
        payment = Payment(
            merchant_id=merchant_id,
            source_id="p1",
            source_system="razorpay",
            amount=Decimal("1000.0000"),
            fee=Decimal("20.0000"),
            tax=Decimal("3.6000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        ledger = LedgerEntry(
            merchant_id=merchant_id,
            source_id="l1",
            source_system="erp",
            amount=Decimal("976.4000"),
            currency="INR",
            entry_type="credit",
            entry_timestamp=base_time,
        )

        res = ReconciliationCalculator.calculate(payment=payment, ledger_entry=ledger)
        assert res.gross_amount == Decimal("1000.0000")
        assert res.fee_deducted == Decimal("20.0000")
        assert res.tax_deducted == Decimal("3.6000")
        assert res.expected_amount == Decimal("976.4000")
        assert res.actual_amount == Decimal("976.4000")
        assert res.variance == Decimal("0.0000")

    def test_calculate_with_refund_and_dispute(self, merchant_id, base_time):
        payment = Payment(
            merchant_id=merchant_id,
            source_id="p2",
            source_system="razorpay",
            amount=Decimal("5000.0000"),
            fee=Decimal("100.0000"),
            tax=Decimal("18.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        refund = Refund(
            merchant_id=merchant_id,
            source_id="rfnd1",
            source_system="razorpay",
            payment_source_id="p2",
            amount=Decimal("500.0000"),
            currency="INR",
            status="processed",
            refund_timestamp=base_time,
        )
        chargeback = Chargeback(
            merchant_id=merchant_id,
            source_id="disp1",
            source_system="razorpay",
            payment_source_id="p2",
            amount=Decimal("1000.0000"),
            currency="INR",
            status="open",
            chargeback_timestamp=base_time,
        )
        # Expected = 5000 - 100 - 18 - 500 - 1000 = 3382.0000
        ledger = LedgerEntry(
            merchant_id=merchant_id,
            source_id="l2",
            source_system="erp",
            amount=Decimal("3382.0000"),
            currency="INR",
            entry_type="credit",
            entry_timestamp=base_time,
        )

        res = ReconciliationCalculator.calculate(
            payment=payment,
            ledger_entry=ledger,
            refund=refund,
            chargeback=chargeback,
        )
        assert res.expected_amount == Decimal("3382.0000")
        assert res.variance == Decimal("0.0000")


class TestReconciliationClassifier:
    """Tests for 10-state classification logic."""

    def test_classify_matched_and_matched_after_fees(self, merchant_id, base_time):
        classifier = ReconciliationClassifier()

        p1 = Payment(merchant_id=merchant_id, source_id="p1", source_system="razorpay", amount=Decimal("100.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        l1 = LedgerEntry(merchant_id=merchant_id, source_id="l1", source_system="erp", amount=Decimal("100.0000"), currency="INR", entry_type="credit", entry_timestamp=base_time)
        match1 = ScoredMatch(match_status=MatchStatus.EXACT, confidence=Decimal("1.0000"))
        calc1 = ReconciliationCalculator.calculate(payment=p1, ledger_entry=l1)

        status1, reason1 = classifier.classify(match=match1, calc=calc1, payment=p1, ledger_entry=l1)
        assert status1 == ReconStatus.MATCHED

        # After fees
        p2 = Payment(merchant_id=merchant_id, source_id="p2", source_system="razorpay", amount=Decimal("100.0000"), fee=Decimal("2.0000"), tax=Decimal("0.3600"), currency="INR", status="captured", payment_timestamp=base_time)
        l2 = LedgerEntry(merchant_id=merchant_id, source_id="l2", source_system="erp", amount=Decimal("97.6400"), currency="INR", entry_type="credit", entry_timestamp=base_time)
        match2 = ScoredMatch(match_status=MatchStatus.EXACT, confidence=Decimal("1.0000"))
        calc2 = ReconciliationCalculator.calculate(payment=p2, ledger_entry=l2)

        status2, reason2 = classifier.classify(match=match2, calc=calc2, payment=p2, ledger_entry=l2)
        assert status2 == ReconStatus.MATCHED_AFTER_FEES

    def test_classify_timing_difference(self, merchant_id, base_time):
        classifier = ReconciliationClassifier()
        p = Payment(merchant_id=merchant_id, source_id="p_td", source_system="razorpay", amount=Decimal("500.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        # Cleared 3 days later
        l = LedgerEntry(merchant_id=merchant_id, source_id="l_td", source_system="erp", amount=Decimal("500.0000"), currency="INR", entry_type="credit", entry_timestamp=base_time + timedelta(days=3))
        match = ScoredMatch(match_status=MatchStatus.EXACT, confidence=Decimal("1.0000"))
        calc = ReconciliationCalculator.calculate(payment=p, ledger_entry=l)

        status, reason = classifier.classify(match=match, calc=calc, payment=p, ledger_entry=l)
        assert status == ReconStatus.TIMING_DIFFERENCE
        assert "bank clearance delay" in reason

    def test_classify_partial_settlement(self, merchant_id, base_time):
        classifier = ReconciliationClassifier()
        p = Payment(merchant_id=merchant_id, source_id="p_ps", source_system="razorpay", amount=Decimal("1000.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        l = LedgerEntry(merchant_id=merchant_id, source_id="l_ps", source_system="erp", amount=Decimal("400.0000"), currency="INR", entry_type="credit", entry_timestamp=base_time)
        match = ScoredMatch(match_status=MatchStatus.POSSIBLE, confidence=Decimal("0.7000"))
        calc = ReconciliationCalculator.calculate(payment=p, ledger_entry=l)

        status, reason = classifier.classify(match=match, calc=calc, payment=p, ledger_entry=l)
        assert status == ReconStatus.PARTIAL_SETTLEMENT

    def test_classify_missing_record(self, merchant_id, base_time):
        classifier = ReconciliationClassifier()
        p = Payment(merchant_id=merchant_id, source_id="p_mis", source_system="razorpay", amount=Decimal("800.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        match = ScoredMatch(match_status=MatchStatus.UNMATCHED, confidence=Decimal("0.0000"))
        calc = ReconciliationCalculator.calculate(payment=p, ledger_entry=None)

        status, reason = classifier.classify(match=match, calc=calc, payment=p, ledger_entry=None)
        assert status == ReconStatus.MISSING_RECORD


class TestExceptionGenerator:
    """Tests for exception and evidence generation."""

    def test_create_exception_with_evidence(self, merchant_id, base_time):
        generator = ExceptionGenerator()

        run = ReconciliationRun(id=uuid.uuid4(), merchant_id=merchant_id, status="running")
        match = ReconciliationMatch(id=uuid.uuid4(), run_id=run.id, match_status="EXACT", match_confidence=Decimal("1.0"), recon_status="AMOUNT_MISMATCH")
        p = Payment(id=uuid.uuid4(), merchant_id=merchant_id, source_id="p_err", source_system="razorpay", amount=Decimal("12000.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        l = LedgerEntry(id=uuid.uuid4(), merchant_id=merchant_id, source_id="l_err", source_system="erp", amount=Decimal("10000.0000"), currency="INR", entry_type="credit", entry_timestamp=base_time)

        calc = ReconciliationCalculator.calculate(payment=p, ledger_entry=l)
        exc, evidence = generator.create_exception(
            run=run,
            match=match,
            recon_status=ReconStatus.AMOUNT_MISMATCH,
            explanation="Variance of -2000 INR detected",
            calc=calc,
            payment=p,
            ledger_entry=l,
        )

        assert exc.run_id == run.id
        assert exc.severity == "high"  # > 5000 INR
        assert exc.amount_involved == Decimal("12000.0000")
        assert exc.variance == Decimal("-2000.0000")

        evidence_types = [ev.evidence_type for ev in evidence]
        assert "calculation" in evidence_types
        assert "payment" in evidence_types
        assert "ledger" in evidence_types


class TestReconciliationEngineIntegration:
    """Full database integration test for ReconciliationEngine."""

    async def test_end_to_end_reconciliation_run(self, db_session: AsyncSession, merchant_id, base_time):
        # 1. Create merchant
        merchant = Merchant(id=merchant_id, name="Recon Merchant", status="active")
        db_session.add(merchant)
        await db_session.flush()

        # 2. Add sample transactions:
        # P1 & L1: Matched
        p1 = Payment(id=uuid.uuid4(), merchant_id=merchant_id, source_id="pay_int_1", source_system="razorpay", amount=Decimal("1500.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        l1 = LedgerEntry(id=uuid.uuid4(), merchant_id=merchant_id, source_id="led_int_1", source_system="erp", reference_id="pay_int_1", amount=Decimal("1500.0000"), currency="INR", entry_type="credit", entry_timestamp=base_time)

        # P2: Orphan Payment (Missing Record)
        p2 = Payment(id=uuid.uuid4(), merchant_id=merchant_id, source_id="pay_int_2", source_system="razorpay", amount=Decimal("3000.0000"), currency="INR", status="captured", payment_timestamp=base_time)

        db_session.add_all([p1, l1, p2])
        await db_session.commit()

        # 3. Execute run
        engine = ReconciliationEngine()
        run = await engine.run_reconciliation(db=db_session, merchant_id=merchant_id)

        assert run.status == "completed"
        assert run.total_records == 3  # 2 payments + 1 ledger entry
        assert run.matched_records >= 1
        assert run.exceptions_found >= 1  # P2 is missing in ledger
        assert run.processing_time_ms is not None

        # Verify audit log was recorded
        audit_res = await db_session.execute(
            select(AuditLog).where(AuditLog.entity_id == run.id)
        )
        audit_entry = audit_res.scalar_one_or_none()
        assert audit_entry is not None
        assert audit_entry.action == "reconciliation_completed"


class TestReconciliationAPI:
    """Tests for Reconciliation REST endpoints."""

    async def test_trigger_and_get_reconciliation_run(self, client: AsyncClient, db_session: AsyncSession, base_time):
        # Create merchant
        merchant = Merchant(name="API Recon Test", status="active")
        db_session.add(merchant)
        await db_session.commit()
        await db_session.refresh(merchant)

        # Add a payment
        p = Payment(merchant_id=merchant.id, source_id="pay_api_1", source_system="razorpay", amount=Decimal("250.0000"), currency="INR", status="captured", payment_timestamp=base_time)
        db_session.add(p)
        await db_session.commit()

        # POST /reconciliation/run
        resp = await client.post(
            "/api/v1/reconciliation/run",
            json={"merchant_id": str(merchant.id)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "completed"
        assert data["total_records"] >= 1
        run_id = data["id"]

        # GET /reconciliation/{run_id}
        get_resp = await client.get(f"/api/v1/reconciliation/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == run_id

        # GET /reconciliation?merchant_id=...
        list_resp = await client.get(f"/api/v1/reconciliation?merchant_id={merchant.id}")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

        # GET /reconciliation/{run_id}/matches
        matches_resp = await client.get(f"/api/v1/reconciliation/{run_id}/matches")
        assert matches_resp.status_code == 200
        assert isinstance(matches_resp.json(), list)
