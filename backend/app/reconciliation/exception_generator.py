"""Exception and evidence generation for reconciliation discrepancies."""
from decimal import Decimal
import uuid

from app.models.exception import Exception_, ExceptionEvidence
from app.models.reconciliation import ReconciliationMatch, ReconciliationRun
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.reconciliation.calculator import CalculationResult
from app.reconciliation.classifier import ReconStatus


class ExceptionGenerator:
    """Generates structured Exception_ and immutable ExceptionEvidence entities."""

    @staticmethod
    def calculate_severity(recon_status: ReconStatus, amount_involved: Decimal | None, variance: Decimal | None) -> str:
        """Deterministically evaluates severity based on financial exposure."""
        abs_var = abs(variance) if variance is not None else Decimal("0.0000")
        abs_amt = abs(amount_involved) if amount_involved is not None else Decimal("0.0000")
        max_exposure = max(abs_var, abs_amt)

        if recon_status == ReconStatus.CHARGEBACK_RELATED:
            return "high" if max_exposure < Decimal("50000") else "critical"
        elif recon_status in (ReconStatus.MISSING_RECORD, ReconStatus.AMOUNT_MISMATCH, ReconStatus.UNKNOWN_EXCEPTION):
            if max_exposure >= Decimal("50000"):
                return "critical"
            elif max_exposure >= Decimal("5000"):
                return "high"
            elif max_exposure >= Decimal("500"):
                return "medium"
            else:
                return "low"
        elif recon_status == ReconStatus.PARTIAL_SETTLEMENT:
            return "high" if max_exposure >= Decimal("10000") else "medium"
        elif recon_status in (ReconStatus.TIMING_DIFFERENCE, ReconStatus.REFUND_RELATED):
            return "medium" if max_exposure >= Decimal("5000") else "low"
        else:
            return "low"

    def create_exception(
        self,
        run: ReconciliationRun,
        match: ReconciliationMatch,
        recon_status: ReconStatus,
        explanation: str,
        calc: CalculationResult,
        payment: Payment | None = None,
        order: Order | None = None,
        settlement: Settlement | None = None,
        refund: Refund | None = None,
        chargeback: Chargeback | None = None,
        ledger_entry: LedgerEntry | None = None,
    ) -> tuple[Exception_, list[ExceptionEvidence]]:
        """
        Creates an Exception_ record and associates immutable evidence snapshots.
        """
        amount_involved = payment.amount if payment else (ledger_entry.amount if ledger_entry else Decimal("0.0000"))
        severity = self.calculate_severity(recon_status, amount_involved, calc.variance)

        exception_record = Exception_(
            id=uuid.uuid4(),
            run_id=run.id,
            match_id=match.id,
            merchant_id=run.merchant_id,
            exception_type=recon_status.value,
            severity=severity,
            status="open",
            amount_involved=amount_involved,
            variance=calc.variance,
            description=explanation,
            ai_analysis=None,
            policy_result=None,
        )

        evidence_list: list[ExceptionEvidence] = []

        # 1. Calculation breakdown evidence
        evidence_list.append(
            ExceptionEvidence(
                id=uuid.uuid4(),
                exception_id=exception_record.id,
                evidence_type="calculation",
                record_id=match.id,
                record_type="reconciliation_match",
                data_snapshot=calc.breakdown,
                relationship="variance_calculation",
            )
        )

        # 2. Payment evidence
        if payment:
            evidence_list.append(
                ExceptionEvidence(
                    id=uuid.uuid4(),
                    exception_id=exception_record.id,
                    evidence_type="payment",
                    record_id=payment.id,
                    record_type="payment",
                    data_snapshot={
                        "source_id": payment.source_id,
                        "amount": str(payment.amount),
                        "fee": str(payment.fee) if payment.fee else None,
                        "tax": str(payment.tax) if payment.tax else None,
                        "status": payment.status,
                        "method": payment.method,
                        "payment_timestamp": payment.payment_timestamp.isoformat(),
                    },
                    relationship="source_payment",
                )
            )

        # 3. Ledger entry evidence
        if ledger_entry:
            evidence_list.append(
                ExceptionEvidence(
                    id=uuid.uuid4(),
                    exception_id=exception_record.id,
                    evidence_type="ledger",
                    record_id=ledger_entry.id,
                    record_type="ledger_entry",
                    data_snapshot={
                        "source_id": ledger_entry.source_id,
                        "amount": str(ledger_entry.amount),
                        "entry_type": ledger_entry.entry_type,
                        "reference_id": ledger_entry.reference_id,
                        "description": ledger_entry.description,
                        "entry_timestamp": ledger_entry.entry_timestamp.isoformat(),
                    },
                    relationship="merchant_ledger_entry",
                )
            )

        # 4. Order evidence
        if order:
            evidence_list.append(
                ExceptionEvidence(
                    id=uuid.uuid4(),
                    exception_id=exception_record.id,
                    evidence_type="order",
                    record_id=order.id,
                    record_type="order",
                    data_snapshot={
                        "source_id": order.source_id,
                        "amount": str(order.amount),
                        "receipt": order.receipt,
                        "status": order.status,
                    },
                    relationship="source_order",
                )
            )

        # 5. Refund evidence
        if refund:
            evidence_list.append(
                ExceptionEvidence(
                    id=uuid.uuid4(),
                    exception_id=exception_record.id,
                    evidence_type="refund",
                    record_id=refund.id,
                    record_type="refund",
                    data_snapshot={
                        "source_id": refund.source_id,
                        "amount": str(refund.amount),
                        "status": refund.status,
                        "payment_source_id": refund.payment_source_id,
                    },
                    relationship="linked_refund",
                )
            )

        # 6. Chargeback evidence
        if chargeback:
            evidence_list.append(
                ExceptionEvidence(
                    id=uuid.uuid4(),
                    exception_id=exception_record.id,
                    evidence_type="chargeback",
                    record_id=chargeback.id,
                    record_type="chargeback",
                    data_snapshot={
                        "source_id": chargeback.source_id,
                        "amount": str(chargeback.amount),
                        "status": chargeback.status,
                        "reason": chargeback.reason,
                    },
                    relationship="linked_chargeback",
                )
            )

        return exception_record, evidence_list
