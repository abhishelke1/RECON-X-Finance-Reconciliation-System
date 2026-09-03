"""Tests for Group 6: Policy Engine, Auto-Resolution, Human Review, and Audit Trail."""
from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import Merchant
from app.models.payment import Payment
from app.models.reconciliation import ReconciliationRun, ReconciliationMatch
from app.models.exception import Exception_, ExceptionEvidence
from app.models.decision import Decision
from app.models.audit_log import AuditLog

from app.ai.schemas import AIAnalysisResult
from app.policy.rules import PolicyRules
from app.policy.engine import PolicyEngine
from app.audit.logger import AuditLogger


@pytest.fixture
def base_time():
    return datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)


class TestPolicyRules:
    """Tests for deterministic policy rules and safety guardrails."""

    def test_timing_difference_zero_variance_auto_resolves(self):
        rules = PolicyRules()
        exc = Exception_(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            exception_type="TIMING_DIFFERENCE",
            severity="low",
            status="open",
            amount_involved=Decimal("1000.00"),
            variance=Decimal("0.00"),
            description="Timing difference",
        )
        ai = AIAnalysisResult(
            classification="TIMING_DIFFERENCE",
            explanation="Normal banking clearance delay.",
            supporting_evidence=["pay_1"],
            confidence=0.95,
            recommended_action="AUTO_RESOLVE_TIMING",
            missing_information=[],
            requires_human_review=False,
        )

        decision = rules.evaluate(exc, ai)
        assert decision.can_auto_resolve is True
        assert decision.action == "MARK_TIMING_RECONCILED"

    def test_chargeback_mandates_human_review(self):
        rules = PolicyRules()
        exc = Exception_(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            exception_type="CHARGEBACK_RELATED",
            severity="critical",
            status="open",
            amount_involved=Decimal("2000.00"),
            variance=Decimal("-2000.00"),
            description="Dispute raised by customer bank",
        )
        ai = AIAnalysisResult(
            classification="CHARGEBACK_HOLD",
            explanation="Issuer dispute hold.",
            supporting_evidence=["disp_1"],
            confidence=0.99,
            recommended_action="AUTO_RESOLVE",  # Even if AI hallucinates auto-resolve!
            missing_information=[],
            requires_human_review=False,
        )

        decision = rules.evaluate(exc, ai)
        # Policy rules OVERRIDE AI: Chargebacks must never be auto-resolved
        assert decision.can_auto_resolve is False
        assert decision.action == "ESCALATE_TO_HUMAN"
        assert "mandates human controller review" in decision.reason

    def test_low_confidence_blocks_auto_resolve(self):
        rules = PolicyRules()
        exc = Exception_(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            merchant_id=uuid.uuid4(),
            exception_type="TIMING_DIFFERENCE",
            severity="low",
            status="open",
            amount_involved=Decimal("500.00"),
            variance=Decimal("0.00"),
            description="Timing difference",
        )
        ai = AIAnalysisResult(
            classification="TIMING_DIFFERENCE",
            explanation="Possible timing delay.",
            supporting_evidence=["pay_2"],
            confidence=0.70,  # Below threshold 0.85
            recommended_action="AUTO_RESOLVE_TIMING",
            missing_information=[],
            requires_human_review=False,
        )

        decision = rules.evaluate(exc, ai)
        assert decision.can_auto_resolve is False
        assert decision.action == "ESCALATE_TO_HUMAN"
        assert "below strict safety threshold" in decision.reason


class TestPolicyEngineExecution:
    """Tests for policy evaluation and automatic decision persistence."""

    async def test_auto_resolve_execution(self, db_session: AsyncSession, base_time):
        merchant = Merchant(name="Auto Resolve Test", status="active")
        db_session.add(merchant)
        await db_session.flush()

        run = ReconciliationRun(merchant_id=merchant.id, status="completed")
        db_session.add(run)
        await db_session.flush()

        exc = Exception_(
            id=uuid.uuid4(),
            run_id=run.id,
            merchant_id=merchant.id,
            exception_type="TIMING_DIFFERENCE",
            severity="low",
            status="open",
            amount_involved=Decimal("1500.00"),
            variance=Decimal("0.00"),
            description="T+1 clearing delay",
        )
        db_session.add(exc)
        await db_session.commit()

        ai = AIAnalysisResult(
            classification="TIMING_DIFFERENCE",
            explanation="Cleared T+1 day with exact amount.",
            supporting_evidence=["p1"],
            confidence=0.95,
            recommended_action="AUTO_RESOLVE_TIMING",
            missing_information=[],
            requires_human_review=False,
        )

        engine = PolicyEngine()
        policy_dec, dec_record = await engine.evaluate_and_apply(db_session, exc, ai)

        assert policy_dec.can_auto_resolve is True
        assert dec_record is not None
        assert dec_record.decision_type == "auto_resolve"
        assert exc.status == "auto_resolved"
        assert exc.resolved_at is not None

        # Verify audit trail
        trail = await AuditLogger.get_trail(db_session, exc.id)
        assert len(trail) >= 1
        assert trail[-1].action == "exception_auto_resolve"


class TestHumanReviewAPI:
    """Tests for human-in-the-loop exception API routes."""

    async def test_exception_lifecycle_api(self, client: AsyncClient, db_session: AsyncSession, base_time):
        # 1. Setup Merchant & Exception
        merchant = Merchant(name="Human Review Test", status="active")
        db_session.add(merchant)
        await db_session.flush()

        run = ReconciliationRun(merchant_id=merchant.id, status="completed")
        db_session.add(run)
        await db_session.flush()

        exc = Exception_(
            id=uuid.uuid4(),
            run_id=run.id,
            merchant_id=merchant.id,
            exception_type="AMOUNT_MISMATCH",
            severity="high",
            status="open",
            amount_involved=Decimal("10000.00"),
            variance=Decimal("-500.00"),
            description="500 INR variance detected",
        )
        db_session.add(exc)
        await db_session.commit()

        # 2. GET /exceptions
        list_resp = await client.get(f"/api/v1/exceptions?merchant_id={merchant.id}")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # 3. GET /exceptions/{id}
        detail_resp = await client.get(f"/api/v1/exceptions/{exc.id}")
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert data["id"] == str(exc.id)
        assert "evidence_graph" in data

        # 4. POST /exceptions/{id}/investigate
        inv_resp = await client.post(f"/api/v1/exceptions/{exc.id}/investigate")
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()
        assert "ai_analysis" in inv_data
        assert "policy_decision" in inv_data
        # 500 INR variance should mandate human review
        assert inv_data["auto_resolved"] is False

        # 5. POST /exceptions/{id}/approve (Human approves resolution)
        app_resp = await client.post(
            f"/api/v1/exceptions/{exc.id}/approve",
            json={"reviewer": "chief_controller@merchant.com", "notes": "Approved variance post-adjustment."},
        )
        assert app_resp.status_code == 200
        assert app_resp.json()["status"] == "approved"

        # 6. GET /audit/{entity_id}
        audit_resp = await client.get(f"/api/v1/audit/{exc.id}")
        assert audit_resp.status_code == 200
        logs = audit_resp.json()
        assert len(logs) >= 2  # escalated + human approve
        actions = [log["action"] for log in logs]
        assert "exception_human_approve" in actions
