"""Tests for Group 2: Data Ingestion & Normalization."""
import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.ingestion.normalizer import (
    normalize_razorpay_amount,
    normalize_timestamp,
    normalize_currency,
    normalize_string,
    normalize_razorpay_payment,
)
from app.ingestion.validators import (
    PaymentImportRecord,
    SettlementImportRecord,
    LedgerEntryImportRecord,
    ImportResult,
)
from app.ingestion.razorpay_client import MockRazorpayClient, get_razorpay_client


class TestNormalizer:
    """Test the normalizer utilities."""

    def test_paise_to_inr_conversion(self):
        """100000 paise should become 1000.00 INR."""
        result = normalize_razorpay_amount(100000)
        assert result == Decimal("1000.00")
        assert isinstance(result, Decimal)

    def test_paise_conversion_precision(self):
        """2360 paise should become 23.60 INR with exact precision."""
        result = normalize_razorpay_amount(2360)
        assert result == Decimal("23.60")

    def test_paise_conversion_none(self):
        """None input should return None."""
        assert normalize_razorpay_amount(None) is None

    def test_paise_conversion_string(self):
        """String input should be handled."""
        result = normalize_razorpay_amount("5000")
        assert result == Decimal("50.00")

    def test_normalize_timestamp_epoch(self):
        """Unix epoch timestamp should convert to UTC datetime."""
        result = normalize_timestamp(1672531200)
        assert result is not None
        assert result.tzinfo is not None

    def test_normalize_timestamp_iso(self):
        """ISO string should parse correctly."""
        result = normalize_timestamp("2023-01-01T00:00:00Z")
        assert result is not None
        assert result.year == 2023

    def test_normalize_timestamp_none(self):
        """None should return None."""
        assert normalize_timestamp(None) is None

    def test_normalize_currency_default(self):
        """None currency should default to INR."""
        assert normalize_currency(None) == "INR"

    def test_normalize_currency_uppercase(self):
        """Currency should be uppercased."""
        assert normalize_currency("inr") == "INR"

    def test_normalize_string_strip(self):
        """Strings should be stripped and lowercased."""
        assert normalize_string("  Captured ") == "captured"

    def test_normalize_string_none(self):
        """None should return None."""
        assert normalize_string(None) is None


class TestNormalizeRazorpayPayment:
    """Test the full Razorpay payment normalization."""

    def test_normalize_payment(self):
        """A Razorpay payment dict should normalize correctly."""
        raw = {
            "id": "pay_test123",
            "amount": 100000,
            "currency": "INR",
            "status": "captured",
            "method": "card",
            "email": "test@example.com",
            "contact": "+919999999999",
            "fee": 2000,
            "tax": 360,
            "order_id": "order_test123",
            "created_at": 1672531200,
        }
        result = normalize_razorpay_payment(raw)

        assert result["source_id"] == "pay_test123"
        assert result["source_system"] == "razorpay"
        assert result["amount"] == Decimal("1000.00")
        assert result["fee"] == Decimal("20.00")
        assert result["tax"] == Decimal("3.60")
        assert result["status"] == "captured"
        assert result["order_source_id"] == "order_test123"
        assert result["raw_data"] is raw  # raw data preserved


class TestValidators:
    """Test Pydantic validators."""

    def test_payment_record_valid(self):
        """Valid payment data should pass validation."""
        record = PaymentImportRecord(
            source_id="pay_001",
            source_system="razorpay",
            amount=Decimal("1000.00"),
            status="captured",
            payment_timestamp=datetime.now(timezone.utc),
        )
        assert record.amount == Decimal("1000.00")
        assert record.currency == "INR"

    def test_payment_record_negative_amount_rejected(self):
        """Negative amounts should fail validation."""
        with pytest.raises(Exception):
            PaymentImportRecord(
                source_id="pay_002",
                source_system="razorpay",
                amount=Decimal("-100.00"),
                status="captured",
                payment_timestamp=datetime.now(timezone.utc),
            )

    def test_payment_record_epoch_timestamp(self):
        """Epoch timestamp should be parsed to datetime."""
        record = PaymentImportRecord(
            source_id="pay_003",
            source_system="razorpay",
            amount=Decimal("500.00"),
            status="captured",
            payment_timestamp=1672531200,
        )
        assert isinstance(record.payment_timestamp, datetime)

    def test_import_result_defaults(self):
        """ImportResult should have zero defaults."""
        result = ImportResult()
        assert result.records_received == 0
        assert result.records_accepted == 0
        assert result.duplicates == 0

    def test_ledger_entry_record(self):
        """Ledger entry should validate correctly."""
        record = LedgerEntryImportRecord(
            source_id="ledger_001",
            source_system="tally",
            amount=Decimal("5000.00"),
            type="credit",
            entry_timestamp=datetime.now(timezone.utc),
        )
        assert record.type == "credit"


