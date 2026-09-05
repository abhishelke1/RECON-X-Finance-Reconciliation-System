"""Demo and trial showcase API routes."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.models.reconciliation import ReconciliationRun
from app.models.exception import Exception_
from app.reconciliation.engine import ReconciliationEngine
from app.investigation.evidence_collector import EvidenceCollector
from app.ai.analyst import AIAnalyst
from app.policy.engine import PolicyEngine

logger = logging.getLogger(__name__)
router = APIRouter()


class SeedTrialResponse(BaseModel):
    success: bool
    merchant_id: str
    merchant_name: str
    run_id: str
    total_records: int
    matched_records: int
    exceptions_found: int
    auto_resolved_count: int
    human_review_count: int
    processing_time_ms: int
    spotlight_scenarios: dict[str, dict]

    model_config = ConfigDict(from_attributes=True)


@router.post("/demo/seed-trial", response_model=SeedTrialResponse, status_code=status.HTTP_201_CREATED)
async def seed_pro_trial_dataset(
    db: AsyncSession = Depends(get_db),
):
    """
    Seeds a pristine, professional enterprise trial dataset tailored for judge evaluations:
    - 8 Real-World Financial Scenarios (Spotlight cases)
    - 100 Background Transactions
    - Executes 4-tier matching, AI investigation, policy guardrails, and audit logging
    """
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=5)

    # 1. Create or retrieve Showcase Merchant
    merchant_name = "Apex Global Technologies (Enterprise Showcase)"
    stmt = select(Merchant).where(Merchant.name == merchant_name).limit(1)
    existing_merchant = (await db.execute(stmt)).scalar_one_or_none()

    if existing_merchant:
        merchant = existing_merchant
    else:
        merchant = Merchant(
            id=uuid.uuid4(),
            name=merchant_name,
            razorpay_account_id="acc_apex_rzp_enterprise_pro",
            business_type="ecommerce",
            status="active",
        )
        db.add(merchant)
        await db.flush()

    m_id = merchant.id
    tag = uuid.uuid4().hex[:6]

    payments: list[Payment] = []
    ledgers: list[LedgerEntry] = []
    refunds: list[Refund] = []
    chargebacks: list[Chargeback] = []

    # -------------------------------------------------------------------------
    # 8 SPOTLIGHT SCENARIOS (Designed specifically for demonstration to judges)
    # -------------------------------------------------------------------------

    # Scenario 1: Clean 1:1 Direct UPI Settlement (Level 1 Exact ID Match)
    s1_p_id = f"pay_pro_s1_{tag}"
    s1_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s1_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s1_{tag}",
        amount=Decimal("2499.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="captured",
        method="upi",
        customer_name="Aarav Sharma",
        customer_email="aarav.sharma@enterprise.com",
        customer_phone="+919876543210",
        payment_timestamp=base_time + timedelta(hours=1),
        raw_data={"item": "Pro Annual SaaS License", "customer": "Aarav Sharma"},
    )
    s1_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s1_{tag}",
        source_system="tally_erp",
        reference_id=s1_p_id,
        reference_type="payment_id",
        entry_type="credit",
        amount=Decimal("2499.0000"),
        currency="INR",
        description=f"HDFC UPI settlement credit for {s1_p_id}",
        account_code="1020-BANK-HDFC",
        entry_timestamp=base_time + timedelta(hours=2),
    )
    payments.append(s1_pay)
    ledgers.append(s1_led)

    # Scenario 2: Gateway Fee & GST Deduction (Level 3 Net Attribute Match -> Auto-Resolved POST_FEE_ADJUSTMENT)
    s2_p_id = f"pay_pro_s2_{tag}"
    s2_gross = Decimal("10000.0000")
    s2_fee = Decimal("200.0000")  # 2% MDR
    s2_tax = Decimal("36.0000")   # 18% GST
    s2_net = s2_gross - s2_fee - s2_tax  # 9764.00
    s2_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s2_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s2_{tag}",
        amount=s2_gross,
        currency="INR",
        fee=s2_fee,
        tax=s2_tax,
        status="captured",
        method="card",
        customer_name="Priya Nair",
        customer_email="priya.nair@corporate.in",
        customer_phone="+919811223344",
        payment_timestamp=base_time + timedelta(hours=3),
        raw_data={"item": "Cloud Server Reservation", "customer": "Priya Nair"},
    )
    s2_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s2_{tag}",
        source_system="bank_icici",
        reference_id=s2_p_id,
        reference_type="payment_id",
        entry_type="credit",
        amount=s2_net,
        currency="INR",
        description=f"Razorpay net bank deposit after MDR fees for {s2_p_id}",
        account_code="1020-BANK-ICICI",
        entry_timestamp=base_time + timedelta(hours=5),
    )
    payments.append(s2_pay)
    ledgers.append(s2_led)

    # Scenario 3: Bank Weekend / Clearance Delay (T+2) -> Auto-Resolved MARK_TIMING_RECONCILED
    s3_p_id = f"pay_pro_s3_{tag}"
    s3_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s3_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s3_{tag}",
        amount=Decimal("6500.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="captured",
        method="netbanking",
        customer_name="Vikram Malhotra",
        customer_email="vikram.malhotra@consulting.com",
        customer_phone="+919822334455",
        payment_timestamp=base_time + timedelta(hours=6),
        raw_data={"item": "Professional Training Bundle", "customer": "Vikram Malhotra"},
    )
    s3_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s3_{tag}",
        source_system="bank_icici",
        reference_id=f"NEFT-ICICI-{s3_p_id}",
        reference_type="bank_utr",
        entry_type="credit",
        amount=Decimal("6500.0000"),
        currency="INR",
        description=f"Bank RTGS clearance settlement for payment {s3_p_id} (T+2 bank delay)",
        account_code="1020-BANK-ICICI",
        entry_timestamp=base_time + timedelta(days=3, hours=2),
    )
    payments.append(s3_pay)
    ledgers.append(s3_led)

    # Scenario 4: Customer Refund Offset -> Auto-Resolved ASSOCIATE_REFUND
    s4_p_id = f"pay_pro_s4_{tag}"
    s4_rf_id = f"rfnd_pro_s4_{tag}"
    s4_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s4_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s4_{tag}",
        amount=Decimal("1850.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="refunded",
        method="upi",
        customer_name="Ananya Iyer",
        customer_email="ananya.iyer@fintech.org",
        customer_phone="+919833445566",
        payment_timestamp=base_time + timedelta(hours=8),
        raw_data={"item": "Hardware Accessory Return", "customer": "Ananya Iyer"},
    )
    s4_rfnd = Refund(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s4_rf_id,
        source_system="razorpay",
        payment_source_id=s4_p_id,
        amount=Decimal("1850.0000"),
        currency="INR",
        status="processed",
        speed="normal",
        refund_timestamp=base_time + timedelta(hours=14),
        raw_data={"reason": "Customer cancellation within 24h"},
    )
    s4_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s4_{tag}",
        source_system="tally_erp",
        reference_id=s4_p_id,
        reference_type="payment_id",
        entry_type="credit",
        amount=Decimal("0.0000"),
        currency="INR",
        description=f"Zero net balance for refunded order {s4_p_id}",
        account_code="1020-BANK-HDFC",
        entry_timestamp=base_time + timedelta(hours=16),
    )
    payments.append(s4_pay)
    refunds.append(s4_rfnd)
    ledgers.append(s4_led)

    # Scenario 5: Cardholder Chargeback / Dispute Hold -> Mandated Human Review (Strict Policy Guardrail)
    s5_p_id = f"pay_pro_s5_{tag}"
    s5_disp_id = f"disp_pro_s5_{tag}"
    s5_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s5_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s5_{tag}",
        amount=Decimal("18500.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="disputed",
        method="card",
        customer_name="Rohan Gupta",
        customer_email="rohan.gupta@ecommerce.com",
        customer_phone="+919844556677",
        payment_timestamp=base_time + timedelta(hours=10),
        raw_data={"item": "Luxury Electronics Order", "customer": "Rohan Gupta"},
    )
    s5_cb = Chargeback(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s5_disp_id,
        source_system="razorpay",
        payment_source_id=s5_p_id,
        amount=Decimal("18500.0000"),
        currency="INR",
        status="open",
        reason="Suspected Fraud: Unauthorized card transaction claimed by issuer bank",
        chargeback_timestamp=base_time + timedelta(hours=11),
        raw_data={"evidence_due_by": (now + timedelta(days=7)).isoformat()},
    )
    s5_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s5_{tag}",
        source_system="bank_icici",
        reference_id=s5_p_id,
        reference_type="payment_id",
        entry_type="credit",
        amount=Decimal("0.0000"),
        currency="INR",
        description=f"Bank payout withheld by gateway pending chargeback dispute {s5_disp_id}",
        account_code="1020-BANK-ESCROW",
        entry_timestamp=base_time + timedelta(hours=12),
    )
    payments.append(s5_pay)
    chargebacks.append(s5_cb)
    ledgers.append(s5_led)

    # Scenario 6: Partial Installment Settlement -> Mandated Human Review (Variance ₹25,000 exceeds ₹10 threshold)
    s6_p_id = f"pay_pro_s6_{tag}"
    s6_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s6_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s6_{tag}",
        amount=Decimal("50000.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="captured",
        method="netbanking",
        customer_name="TechCorp India Ltd",
        customer_email="accounts@techcorpindia.com",
        customer_phone="+919855667788",
        payment_timestamp=base_time + timedelta(hours=12),
        raw_data={"item": "B2B Milestone Contract FY26", "customer": "TechCorp India Ltd"},
    )
    s6_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s6_{tag}",
        source_system="bank_hdfc",
        reference_id=s6_p_id,
        reference_type="payment_id",
        entry_type="credit",
        amount=Decimal("25000.0000"),
        currency="INR",
        description=f"Milestone Tranche 1 received (50% installment) for {s6_p_id}",
        account_code="1020-BANK-HDFC",
        entry_timestamp=base_time + timedelta(hours=14),
    )
    payments.append(s6_pay)
    ledgers.append(s6_led)

    # Scenario 7: Missing ERP Journal Entry (Dropped Webhook) -> Mandated Human Review
    s7_p_id = f"pay_pro_s7_{tag}"
    s7_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s7_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s7_{tag}",
        amount=Decimal("4200.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="captured",
        method="upi",
        customer_name="Sneha Patel",
        customer_email="sneha.patel@designstudio.com",
        customer_phone="+919866778899",
        payment_timestamp=base_time + timedelta(hours=15),
        raw_data={"item": "Quarterly Retainer Subscription", "customer": "Sneha Patel"},
    )
    payments.append(s7_pay)

    # Scenario 8: High-Variance Billing Mismatch -> Mandated Human Review (₹500 variance exceeds ₹10 limit)
    s8_p_id = f"pay_pro_s8_{tag}"
    s8_pay = Payment(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=s8_p_id,
        source_system="razorpay",
        order_source_id=f"order_pro_s8_{tag}",
        amount=Decimal("8500.0000"),
        currency="INR",
        fee=Decimal("0.0000"),
        tax=Decimal("0.0000"),
        status="captured",
        method="card",
        customer_name="Karan Verma",
        customer_email="karan.verma@retailcorp.in",
        customer_phone="+919877889900",
        payment_timestamp=base_time + timedelta(hours=18),
        raw_data={"item": "Omnichannel Inventory Order", "customer": "Karan Verma"},
    )
    s8_led = LedgerEntry(
        id=uuid.uuid4(),
        merchant_id=m_id,
        source_id=f"led_pro_s8_{tag}",
        source_system="tally_erp",
        reference_id=s8_p_id,
        reference_type="payment_id",
        entry_type="credit",
        amount=Decimal("8000.0000"),
        currency="INR",
        description=f"ERP journal booking with unapplied promo code discount for {s8_p_id}",
        account_code="1020-BANK-ICICI",
        entry_timestamp=base_time + timedelta(hours=20),
    )
    payments.append(s8_pay)
    ledgers.append(s8_led)

    # -------------------------------------------------------------------------
    # BACKGROUND TRANSACTIONS (100 Clean records)
    # -------------------------------------------------------------------------
    for i in range(1, 101):
        bg_p_id = f"pay_bg_{tag}_{i:04d}"
        amt = Decimal(f"{(i * 137.5 % 7500) + 500:.2f}")
        bg_pay = Payment(
            id=uuid.uuid4(),
            merchant_id=m_id,
            source_id=bg_p_id,
            source_system="razorpay",
            order_source_id=f"order_bg_{tag}_{i:04d}",
            amount=amt,
            currency="INR",
            fee=Decimal("0.0000"),
            tax=Decimal("0.0000"),
            status="captured",
            method="upi" if i % 2 == 0 else "card",
            customer_name=f"Customer {i}",
            customer_email=f"customer_{i}_{tag}@enterprise.com",
            customer_phone=f"+919800{i:06d}",
            payment_timestamp=base_time + timedelta(minutes=i * 25),
        )
        bg_led = LedgerEntry(
            id=uuid.uuid4(),
            merchant_id=m_id,
            source_id=f"led_bg_{tag}_{i:04d}",
            source_system="bank_hdfc",
            reference_id=bg_p_id,
            reference_type="payment_id",
            entry_type="credit",
            amount=amt,
            currency="INR",
            description=f"Bank direct settlement for {bg_p_id}",
            account_code="1020-BANK-HDFC",
            entry_timestamp=base_time + timedelta(minutes=i * 25 + 15),
        )
        payments.append(bg_pay)
        ledgers.append(bg_led)

    for p in payments: db.add(p)
    for l in ledgers: db.add(l)
    for r in refunds: db.add(r)
    for c in chargebacks: db.add(c)
    await db.commit()

    # Run reconciliation
    recon_engine = ReconciliationEngine()
    run = await recon_engine.run_reconciliation(
        db=db,
        merchant_id=m_id,
        parameters={"purpose": "judge_demonstration", "tag": tag},
    )

    # Evaluate exceptions with AI & policy
    exc_stmt = select(Exception_).where(Exception_.run_id == run.id)
    exceptions = list((await db.execute(exc_stmt)).scalars().all())

    collector = EvidenceCollector()
    analyst = AIAnalyst()
    policy_engine = PolicyEngine()

    auto_resolved_count = 0
    human_review_count = 0
    spotlight_map: dict[str, dict] = {}

    for exc in exceptions:
        graph = await collector.collect_evidence(db, exc.id)
        ai_res = await analyst.analyze_exception(exc, graph)
        pol_dec, _ = await policy_engine.evaluate_and_apply(db, exc, ai_res)

        if pol_dec.can_auto_resolve:
            auto_resolved_count += 1
        else:
            human_review_count += 1

        desc = exc.description or ""
        if s2_p_id in desc:
            spotlight_map["Scenario B (Fee Deduction)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}
        elif s3_p_id in desc:
            spotlight_map["Scenario C (Timing Delay)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}
        elif s4_p_id in desc or "rfnd" in desc:
            spotlight_map["Scenario D (Refund Offset)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}
        elif s5_p_id in desc or "disp" in desc:
            spotlight_map["Scenario E (Chargeback Hold)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}
        elif s6_p_id in desc:
            spotlight_map["Scenario F (Partial Installment)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}
        elif s7_p_id in desc:
            spotlight_map["Scenario G (Missing ERP Entry)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}
        elif s8_p_id in desc:
            spotlight_map["Scenario H (Amount Discrepancy)"] = {"exception_id": str(exc.id), "status": exc.status, "action": pol_dec.action, "variance": float(exc.variance or 0)}

    run.auto_resolved = auto_resolved_count
    run.human_review = human_review_count
    await db.commit()

    return SeedTrialResponse(
        success=True,
        merchant_id=str(merchant.id),
        merchant_name=merchant.name,
        run_id=str(run.id),
        total_records=run.total_records,
        matched_records=run.matched_records,
        exceptions_found=run.exceptions_found,
        auto_resolved_count=auto_resolved_count,
        human_review_count=human_review_count,
        processing_time_ms=run.processing_time_ms or 0,
        spotlight_scenarios=spotlight_map,
    )
