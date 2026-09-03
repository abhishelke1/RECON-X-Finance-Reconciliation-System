"""Secondary machine learning anomaly detector using Isolation Forest."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
import numpy as np
from sklearn.ensemble import IsolationForest

from app.models.payment import Payment
from app.models.ledger_entry import LedgerEntry


@dataclass
class AnomalyScore:
    source_id: str
    is_anomaly: bool
    anomaly_score: float  # Negative values are outliers
    reason: str


class AnomalyDetector:
    """Detects statistical outliers in financial transaction patterns."""

    def __init__(self, contamination: float = 0.03, random_state: int = 42):
        self.contamination = contamination
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100,
        )

    def fit_predict(
        self,
        payments: Sequence[Payment],
        ledger_entries: Sequence[LedgerEntry] = (),
    ) -> list[AnomalyScore]:
        """
        Extracts tabular features and predicts anomalous transactions:
        - Amount
        - Fee percentage
        - Hour of day
        - Day of week (weekend flag)
        """
        if len(payments) < 10:
            # Not enough data for meaningful distribution fitting
            return [
                AnomalyScore(source_id=p.source_id, is_anomaly=False, anomaly_score=0.0, reason="Normal")
                for p in payments
            ]

        # Build feature matrix
        feature_matrix = []
        for p in payments:
            amt = float(p.amount)
            fee = float(p.fee) if p.fee is not None else 0.0
            fee_pct = (fee / amt * 100.0) if amt > 0 else 0.0
            hour = p.payment_timestamp.hour
            is_weekend = 1.0 if p.payment_timestamp.weekday() >= 5 else 0.0

            feature_matrix.append([amt, fee_pct, hour, is_weekend])

        X = np.array(feature_matrix)
        preds = self.model.fit_predict(X)
        scores = self.model.score_samples(X)

        results: list[AnomalyScore] = []
        for p, pred, score in zip(payments, preds, scores):
            is_outlier = bool(pred == -1)
            reasons: list[str] = []
            if is_outlier:
                amt = float(p.amount)
                if amt > 20000.0:
                    reasons.append(f"High value transaction ({amt:.2f} INR)")
                fee = float(p.fee) if p.fee else 0.0
                fee_pct = (fee / amt * 100.0) if amt > 0 else 0.0
                if fee_pct > 3.0 or fee_pct < 0.5:
                    reasons.append(f"Abnormal gateway fee rate ({fee_pct:.2f}%)")
                if p.payment_timestamp.hour < 5:
                    reasons.append(f"Off-hours transaction ({p.payment_timestamp.hour}:00)")

            reason_str = "; ".join(reasons) if reasons else ("Statistical outlier" if is_outlier else "Normal")
            results.append(
                AnomalyScore(
                    source_id=p.source_id,
                    is_anomaly=is_outlier,
                    anomaly_score=float(score),
                    reason=reason_str,
                )
            )

        return results