class TestMockRazorpayClient:
    """Test the mock Razorpay client."""

    async def test_fetch_payments_returns_data(self):
        """Mock client should return realistic payment data."""
        client = MockRazorpayClient()
        payments = await client.fetch_payments()
        assert len(payments) == 5
        assert payments[0]["id"].startswith("pay_")
        assert isinstance(payments[0]["amount"], int)  # Paise
        assert payments[0]["fee"] > 0

    async def test_fetch_orders_returns_data(self):
        """Mock client should return order data."""
        client = MockRazorpayClient()
        orders = await client.fetch_orders()
        assert len(orders) == 5
        assert orders[0]["id"].startswith("order_")

    async def test_fetch_settlements_returns_data(self):
        """Mock client should return settlement data."""
        client = MockRazorpayClient()
        settlements = await client.fetch_settlements()
        assert len(settlements) == 5
        assert settlements[0]["id"].startswith("setl_")

    async def test_fetch_refunds_returns_data(self):
        """Mock client should return refund data."""
        client = MockRazorpayClient()
        refunds = await client.fetch_refunds()
        assert len(refunds) == 5
        assert refunds[0]["id"].startswith("rfnd_")

    async def test_fetch_disputes_returns_data(self):
        """Mock client should return dispute data."""
        client = MockRazorpayClient()
        disputes = await client.fetch_disputes()
        assert len(disputes) == 5
        assert disputes[0]["id"].startswith("disp_")

    async def test_mock_client_no_network(self):
        """Mock client must work without network."""
        client = MockRazorpayClient()
        # All calls should succeed instantly without any network
        payments = await client.fetch_payments()
        orders = await client.fetch_orders()
        assert len(payments) > 0
        assert len(orders) > 0

    async def test_factory_returns_mock_by_default(self):
        """Factory should return mock client by default."""
        client = get_razorpay_client("mock")
        assert isinstance(client, MockRazorpayClient)


class TestMerchantEndpoints:
    """Test merchant CRUD endpoints."""

    async def test_create_merchant(self, client: AsyncClient):
        """Create a merchant via API."""
        response = await client.post(
            "/api/v1/merchants",
            json={"name": "Test Corp", "business_type": "ecommerce"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Corp"
        assert "id" in data

    async def test_list_merchants(self, client: AsyncClient):
        """List merchants via API."""
        # Create one first
        await client.post(
            "/api/v1/merchants",
            json={"name": "List Test Corp"},
        )
        response = await client.get("/api/v1/merchants")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRazorpaySync:
    """Test Razorpay sync endpoint."""

    async def test_sync_nonexistent_merchant(self, client: AsyncClient):
        """Syncing with non-existent merchant should return 404."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/v1/import/razorpay/sync?merchant_id={fake_id}"
        )
        assert response.status_code == 404

    async def test_sync_with_mock_client(self, client: AsyncClient, db_session):
        """Sync should work with mock Razorpay client."""
        from app.models.merchant import Merchant

        merchant = Merchant(name="Sync Test", status="active")
        db_session.add(merchant)
        await db_session.flush()

        response = await client.post(
            f"/api/v1/import/razorpay/sync?merchant_id={merchant.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "payments" in data["summary"]
        assert data["summary"]["payments"]["synced"] > 0
