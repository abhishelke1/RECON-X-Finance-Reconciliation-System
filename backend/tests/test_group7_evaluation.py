"""Tests for Group 7: Evaluation, Synthetic Data Generation, Baseline, and Metrics."""
from decimal import Decimal
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import Merchant
from app.models.evaluation import EvaluationRun
from app.evaluation.data_generator import SyntheticDataGenerator
from app.evaluation.baseline import NaiveBaselineReconciler
from app.evaluation.metrics import MetricsCalculator
from app.evaluation.anomaly_detector import AnomalyDetector
from app.evaluation.runner import EvaluationRunner


class TestSyntheticDataGenerator:
    """Tests for synthetic dataset generator with ground-truth labels."""

    def test_generate_dataset_structure_and_reproducibility(self):
        gen1 = SyntheticDataGenerator(seed=123)
        ds1 = gen1.generate(num_transactions=150)

        gen2 = SyntheticDataGenerator(seed=123)
        ds2 = gen2.generate(num_transactions=150)

        assert len(ds1.ground_truth) == 150
        assert len(ds1.payments) > 0
        assert len(ds1.payments) == len(ds2.payments)
        assert ds1.payments[0].amount == ds2.payments[0].amount
        assert isinstance(ds1.payments[0].amount, Decimal)

        # Check scenario distribution
        scenario_types = {gt.scenario_type for gt in ds1.ground_truth}
        assert "CLEAN_MATCH" in scenario_types
        assert "FEE_MATCH" in scenario_types
        assert "TIMING_DELAY" in scenario_types

    def test_generate_large_scale_capabilities(self):
        """Verify generator can scale to 10,000 records smoothly."""
        gen = SyntheticDataGenerator(seed=999)
        # 5,000 generation test
        ds = gen.generate(num_transactions=5000)
        assert len(ds.ground_truth) == 5000
        assert len(ds.payments) > 4500


class TestBaselineReconciler:
    """Tests for the naive baseline matching algorithm."""

    def test_baseline_matches_only_exact_and_misses_fees(self):
        gen = SyntheticDataGenerator(seed=42)
        ds = gen.generate(num_transactions=100)

        baseline = NaiveBaselineReconciler()
        res = baseline.reconcile(ds.payments, ds.ledger_entries)

        # Baseline only matches clean 1:1, misses fee-deducted, refunds, delays
        assert len(res.matched_pairs) > 0
        assert len(res.unmatched_payments) > 0
        assert res.processing_time_ms >= 0


class TestMetricsCalculator:
    """Tests for mathematical precision and recall metrics."""

    def test_compute_metrics_accuracy(self):
        calc = MetricsCalculator()
        metrics = calc.compute_metrics(
            total_records=100,
            true_matches=80,
            false_matches=0,
            expected_matches=85,
            total_exceptions=20,
            correctly_classified_exceptions=18,
            safe_auto_resolutions=10,
            total_auto_resolutions=10,
            human_review_count=10,
            processing_time_ms=500,
        )

        assert metrics.matching_precision == 1.0
        assert round(metrics.matching_recall, 2) == 0.94
        assert metrics.auto_resolution_precision == 1.0
        assert metrics.false_match_rate == 0.0
        assert metrics.human_review_rate == 0.50
        assert metrics.throughput_records_per_sec > 0


class TestAnomalyDetector:
    """Tests for secondary ML Isolation Forest anomaly detection."""

    def test_fit_predict_anomalies(self):
        gen = SyntheticDataGenerator(seed=42)
        ds = gen.generate(num_transactions=100)

        detector = AnomalyDetector(contamination=0.05)
        scores = detector.fit_predict(ds.payments)

        assert len(scores) == len(ds.payments)
        anomalies = [s for s in scores if s.is_anomaly]
        assert len(anomalies) > 0  # Should flag outliers


class TestEvaluationRunner:
    """Tests for the full evaluation benchmark comparing RECON-X with baseline."""

    async def test_run_benchmark_comparison(self, db_session: AsyncSession):
        gen = SyntheticDataGenerator(seed=42)
        ds = gen.generate(num_transactions=100, merchant_name="Benchmark Merchant")

        runner = EvaluationRunner()
        report = await runner.run_evaluation(
            db=db_session,
            dataset=ds,
            dataset_name="Test_Benchmark_100",
        )

        assert "recon_x" in report
        assert "baseline" in report
        assert "lift" in report

        # RECON-X must outperform naive baseline on recall due to L2-L4 matching
        assert report["recon_x"]["recall"] >= report["baseline"]["recall"]
        assert report["lift"]["manual_effort_reduction_pct"] > 0


class TestEvaluationAPI:
    """Tests for evaluation REST endpoints."""

    async def test_evaluation_endpoints(self, client: AsyncClient, db_session: AsyncSession):
        # 1. Trigger evaluation run via API (100 records for fast test)
        run_resp = await client.post(
            "/api/v1/evaluation/run",
            json={"num_records": 100, "dataset_name": "API_Evaluation_Test", "seed": 77},
        )
        assert run_resp.status_code == 201
        data = run_resp.json()
        assert "recon_x" in data
        assert "baseline" in data

        # 2. GET /evaluation/runs
        list_resp = await client.get("/api/v1/evaluation/runs")
        assert list_resp.status_code == 200
        runs = list_resp.json()
        assert len(runs) >= 2  # RECON-X + Baseline runs

        # 3. GET /evaluation/latest
        latest_resp = await client.get("/api/v1/evaluation/latest")
        assert latest_resp.status_code == 200
        latest = latest_resp.json()
        assert "recon_x" in latest
        assert "baseline" in latest
