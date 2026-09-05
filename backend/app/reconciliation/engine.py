"""Reconciliation Engine Orchestrator.

Integrates matching, financial calculations, 10-state classification,
and exception generation into an atomic reconciliation run.
"""
from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import Sequence
import uuid

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

from app.matching.engine import MatchingEngine
from app.matching.scorer import MatchStatus, ScoredMatch
from app.reconciliation.calculator import ReconciliationCalculator
from app.reconciliation.classifier import ReconciliationClassifier, ReconStatus
from app.reconciliation.exception_generator import ExceptionGenerator


class ReconciliationEngine:
    """End-to-end financial reconciliation processor."""

    def __init__(
        self,
        matching_engine: MatchingEngine | None = None,
        calculator: ReconciliationCalculator | None = None,
        classifier: ReconciliationClassifier | None = None,
        exception_generator: ExceptionGenerator | None = None,
    ):
        self.matching_engine = matching_engine or MatchingEngine()
        self.calculator = calculator or ReconciliationCalculator()
        self.classifier = classifier or ReconciliationClassifier()
        self.exception_generator = exception_generator or ExceptionGenerator()

    async def run_reconciliation(
        self,
        db: AsyncSession,
        merchant_id: uuid.UUID,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        parameters: dict | None = None,
    ) -> ReconciliationRun:
        """
        Executes a complete reconciliation cycle:
        1. Queries records from DB
        2. Matches across 4 deterministic tiers
        3. Computes net settlements and variances
        4. Classifies each position
        5. Persists runs, matches, exceptions, and audit logs
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc)

        # 1. Fetch records
        payment_stmt = select(Payment).where(Payment.merchant_id == merchant_id)
        order_stmt = select(Order).where(Order.merchant_id == merchant_id)
        settlement_stmt = select(Settlement).where(Settlement.merchant_id == merchant_id)
        refund_stmt = select(Refund).where(Refund.merchant_id == merchant_id)
        chargeback_stmt = select(Chargeback).where(Chargeback.merchant_id == merchant_id)
        ledger_stmt = select(LedgerEntry).where(LedgerEntry.merchant_id == merchant_id)

        if from_timestamp:
            payment_stmt = payment_stmt.where(Payment.payment_timestamp >= from_timestamp)
            ledger_stmt = ledger_stmt.where(LedgerEntry.entry_timestamp >= from_timestamp)
        if to_timestamp:
            payment_stmt = payment_stmt.where(Payment.payment_timestamp <= to_timestamp)
            ledger_stmt = ledger_stmt.where(LedgerEntry.entry_timestamp <= to_timestamp)

        payments = list((await db.execute(payment_stmt)).scalars().all())
        orders = list((await db.execute(order_stmt)).scalars().all())
        settlements = list((await db.execute(settlement_stmt)).scalars().all())
        refunds = list((await db.execute(refund_stmt)).scalars().all())
        chargebacks = list((await db.execute(chargeback_stmt)).scalars().all())
        ledger_entries = list((await db.execute(ledger_stmt)).scalars().all())

        # Create ReconciliationRun record
        run = ReconciliationRun(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            status="running",
            started_at=started_at,
            total_records=len(payments) + len(ledger_entries),
            matched_records=0,
            unmatched_records=0,
            exceptions_found=0,
            auto_resolved=0,
            human_review=0,
            parameters=parameters or {},
        )
        db.add(run)
        await db.flush()

        # Build index maps by ID for fast association
        payment_map = {p.id: p for p in payments}
        order_map = {o.id: o for o in orders}
        settlement_map = {s.id: s for s in settlements}
        refund_map = {r.id: r for r in refunds}
        chargeback_map = {c.id: c for c in chargebacks}
        ledger_map = {l.id: l for l in ledger_entries}

        # 2. Run deterministic matching
        scored_matches: list[ScoredMatch] = self.matching_engine.run_matching(
            payments=payments,
            orders=orders,
            ledger_entries=ledger_entries,
            refunds=refunds,
            chargebacks=chargebacks,
            settlements=settlements,
        )

        matched_count = 0
        unmatched_count = 0
        exceptions_count = 0

        all_matches = []
        all_exceptions = []
        all_evidence = []

        # 3. Process matches, calculate variances, classify and generate exceptions
        for sm in scored_matches:
            pay = payment_map.get(sm.payment_id) if sm.payment_id else None
            ord_ = order_map.get(sm.order_id) if sm.order_id else None
            setl = settlement_map.get(sm.settlement_id) if sm.settlement_id else None
            rfnd = refund_map.get(sm.refund_id) if sm.refund_id else None
            cbk = chargeback_map.get(sm.chargeback_id) if sm.chargeback_id else None
            ledg = ledger_map.get(sm.ledger_entry_id) if sm.ledger_entry_id else None

            # Calculate expected vs actual financial positions
            calc = self.calculator.calculate(
                payment=pay,
                ledger_entry=ledg,
                settlement=setl,
                refund=rfnd,
                chargeback=cbk,
            )

            # Classify into one of 10 deterministic states
            recon_status, explanation = self.classifier.classify(
                match=sm,
                calc=calc,
                payment=pay,
                ledger_entry=ledg,
                refund=rfnd,
                chargeback=cbk,
                settlement=setl,
            )

            # Create ReconciliationMatch DB model
            db_match = ReconciliationMatch(
                id=uuid.uuid4(),
                run_id=run.id,
                payment_id=sm.payment_id,
                order_id=sm.order_id,
                settlement_id=sm.settlement_id,
                invoice_id=sm.invoice_id,
                refund_id=sm.refund_id,
                chargeback_id=sm.chargeback_id,
                ledger_entry_id=sm.ledger_entry_id,
                match_status=sm.match_status.value,
                match_confidence=sm.confidence,
                match_reasons=sm.reasons,
                expected_amount=calc.expected_amount,
                actual_amount=calc.actual_amount,
                variance=calc.variance,
                recon_status=recon_status.value,
            )
            all_matches.append(db_match)

            if sm.match_status == MatchStatus.UNMATCHED:
                unmatched_count += 1
            else:
                matched_count += 1

            # Determine if this position creates an exception
            # Any position that is not cleanly MATCHED or MATCHED_AFTER_FEES (or has non-zero variance)
            if recon_status not in (ReconStatus.MATCHED, ReconStatus.MATCHED_AFTER_FEES) or calc.variance != Decimal("0.0000"):
                exceptions_count += 1
                exc, evidence_items = self.exception_generator.create_exception(
                    run=run,
                    match=db_match,
                    recon_status=recon_status,
                    explanation=explanation,
                    calc=calc,
                    payment=pay,
                    order=ord_,
                    settlement=setl,
                    refund=rfnd,
                    chargeback=cbk,
                    ledger_entry=ledg,
                )
                all_exceptions.append(exc)
                all_evidence.extend(evidence_items)

        # Stage 1: Flush all reconciliation matches (depends only on run)
        for m in all_matches:
            db.add(m)
        await db.flush()

        # Stage 2: Flush all exceptions (depends on run and matches)
        for e in all_exceptions:
            db.add(e)
        await db.flush()

        # Stage 3: Flush all evidence items (depends on exceptions)
        for ev in all_evidence:
            db.add(ev)
        await db.flush()

        # 4. Finalize run stats
        end_time = time.perf_counter()
        processing_time_ms = int((end_time - start_time) * 1000)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.matched_records = matched_count
        run.unmatched_records = unmatched_count
        run.exceptions_found = exceptions_count
        run.processing_time_ms = processing_time_ms

        # 5. Write audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            entity_id=run.id,
            entity_type="reconciliation_run",
            action="reconciliation_completed",
            actor="system:reconciliation_engine",
            details={
                "merchant_id": str(merchant_id),
                "total_records": run.total_records,
                "matched_records": matched_count,
                "unmatched_records": unmatched_count,
                "exceptions_found": exceptions_count,
                "processing_time_ms": processing_time_ms,
            },
        )
        db.add(audit)

        await db.commit()
        await db.refresh(run)

        return run
