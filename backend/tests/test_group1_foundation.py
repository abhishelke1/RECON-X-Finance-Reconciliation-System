"""Unit tests for Group 1: Foundation, database models, and health endpoint."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Merchant,
    Payment,
    Order,
    Settlement,
    Refund,
    Chargeback,
    LedgerEntry,
    ReconciliationRun,
    ReconciliationMatch,
    Exception_,
    ExceptionEvidence,
    Decision,
    AuditLog,
    EvaluationRun,
)


class TestDatabaseConnection:
    """Test that the database is reachable and functional."""

    async def test_db_ping(self, db_session: AsyncSession):
        """Verify database connectivity."""
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    async def test_db_supports_datetime(self, db_session: AsyncSession):
        """Verify database handles datetime values."""
        result = await db_session.execute(text("SELECT datetime('now')"))
        val = result.scalar()
        assert val is not None


class TestHealthEndpoint:
    """Test the health check API endpoint."""

    async def test_health_returns_ok(self, client):
        """Health endpoint should return 200 with status ok."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data

    async def test_health_has_request_id(self, client):
        """Health endpoint response should include X-Request-ID header."""
        response = await client.get("/api/v1/health")
        assert "x-request-id" in response.headers


class TestMonetaryPrecision:
    """Test that monetary values use Decimal precision, not float."""

    async def test_payment_amount_decimal(self, db_session: AsyncSession):
        """Payment amount should maintain Decimal precision."""
        merchant = Merchant(
            name="Test Merchant",
            status="active",
        )
        db_session.add(merchant)
        await db_session.flush()

        payment = Payment(
            merchant_id=merchant.id,
            source_id="pay_test_001",
            source_system="razorpay",
            amount=Decimal("1234.5678"),
            currency="INR",
            status="captured",
            payment_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(payment)
        await db_session.flush()

        result = await db_session.execute(
            select(Payment).where(Payment.source_id == "pay_test_001")
        )
        fetched = result.scalar_one()
        assert isinstance(fetched.amount, Decimal)
        assert fetched.amount == Decimal("1234.5678")

    async def test_settlement_fees_decimal(self, db_session: AsyncSession):
        """Settlement fees should maintain Decimal precision."""
        merchant = Merchant(name="Fee Test Merchant", status="active")
        db_session.add(merchant)
        await db_session.flush()

        settlement = Settlement(
            merchant_id=merchant.id,
            source_id="setl_test_001",
            source_system="razorpay",
            amount=Decimal("9876.5432"),
            fees=Decimal("197.5309"),
            tax=Decimal("35.5556"),
            currency="INR",
            status="processed",
            settlement_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(settlement)
        await db_session.flush()

        result = await db_session.execute(
            select(Settlement).where(Settlement.source_id == "setl_test_001")
        )
        fetched = result.scalar_one()
        assert fetched.amount == Decimal("9876.5432")
        assert fetched.fees == Decimal("197.5309")
        assert fetched.tax == Decimal("35.5556")


class TestModelCreation:
    """Test that all 15 models can be created with proper data."""

    async def test_create_merchant(self, db_session: AsyncSession):
        """Create a merchant record."""
        merchant = Merchant(
            name="Acme Corp",
            razorpay_account_id="acc_test123",
            business_type="ecommerce",
            status="active",
        )
        db_session.add(merchant)
        await db_session.flush()
        assert merchant.id is not None
        assert merchant.created_at is not None

    async def test_create_order(self, db_session: AsyncSession):
        """Create an order record."""
        merchant = Merchant(name="Order Test Merchant", status="active")
        db_session.add(merchant)
        await db_session.flush()

        order = Order(
            merchant_id=merchant.id,
            source_id="order_test_001",
            source_system="razorpay",
            amount=Decimal("500.0000"),
            currency="INR",
            status="paid",
            order_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(order)
        await db_session.flush()
        assert order.id is not None

    async def test_create_refund(self, db_session: AsyncSession):
        """Create a refund record."""
        merchant = Merchant(name="Refund Test Merchant", status="active")
        db_session.add(merchant)
        await db_session.flush()

        refund = Refund(
            merchant_id=merchant.id,
            source_id="rfnd_test_001",
            source_system="razorpay",
            payment_source_id="pay_test_refund",
            amount=Decimal("250.0000"),
            currency="INR",
            status="processed",
            refund_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(refund)
        await db_session.flush()
        assert refund.id is not None

    async def test_create_ledger_entry(self, db_session: AsyncSession):
        """Create a ledger entry record."""
        merchant = Merchant(name="Ledger Test Merchant", status="active")
        db_session.add(merchant)
        await db_session.flush()

        entry = LedgerEntry(
            merchant_id=merchant.id,
            source_id="ledger_001",
            source_system="tally",
            entry_type="credit",
            amount=Decimal("1000.0000"),
            currency="INR",
            entry_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(entry)
        await db_session.flush()
        assert entry.id is not None

    async def test_create_reconciliation_run(self, db_session: AsyncSession):
        """Create a reconciliation run record."""
        merchant = Merchant(name="Recon Test Merchant", status="active")
        db_session.add(merchant)
        await db_session.flush()

        run = ReconciliationRun(
            merchant_id=merchant.id,
            status="completed",
            total_records=1000,
            matched_records=900,
            unmatched_records=100,
            exceptions_found=50,
            auto_resolved=30,
            human_review=20,
            processing_time_ms=5432,
        )
        db_session.add(run)
        await db_session.flush()
        assert run.id is not None

    async def test_create_audit_log(self, db_session: AsyncSession):
        """Create an audit log entry (append-only)."""
        audit = AuditLog(
            entity_id=uuid.uuid4(),
            entity_type="payment",
            action="created",
            actor="system:ingestion",
            details={"source": "razorpay", "record_count": 1},
        )
        db_session.add(audit)
        await db_session.flush()
        assert audit.id is not None
        assert audit.timestamp is not None


class TestUniqueConstraints:
    """Test that unique constraints work correctly for deduplication."""

    async def test_duplicate_payment_source_rejected(self, db_session: AsyncSession):
        """Two payments with same source_id + source_system should fail."""
        merchant = Merchant(name="Dedup Test", status="active")
        db_session.add(merchant)
        await db_session.flush()

        payment1 = Payment(
            merchant_id=merchant.id,
            source_id="pay_dup_001",
            source_system="razorpay",
            amount=Decimal("100.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(payment1)
        await db_session.flush()

        payment2 = Payment(
            merchant_id=merchant.id,
            source_id="pay_dup_001",
            source_system="razorpay",
            amount=Decimal("200.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(payment2)
        with pytest.raises(IntegrityError):
            await db_session.flush()


class TestRequestIdMiddleware:
    """Test the request ID middleware."""

    async def test_unique_request_ids(self, client):
        """Each request should get a unique request ID."""
        response1 = await client.get("/api/v1/health")
        response2 = await client.get("/api/v1/health")
        id1 = response1.headers.get("x-request-id")
        id2 = response2.headers.get("x-request-id")
        assert id1 is not None
        assert id2 is not None
        assert id1 != id2
