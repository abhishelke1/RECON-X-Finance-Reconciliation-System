"""Evaluation metrics calculator for benchmark comparisons."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class EvaluationMetrics:
    dataset_size: int
    matching_precision: float
    matching_recall: float
    matching_f1: float
    false_match_rate: float
    unresolved_rate: float
    exception_classification_accuracy: float
    auto_resolution_precision: float
    human_review_rate: float
    processing_time_ms: int
    throughput_records_per_sec: float
    summary: dict[str, Any]


class MetricsCalculator:
    """Calculates factual, unmanipulated benchmark statistics from real evaluation runs."""

    @staticmethod
    def compute_metrics(
        total_records: int,
        true_matches: int,
        false_matches: int,
        expected_matches: int,
        total_exceptions: int,
        correctly_classified_exceptions: int,
        safe_auto_resolutions: int,
        total_auto_resolutions: int,
        human_review_count: int,
        processing_time_ms: int,
    ) -> EvaluationMetrics:
        """
        Calculates mathematical precision, recall, and safety metrics.
        """
        total_matched = true_matches + false_matches

        # 1. Matching Precision & Recall
        precision = (true_matches / total_matched) if total_matched > 0 else 0.0
        recall = (true_matches / expected_matches) if expected_matches > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # 2. Error rates
        false_match_rate = (false_matches / total_matched) if total_matched > 0 else 0.0
        unmatched_count = total_records - true_matches
        unresolved_rate = (unmatched_count / total_records) if total_records > 0 else 0.0

        # 3. AI & Policy performance
        classification_acc = (
            (correctly_classified_exceptions / total_exceptions) if total_exceptions > 0 else 1.0
        )
        auto_res_precision = (
            (safe_auto_resolutions / total_auto_resolutions) if total_auto_resolutions > 0 else 1.0
        )
        human_review_rate = (
            (human_review_count / total_exceptions) if total_exceptions > 0 else 0.0
        )

        # 4. Throughput
        elapsed_sec = max(processing_time_ms / 1000.0, 0.001)
        throughput = round(total_records / elapsed_sec, 1)

        return EvaluationMetrics(
            dataset_size=total_records,
            matching_precision=round(precision, 4),
            matching_recall=round(recall, 4),
            matching_f1=round(f1, 4),
            false_match_rate=round(false_match_rate, 4),
            unresolved_rate=round(unresolved_rate, 4),
            exception_classification_accuracy=round(classification_acc, 4),
            auto_resolution_precision=round(auto_res_precision, 4),
            human_review_rate=round(human_review_rate, 4),
            processing_time_ms=processing_time_ms,
            throughput_records_per_sec=throughput,
            summary={
                "total_records": total_records,
                "true_matches": true_matches,
                "false_matches": false_matches,
                "expected_matches": expected_matches,
                "total_exceptions": total_exceptions,
                "safe_auto_resolutions": safe_auto_resolutions,
                "total_auto_resolutions": total_auto_resolutions,
                "human_review_count": human_review_count,
            },
        )
