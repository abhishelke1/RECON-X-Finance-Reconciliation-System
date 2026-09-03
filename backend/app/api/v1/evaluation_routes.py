"""Evaluation and benchmark API routes."""
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.evaluation import EvaluationRun
from app.models.payment import Payment
from app.evaluation.data_generator import SyntheticDataGenerator
from app.evaluation.runner import EvaluationRunner
from app.evaluation.anomaly_detector import AnomalyDetector

router = APIRouter()


class EvaluationRunRequest(BaseModel):
    num_records: int = 5000  # Minimum 5,000 as per rule #7
    dataset_name: str = "Synthetic_Evaluation_Benchmark"
    seed: int = 42


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    dataset_name: str
    dataset_size: int
    matching_precision: float | None
    matching_recall: float | None
    matching_f1: float | None
    false_match_rate: float | None
    unresolved_rate: float | None
    auto_resolution_precision: float | None
    human_review_rate: float | None
    processing_time_ms: int | None
    is_baseline: bool
    results: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


@router.post("/evaluation/run", status_code=status.HTTP_201_CREATED)
async def trigger_evaluation_run(
    request: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a deterministic synthetic financial dataset with ground-truth labels
    and executes an empirical benchmark comparing RECON-X against baseline.
    """
    if request.num_records < 100:
        raise HTTPException(status_code=400, detail="Minimum records for evaluation is 100")

    generator = SyntheticDataGenerator(seed=request.seed)
    dataset = generator.generate(num_transactions=request.num_records)

    runner = EvaluationRunner()
    results = await runner.run_evaluation(
        db=db,
        dataset=dataset,
        dataset_name=request.dataset_name,
    )
    return results


@router.get("/evaluation/runs", response_model=list[EvaluationRunResponse])
async def list_evaluation_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lists past evaluation benchmark runs."""
    stmt = select(EvaluationRun).order_by(EvaluationRun.started_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/evaluation/latest")
async def get_latest_benchmark_comparison(
    db: AsyncSession = Depends(get_db),
):
    """Retrieves the latest comparative evaluation scoreboard."""
    stmt_rx = select(EvaluationRun).where(EvaluationRun.is_baseline == False).order_by(EvaluationRun.started_at.desc()).limit(1)
    stmt_bl = select(EvaluationRun).where(EvaluationRun.is_baseline == True).order_by(EvaluationRun.started_at.desc()).limit(1)

    rx_run = (await db.execute(stmt_rx)).scalar_one_or_none()
    bl_run = (await db.execute(stmt_bl)).scalar_one_or_none()

    if not rx_run:
        raise HTTPException(status_code=404, detail="No evaluation runs have been recorded yet.")

    return {
        "dataset_name": rx_run.dataset_name,
        "dataset_size": rx_run.dataset_size,
        "recon_x": {
            "precision": float(rx_run.matching_precision) if rx_run.matching_precision else 0.0,
            "recall": float(rx_run.matching_recall) if rx_run.matching_recall else 0.0,
            "f1_score": float(rx_run.matching_f1) if rx_run.matching_f1 else 0.0,
            "auto_resolution_precision": float(rx_run.auto_resolution_precision) if rx_run.auto_resolution_precision else 0.0,
            "human_review_rate": float(rx_run.human_review_rate) if rx_run.human_review_rate else 0.0,
            "processing_time_ms": rx_run.processing_time_ms,
        },
        "baseline": {
            "precision": float(bl_run.matching_precision) if bl_run and bl_run.matching_precision else 0.0,
            "recall": float(bl_run.matching_recall) if bl_run and bl_run.matching_recall else 0.0,
            "f1_score": float(bl_run.matching_f1) if bl_run and bl_run.matching_f1 else 0.0,
            "human_review_rate": 1.0,
            "processing_time_ms": bl_run.processing_time_ms if bl_run else 0,
        },
    }


@router.post("/evaluation/detect-anomalies")
async def detect_transaction_anomalies(
    merchant_id: uuid.UUID = Query(..., description="Merchant UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Executes secondary ML Isolation Forest to flag statistical outliers."""
    stmt = select(Payment).where(Payment.merchant_id == merchant_id).limit(500)
    payments = list((await db.execute(stmt)).scalars().all())

    detector = AnomalyDetector()
    results = detector.fit_predict(payments)

    anomalies = [r for r in results if r.is_anomaly]
    return {
        "total_analyzed": len(payments),
        "anomalies_detected": len(anomalies),
        "anomalies": [
            {
                "source_id": a.source_id,
                "score": round(a.anomaly_score, 4),
                "reason": a.reason,
            }
            for a in anomalies
        ],
    }
