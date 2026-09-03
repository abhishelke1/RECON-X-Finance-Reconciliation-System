"""Financial calculation module for reconciliation.

Computes expected vs actual amounts, net fees, taxes, refund deductions,
disputes, and variances with exact Decimal precision.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.payment import Payment
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry


@dataclass
class CalculationResult:
    expected_amount: Decimal
    actual_amount: Decimal
    variance: Decimal
    gross_amount: Decimal
    fee_deducted: Decimal
    tax_deducted: Decimal
    refund_deducted: Decimal
    chargeback_deducted: Decimal
    breakdown: dict[str, Any]


class ReconciliationCalculator:
    """Performs strict double-entry and net settlement calculations."""

    @staticmethod
    def calculate(
        payment: Payment | None = None,
        ledger_entry: LedgerEntry | None = None,
        settlement: Settlement | None = None,
        refund: Refund | None = None,
        chargeback: Chargeback | None = None,
    ) -> CalculationResult:
        """
        Calculates expected vs actual financial positions:
        - If both payment and ledger entry are present:
            Expected = Payment Gross - (Fee + Tax) - (Refunds) - (Disputes)
            Actual = Ledger Entry Amount
            Variance = Actual - Expected
        - If only payment is present:
            Expected = Payment Gross
            Actual = 0
            Variance = -Payment Gross (Missing in ledger)
        - If only ledger entry is present:
            Expected = 0
            Actual = Ledger Amount
            Variance = Ledger Amount (Missing in gateway)
        """
        gross = payment.amount if payment else Decimal("0.0000")
        fee = payment.fee if (payment and payment.fee is not None) else Decimal("0.0000")
        tax = payment.tax if (payment and payment.tax is not None) else Decimal("0.0000")
        
        refund_amt = refund.amount if refund else Decimal("0.0000")
        cbk_amt = chargeback.amount if chargeback else Decimal("0.0000")

        # Settlement fees take precedence if explicitly tied to a settlement
        if settlement and settlement.fees is not None:
            fee = settlement.fees
        if settlement and settlement.tax is not None:
            tax = settlement.tax

        actual = ledger_entry.amount if ledger_entry else Decimal("0.0000")

        if payment and ledger_entry:
            expected = gross - fee - tax - refund_amt - cbk_amt
            variance = actual - expected
        elif payment and not ledger_entry:
            expected = gross - fee - tax - refund_amt - cbk_amt
            actual = Decimal("0.0000")
            variance = -expected
        elif ledger_entry and not payment:
            expected = Decimal("0.0000")
            variance = actual
        else:
            expected = Decimal("0.0000")
            actual = Decimal("0.0000")
            variance = Decimal("0.0000")

        return CalculationResult(
            expected_amount=expected,
            actual_amount=actual,
            variance=variance,
            gross_amount=gross,
            fee_deducted=fee,
            tax_deducted=tax,
            refund_deducted=refund_amt,
            chargeback_deducted=cbk_amt,
            breakdown={
                "gross": str(gross),
                "fee": str(fee),
                "tax": str(tax),
                "refund": str(refund_amt),
                "chargeback": str(cbk_amt),
                "expected": str(expected),
                "actual": str(actual),
                "variance": str(variance),
            },
        )
