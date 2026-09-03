"""Tests for Group 5: Exception Investigation & AI Analysis (Graph, Validator, Fallback, Analyst)."""
from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.ledger_entry import LedgerEntry
from app.models.reconciliation import ReconciliationRun, ReconciliationMatch
from app.models.exception import Exception_, ExceptionEvidence

from app.investigation.evidence_graph import EvidenceGraph
from app.investigation.evidence_collector import EvidenceCollector
from app.ai.schemas import AIAnalysisResult
from app.ai.validator import AIOutputValidator
from app.ai.fallback import DeterministicFallbackAnalyst
from app.ai.analyst import AIAnalyst


@pytest.fixture
def base_time():
    return datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestEvidenceGraph:
    """Tests for EvidenceGraph construction and serialization."""

    def test_build_graph_and_summarize(self):
        exc_id = uuid.uuid4()
        graph = EvidenceGraph(exception_id=exc_id)

        n1 = graph.add_node("pay_1", "payment", {"amount": "1000.00", "status": "captured"}, "Payment pay_1")
        n2 = graph.add_node("match_1", "reconciliation_match", {"variance": "0.00"}, "Match")
        e1 = graph.add_edge("pay_1", "match_1", "subject_of")

        graph_dict = graph.to_dict()
        assert graph_dict["exception_id"] == str(exc_id)
        assert len(graph_dict["nodes"]) == 2
        assert len(graph_dict["edges"]) == 1

        summary = graph.to_text_summary()
        assert "EVIDENCE DOSSIER" in summary
        assert "pay_1" in summary


class TestEvidenceCollector:
    """Tests for gathering evidence from DB records into graph."""

    async def test_collect_evidence_from_db(self, db_session: AsyncSession, base_time):
        merchant = Merchant(name="Investigate Corp", status="active")
        db_session.add(merchant)
        await db_session.flush()

        run = ReconciliationRun(merchant_id=merchant.id, status="completed")
        db_session.add(run)
        await db_session.flush()

        payment = Payment(
            merchant_id=merchant.id,
            source_id="pay_inv_1",
            source_system="razorpay",
            amount=Decimal("2500.0000"),
            currency="INR",
            status="captured",
            payment_timestamp=base_time,
        )
        db_session.add(payment)
        await db_session.flush()

        match = ReconciliationMatch(
            run_id=run.id,
            payment_id=payment.id,
            match_status="EXACT",
            match_confidence=Decimal("1.0"),
            expected_amount=Decimal("2500.0000"),
            actual_amount=Decimal("0.0000"),
            variance=Decimal("-2500.0000"),
            recon_status="MISSING_RECORD",
        )
        db_session.add(match)
        await db_session.flush()

        exc = Exception_(
            run_id=run.id,
            match_id=match.id,
            merchant_id=merchant.id,
            exception_type="MISSING_RECORD",
            severity="high",
            status="open",
            amount_involved=Decimal("2500.0000"),
            variance=Decimal("-2500.0000"),
            description="Payment captured on gateway but missing in ledger",
        )
        db_session.add(exc)
        await db_session.flush()

        ev = ExceptionEvidence(
            exception_id=exc.id,
            evidence_type="payment",
            record_id=payment.id,
            record_type="payment",
            data_snapshot={"source_id": "pay_inv_1", "amount": "2500.0000"},
            relationship="source_payment",
        )
        db_session.add(ev)
        await db_session.commit()

        collector = EvidenceCollector()
        graph = await collector.collect_evidence(db_session, exc.id)

        assert len(graph.nodes) >= 2  # evidence node + match node + payment node
        entities = collector.extract_ground_truth_entities(graph)
        assert "pay_inv_1" in entities
        assert "2500.0000" in entities


class TestAIOutputValidator:
    """Tests for validating AI responses and catching hallucinations."""

    def test_valid_grounded_response(self):
        validator = AIOutputValidator()
        ground_truth = {"pay_123", "order_456", "1000.00"}

        raw_json = """
        {
            "classification": "TIMING_DIFFERENCE",
            "explanation": "Transaction pay_123 cleared next banking day with 1000.00 INR.",
            "supporting_evidence": ["pay_123", "1000.00"],
            "confidence": 0.95,
            "recommended_action": "AUTO_RESOLVE_TIMING",
            "missing_information": [],
            "requires_human_review": false
        }
        """
        res = validator.validate_and_sanitize(raw_json, ground_truth)
        assert res.classification == "TIMING_DIFFERENCE"
        assert res.confidence == 0.95
        assert res.requires_human_review is False

    def test_hallucinated_evidence_rejected_and_escalated(self):
        validator = AIOutputValidator()
        ground_truth = {"pay_123", "order_456"}

        # AI invents "fake_txn_999" and "$50,000" not in ground truth
        raw_json = {
            "classification": "FRAUD_SUSPECT",
            "explanation": "Customer attempted multiple card runs under fake_txn_999.",
            "supporting_evidence": ["fake_txn_999"],
            "confidence": 0.90,
            "recommended_action": "AUTO_RESOLVE",
            "missing_information": [],
            "requires_human_review": False,
        }
        res = validator.validate_and_sanitize(raw_json, ground_truth)
        # Must be penalized and escalated to human
        assert res.requires_human_review is True
        assert res.recommended_action == "ESCALATE_TO_HUMAN"
        assert res.confidence <= 0.50
        assert "Unverified claims" in str(res.missing_information)


class TestDeterministicFallbackAnalyst:
    """Tests for zero-LLM deterministic fallback."""

    def test_fallback_timing_difference(self):
        analyst = DeterministicFallbackAnalyst()
        graph = EvidenceGraph(exception_id=uuid.uuid4())
        graph.add_node("p1", "payment", {}, "Payment")

        res = analyst.analyze(
            exception_type="TIMING_DIFFERENCE",
            amount_involved=Decimal("1000.00"),
            variance=Decimal("0.00"),
            evidence_graph=graph,
        )

        assert res.classification == "TIMING_DIFFERENCE"
        assert res.recommended_action == "AUTO_RESOLVE_TIMING"
        assert res.confidence >= 0.90
        assert res.requires_human_review is False

    def test_fallback_chargeback(self):
        analyst = DeterministicFallbackAnalyst()
        graph = EvidenceGraph(exception_id=uuid.uuid4())

        res = analyst.analyze(
            exception_type="CHARGEBACK_RELATED",
            amount_involved=Decimal("5000.00"),
            variance=Decimal("-5000.00"),
            evidence_graph=graph,
        )

        assert res.classification == "CHARGEBACK_HOLD"
        assert res.requires_human_review is True
        assert res.recommended_action == "ESCALATE_TO_HUMAN"


class TestAIAnalystIntegration:
    """Tests for the AIAnalyst interface."""

    async def test_analyst_graceful_fallback_when_no_api_key(self):
        analyst = AIAnalyst()
        # Default settings have no GEMINI_API_KEY
        exc = Exception_(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            exception_type="TIMING_DIFFERENCE",
            severity="low",
            status="open",
            amount_involved=Decimal("100.00"),
            variance=Decimal("0.00"),
            description="Timing difference",
        )
        graph = EvidenceGraph(exception_id=exc.id)

        result = await analyst.analyze_exception(exc, graph)
        assert isinstance(result, AIAnalysisResult)
        assert result.classification == "TIMING_DIFFERENCE"
        assert result.requires_human_review is False
