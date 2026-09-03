"""Import API endpoints for RECON-X data ingestion."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.settlement import Settlement
from app.models.order import Order
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.ingestion.csv_importer import CSVImporter
from app.ingestion.deduplicator import Deduplicator
from app.ingestion.normalizer import (
    normalize_razorpay_payment,
    normalize_razorpay_amount,
    normalize_timestamp,
    normalize_currency,
    normalize_string,
)
from app.ingestion.razorpay_client import get_razorpay_client
from app.ingestion.validators import (
    PaymentImportRecord,
    SettlementImportRecord,
    LedgerEntryImportRecord,
    ImportResult,
)

router = APIRouter()


# --- Pydantic schemas for API ---

class MerchantCreate(PydanticBaseModel):
    """Schema for creating a merchant."""
    name: str
    razorpay_account_id: str | None = None
    business_type: str | None = None


class MerchantResponse(PydanticBaseModel):
    """Schema for returning a merchant."""
    id: uuid.UUID
    name: str
    razorpay_account_id: str | None
    business_type: str | None
    status: str
    model_config = ConfigDict(from_attributes=True)


class ImportResultResponse(PydanticBaseModel):
    """Standard import result returned by all import endpoints."""
    records_received: int
    records_accepted: int
    records_rejected: int
    duplicates: int
    validation_errors: list[dict[str, Any]]


# --- Merchant endpoints ---

@router.post("/merchants", response_model=MerchantResponse, status_code=status.HTTP_201_CREATED)
async def create_merchant(merchant: MerchantCreate, db: AsyncSession = Depends(get_db)):
    """Create a new merchant."""
    new_merchant = Merchant(
        name=merchant.name,
        razorpay_account_id=merchant.razorpay_account_id,
        business_type=merchant.business_type,
        status="active",
    )
    db.add(new_merchant)
    await db.commit()
    await db.refresh(new_merchant)
    return new_merchant


@router.get("/merchants", response_model=list[MerchantResponse])
async def list_merchants(db: AsyncSession = Depends(get_db)):
    """List all merchants."""
    result = await db.execute(select(Merchant))
    return result.scalars().all()


# --- CSV Import endpoints ---

@router.post("/import/payments", response_model=ImportResultResponse)
async def import_payments(
    merchant_id: uuid.UUID = Query(..., description="Merchant UUID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import payment records from a CSV file."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    importer = CSVImporter()
    valid_records, result = await importer.import_csv(file, PaymentImportRecord)

    # Deduplicate
    dedup = Deduplicator(db)
    record_dicts = [r.model_dump() for r in valid_records]
    new_records, dup_count = await dedup.filter_new_records(Payment, record_dicts)

    # Save to DB
    for rec in new_records:
        payment = Payment(
            merchant_id=merchant_id,
            source_id=rec["source_id"],
            source_system=rec["source_system"],
            amount=rec["amount"],
            currency=rec.get("currency", "INR"),
            status=rec["status"],
            method=rec.get("method"),
            customer_email=rec.get("customer_email"),
            customer_phone=rec.get("customer_phone"),
            customer_name=rec.get("customer_name"),
            payment_timestamp=rec["payment_timestamp"],
            order_source_id=rec.get("order_source_id"),
            fee=rec.get("fee"),
            tax=rec.get("tax"),
        )
        db.add(payment)

    await db.commit()

    return ImportResultResponse(
        records_received=result.records_received,
        records_accepted=len(new_records),
        records_rejected=result.records_rejected,
        duplicates=dup_count,
        validation_errors=result.validation_errors,
    )


@router.post("/import/settlements", response_model=ImportResultResponse)
async def import_settlements(
    merchant_id: uuid.UUID = Query(..., description="Merchant UUID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import settlement records from a CSV file."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    importer = CSVImporter()
    valid_records, result = await importer.import_csv(file, SettlementImportRecord)

    dedup = Deduplicator(db)
    record_dicts = [r.model_dump() for r in valid_records]
    new_records, dup_count = await dedup.filter_new_records(Settlement, record_dicts)

    for rec in new_records:
        settlement = Settlement(
            merchant_id=merchant_id,
            source_id=rec["source_id"],
            source_system=rec["source_system"],
            amount=rec["amount"],
            currency=rec.get("currency", "INR"),
            status=rec["status"],
            fees=rec.get("fee"),
            tax=rec.get("tax"),
            utr=rec.get("utr"),
            settlement_timestamp=rec["settlement_timestamp"],
        )
        db.add(settlement)

    await db.commit()

    return ImportResultResponse(
        records_received=result.records_received,
        records_accepted=len(new_records),
        records_rejected=result.records_rejected,
        duplicates=dup_count,
        validation_errors=result.validation_errors,
    )


@router.post("/import/ledger", response_model=ImportResultResponse)
async def import_ledger(
    merchant_id: uuid.UUID = Query(..., description="Merchant UUID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import ledger entries from a CSV file."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    importer = CSVImporter()
    valid_records, result = await importer.import_csv(file, LedgerEntryImportRecord)

    dedup = Deduplicator(db)
    record_dicts = [r.model_dump() for r in valid_records]
    new_records, dup_count = await dedup.filter_new_records(LedgerEntry, record_dicts)

    for rec in new_records:
        entry = LedgerEntry(
            merchant_id=merchant_id,
            source_id=rec["source_id"],
            source_system=rec["source_system"],
            entry_type=rec["type"],
            amount=rec["amount"],
            currency=rec.get("currency", "INR"),
            description=rec.get("description"),
            entry_timestamp=rec["entry_timestamp"],
        )
        db.add(entry)

    await db.commit()

    return ImportResultResponse(
        records_received=result.records_received,
        records_accepted=len(new_records),
        records_rejected=result.records_rejected,
        duplicates=dup_count,
        validation_errors=result.validation_errors,
    )


# --- Razorpay Sync ---

@router.post("/import/razorpay/sync")
async def sync_razorpay(
    merchant_id: uuid.UUID = Query(..., description="Merchant UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Sync records from Razorpay API (mock or sandbox based on config)."""
    from app.config import get_settings
    settings = get_settings()

    merchant = await db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    client = get_razorpay_client(mode=settings.razorpay_mode)
    dedup = Deduplicator(db)
    summary: dict[str, dict[str, int]] = {}

    # Sync payments
    raw_payments = await client.fetch_payments()
    payment_dicts = [normalize_razorpay_payment(p) for p in raw_payments]
    new_payments, dup_payments = await dedup.filter_new_records(Payment, payment_dicts)
    for rec in new_payments:
        db.add(Payment(merchant_id=merchant_id, **{k: v for k, v in rec.items() if k != "raw_data"}, raw_data=rec.get("raw_data")))
    summary["payments"] = {"synced": len(new_payments), "duplicates": dup_payments}

    # Sync orders
    raw_orders = await client.fetch_orders()
    order_dicts = [
        {
            "source_id": o.get("id"),
            "source_system": "razorpay",
            "amount": normalize_razorpay_amount(o.get("amount")),
            "currency": normalize_currency(o.get("currency")),
            "status": normalize_string(o.get("status")),
            "receipt": o.get("receipt"),
            "order_timestamp": normalize_timestamp(o.get("created_at")),
            "raw_data": o,
        }
        for o in raw_orders
    ]
    new_orders, dup_orders = await dedup.filter_new_records(Order, order_dicts)
    for rec in new_orders:
        db.add(Order(merchant_id=merchant_id, **{k: v for k, v in rec.items() if k != "raw_data"}, raw_data=rec.get("raw_data")))
    summary["orders"] = {"synced": len(new_orders), "duplicates": dup_orders}

    # Sync refunds
    raw_refunds = await client.fetch_refunds()
    refund_dicts = [
        {
            "source_id": r.get("id"),
            "source_system": "razorpay",
            "payment_source_id": r.get("payment_id", ""),
            "amount": normalize_razorpay_amount(r.get("amount")),
            "currency": normalize_currency(r.get("currency")),
            "status": normalize_string(r.get("status")),
            "speed": r.get("speed_processed"),
            "refund_timestamp": normalize_timestamp(r.get("created_at")),
            "raw_data": r,
        }
        for r in raw_refunds
    ]
    new_refunds, dup_refunds = await dedup.filter_new_records(Refund, refund_dicts)
    for rec in new_refunds:
        db.add(Refund(merchant_id=merchant_id, **{k: v for k, v in rec.items() if k != "raw_data"}, raw_data=rec.get("raw_data")))
    summary["refunds"] = {"synced": len(new_refunds), "duplicates": dup_refunds}

    # Sync settlements
    raw_settlements = await client.fetch_settlements()
    settlement_dicts = [
        {
            "source_id": s.get("id"),
            "source_system": "razorpay",
            "amount": normalize_razorpay_amount(s.get("amount")),
            "currency": "INR",
            "status": normalize_string(s.get("status")),
            "fees": normalize_razorpay_amount(s.get("fees")),
            "tax": normalize_razorpay_amount(s.get("tax")),
            "utr": s.get("utr"),
            "settlement_timestamp": normalize_timestamp(s.get("created_at")),
            "raw_data": s,
        }
        for s in raw_settlements
    ]
    new_settlements, dup_settlements = await dedup.filter_new_records(Settlement, settlement_dicts)
    for rec in new_settlements:
        db.add(Settlement(merchant_id=merchant_id, **{k: v for k, v in rec.items() if k != "raw_data"}, raw_data=rec.get("raw_data")))
    summary["settlements"] = {"synced": len(new_settlements), "duplicates": dup_settlements}

    await db.commit()

    return {"status": "success", "summary": summary}
