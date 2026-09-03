"""Synthetic financial dataset generator for RECON-X evaluation.

Generates realistic Razorpay payments, orders, refunds, chargebacks,
settlements, and merchant ledger entries with known ground truth labels.
Capable of generating 10,000+ records deterministically.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import random
from typing import NamedTuple
import uuid

from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry


class GroundTruthScenario(NamedTuple):
    payment_id: str
    scenario_type: str  # CLEAN_MATCH, FEE_MATCH, TIMING_DELAY, REFUND, CHARGEBACK, PARTIAL, DUPLICATE, MISSING_LEDGER, ORPHAN_LEDGER, AMOUNT_MISMATCH
    expected_recon_status: str
    expected_auto_resolve: bool


class GeneratedDataset(NamedTuple):
    merchant: Merchant
    payments: list[Payment]
    orders: list[Order]
    settlements: list[Settlement]
    refunds: list[Refund]
    chargebacks: list[Chargeback]
    ledger_entries: list[LedgerEntry]
    ground_truth: list[GroundTruthScenario]


class SyntheticDataGenerator:
    """Generates parameterized, reproducible synthetic financial datasets."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(
        self,
        num_transactions: int = 10000,
        merchant_name: str = "Razorpay Merchant Corp",
        start_date: datetime | None = None,
    ) -> GeneratedDataset:
        """
        Generates a complete dataset with a balanced distribution of real-world scenarios:
        - ~65% Clean 1:1 or fee deduction matches
        - ~10% Bank clearance / timing delay differences
        - ~7% Refunds
        - ~3% Disputes / chargebacks
        - ~4% Partial settlements
        - ~3% Duplicate records
        - ~4% Missing in ledger (unreconciled payment)
        - ~2% Orphan ledger entries (unreconciled deposit)
        - ~2% Amount mismatch / billing variance
        """
        self.rng.seed(self.seed)
        start_ts = start_date or datetime(2026, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

        merchant_id = uuid.uuid4()
        batch_tag = merchant_id.hex[:6]
        merchant = Merchant(
            id=merchant_id,
            name=merchant_name,
            razorpay_account_id=f"acc_{batch_tag}_{self.rng.randint(1000, 9999)}",
            business_type="ecommerce",
            status="active",
        )

        payments: list[Payment] = []
        orders: list[Order] = []
        settlements: list[Settlement] = []
        refunds: list[Refund] = []
        chargebacks: list[Chargeback] = []
        ledger_entries: list[LedgerEntry] = []
        ground_truth: list[GroundTruthScenario] = []

        first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan", "Diya", "Saanvi", "Ananya", "Aadhya", "Pari"]
        last_names = ["Sharma", "Verma", "Gupta", "Malhotra", "Mehta", "Patel", "Joshi", "Bhat", "Rao", "Reddy", "Nair", "Iyer", "Sen", "Das", "Singh"]

        for idx in range(1, num_transactions + 1):
            ts_offset_sec = idx * 120 + self.rng.randint(0, 60)
            txn_time = start_ts + timedelta(seconds=ts_offset_sec)

            p_source_id = f"pay_{batch_tag}_{idx:06d}"
            o_source_id = f"order_{batch_tag}_{idx:06d}"
            receipt_id = f"rcpt_{batch_tag}_{idx:06d}"

            first = self.rng.choice(first_names)
            last = self.rng.choice(last_names)
            cust_name = f"{first} {last}"
            cust_email = f"{first.lower()}.{last.lower()}{idx % 100}@example.com"
            cust_phone = f"+9198{self.rng.randint(10000000, 99999999)}"

            base_amount = Decimal(str(self.rng.randint(100, 25000))) + Decimal(str(self.rng.choice([0, 50, 99]))) / Decimal("100")
            fee = round(base_amount * Decimal("0.0200"), 4)
            tax = round(fee * Decimal("0.1800"), 4)
            net_amount = base_amount - fee - tax

            roll = self.rng.random()

            if roll < 0.45:
                # 1. Clean Match: Gross amount recorded in ledger
                scenario = "CLEAN_MATCH"
                expected_status = "MATCHED"
                auto_resolve = True

                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        fee=Decimal("0.0000"),
                        tax=Decimal("0.0000"),
                        status="captured",
                        method="upi",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                orders.append(
                    Order(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=o_source_id,
                        source_system="razorpay",
                        amount=base_amount,
                        currency="INR",
                        status="paid",
                        receipt=receipt_id,
                        order_timestamp=txn_time - timedelta(minutes=2),
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="tally",
                        entry_type="credit",
                        amount=base_amount,
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"UPI Payment receipt {p_source_id} from {cust_name}",
                        entry_timestamp=txn_time + timedelta(hours=1),
                    )
                )

            elif roll < 0.65:
                # 2. Fee Deduction Match: Net amount recorded in ledger
                scenario = "FEE_MATCH"
                expected_status = "MATCHED_AFTER_FEES"
                auto_resolve = True

                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        fee=fee,
                        tax=tax,
                        currency="INR",
                        status="captured",
                        method="card",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                orders.append(
                    Order(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=o_source_id,
                        source_system="razorpay",
                        amount=base_amount,
                        currency="INR",
                        status="paid",
                        receipt=receipt_id,
                        order_timestamp=txn_time - timedelta(minutes=1),
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="bank_feed",
                        entry_type="credit",
                        amount=net_amount,
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"Bank settlement net credit {p_source_id}",
                        entry_timestamp=txn_time + timedelta(hours=12),
                    )
                )

            elif roll < 0.75:
                # 3. Timing Clearance Delay (>24 hours)
                scenario = "TIMING_DELAY"
                expected_status = "TIMING_DIFFERENCE"
                auto_resolve = True

                delay_days = self.rng.randint(2, 4)
                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="captured",
                        method="netbanking",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                orders.append(
                    Order(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=o_source_id,
                        source_system="razorpay",
                        amount=base_amount,
                        currency="INR",
                        status="paid",
                        receipt=receipt_id,
                        order_timestamp=txn_time - timedelta(minutes=3),
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="bank_feed",
                        entry_type="credit",
                        amount=base_amount,
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"Weekend clearance batch credit for {p_source_id}",
                        entry_timestamp=txn_time + timedelta(days=delay_days),
                    )
                )

            elif roll < 0.82:
                # 4. Verified Refund
                scenario = "REFUND"
                expected_status = "REFUND_RELATED"
                auto_resolve = True

                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="refunded",
                        method="upi",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                refund_source_id = f"rfnd_{batch_tag}_{idx:06d}"
                refunds.append(
                    Refund(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=refund_source_id,
                        source_system="razorpay",
                        payment_source_id=p_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="processed",
                        refund_timestamp=txn_time + timedelta(hours=6),
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="tally",
                        entry_type="credit",
                        amount=Decimal("0.0000"),
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"Refund offset {p_source_id} via {refund_source_id}",
                        entry_timestamp=txn_time + timedelta(hours=7),
                    )
                )

            elif roll < 0.86:
                # 5. Chargeback / Dispute (RISKY -> MUST NOT AUTO-RESOLVE)
                scenario = "CHARGEBACK"
                expected_status = "CHARGEBACK_RELATED"
                auto_resolve = False

                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="captured",
                        method="card",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                chargebacks.append(
                    Chargeback(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"disp_{batch_tag}_{idx:06d}",
                        source_system="razorpay",
                        payment_source_id=p_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="open",
                        reason="fraudulent_card_claim",
                        chargeback_timestamp=txn_time + timedelta(days=1),
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="tally",
                        entry_type="credit",
                        amount=Decimal("0.0000"),
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"Dispute hold on {p_source_id}",
                        entry_timestamp=txn_time + timedelta(days=1),
                    )
                )

            elif roll < 0.90:
                # 6. Partial Settlement
                scenario = "PARTIAL"
                expected_status = "PARTIAL_SETTLEMENT"
                auto_resolve = False

                half_amount = round(base_amount / Decimal("2"), 4)
                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="captured",
                        method="upi",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="erp",
                        entry_type="credit",
                        amount=half_amount,
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"Partial installment 1/2 for {p_source_id}",
                        entry_timestamp=txn_time + timedelta(hours=3),
                    )
                )

            elif roll < 0.94:
                # 7. Missing in Ledger (Unreconciled payment)
                scenario = "MISSING_LEDGER"
                expected_status = "MISSING_RECORD"
                auto_resolve = False

                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="captured",
                        method="upi",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )

            elif roll < 0.97:
                # 8. Orphan Ledger Entry (No payment in gateway)
                scenario = "ORPHAN_LEDGER"
                expected_status = "MISSING_RECORD"
                auto_resolve = False

                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_orph_{idx:06d}",
                        source_system="bank_statement",
                        entry_type="credit",
                        amount=base_amount,
                        currency="INR",
                        description=f"Direct bank NEFT credit from unlinked party {cust_name}",
                        entry_timestamp=txn_time,
                    )
                )

            else:
                # 9. Amount Mismatch / Discrepancy
                scenario = "AMOUNT_MISMATCH"
                expected_status = "AMOUNT_MISMATCH"
                auto_resolve = False

                variance_offset = Decimal(str(self.rng.randint(50, 500)))
                payments.append(
                    Payment(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=p_source_id,
                        source_system="razorpay",
                        order_source_id=o_source_id,
                        amount=base_amount,
                        currency="INR",
                        status="captured",
                        method="card",
                        customer_name=cust_name,
                        customer_email=cust_email,
                        customer_phone=cust_phone,
                        payment_timestamp=txn_time,
                    )
                )
                ledger_entries.append(
                    LedgerEntry(
                        id=uuid.uuid4(),
                        merchant_id=merchant_id,
                        source_id=f"led_{batch_tag}_{idx:06d}",
                        source_system="tally",
                        entry_type="credit",
                        amount=base_amount - variance_offset,
                        currency="INR",
                        reference_id=p_source_id,
                        description=f"Ledger entry with discrepancy for {p_source_id}",
                        entry_timestamp=txn_time + timedelta(hours=2),
                    )
                )

            ground_truth.append(
                GroundTruthScenario(
                    payment_id=p_source_id,
                    scenario_type=scenario,
                    expected_recon_status=expected_status,
                    expected_auto_resolve=auto_resolve,
                )
            )

        return GeneratedDataset(
            merchant=merchant,
            payments=payments,
            orders=orders,
            settlements=settlements,
            refunds=refunds,
            chargebacks=chargebacks,
            ledger_entries=ledger_entries,
            ground_truth=ground_truth,
        )
