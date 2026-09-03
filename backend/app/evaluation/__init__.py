"""Evaluation package for RECON-X benchmarking and dataset generation."""
from app.evaluation.data_generator import SyntheticDataGenerator, GeneratedDataset
from app.evaluation.baseline import NaiveBaselineReconciler
from app.evaluation.metrics import MetricsCalculator, EvaluationMetrics
from app.evaluation.anomaly_detector import AnomalyDetector
from app.evaluation.runner import EvaluationRunner

__all__ = [
    "SyntheticDataGenerator",
    "GeneratedDataset",
    "NaiveBaselineReconciler",
    "MetricsCalculator",
    "EvaluationMetrics",
    "AnomalyDetector",
    "EvaluationRunner",
]
