"""Root-cause AI Analyst incorporating Gemini LLM with deterministic fallbacks."""
import asyncio
import logging
from decimal import Decimal
from typing import Any

from app.config import get_settings
from app.models.exception import Exception_
from app.investigation.evidence_graph import EvidenceGraph
from app.investigation.evidence_collector import EvidenceCollector
from app.ai.schemas import AIAnalysisResult
from app.ai.prompts import SYSTEM_PROMPT, ANALYSIS_PROMPT_TEMPLATE
from app.ai.validator import AIOutputValidator
from app.ai.fallback import DeterministicFallbackAnalyst

logger = logging.getLogger(__name__)


class AIAnalyst:
    """Performs AI-assisted root cause analysis with automatic fallback."""

    def __init__(self):
        self.settings = get_settings()
        self.fallback = DeterministicFallbackAnalyst()
        self.validator = AIOutputValidator()

    async def analyze_exception(
        self,
        exception: Exception_,
        evidence_graph: EvidenceGraph,
    ) -> AIAnalysisResult:
        """
        Attempts LLM analysis via Google Gemini API if configured.
        Falls back to DeterministicFallbackAnalyst on any error, timeout, or missing key.
        """
        ground_truth_entities = EvidenceCollector.extract_ground_truth_entities(evidence_graph)

        # Check for API Key
        api_key = self.settings.gemini_api_key.strip() if self.settings.gemini_api_key else ""
        if not api_key:
            logger.info("No GEMINI_API_KEY configured; executing deterministic fallback analysis.")
            return self.fallback.analyze(
                exception_type=exception.exception_type,
                amount_involved=exception.amount_involved,
                variance=exception.variance,
                evidence_graph=evidence_graph,
            )

        # Format prompt
        dossier_text = evidence_graph.to_text_summary()
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            dossier_text=dossier_text,
            exception_id=exception.id,
            exception_type=exception.exception_type,
            severity=exception.severity,
            amount_involved=exception.amount_involved or "0.00",
            variance=exception.variance or "0.00",
            description=exception.description,
        )

        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=self.settings.llm_model,
                system_instruction=SYSTEM_PROMPT,
                generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
            )

            # Run with 10s timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(model.generate_content, prompt),
                timeout=10.0,
            )

            raw_json = response.text
            validated_result = self.validator.validate_and_sanitize(raw_json, ground_truth_entities)
            return validated_result

        except Exception as e:
            logger.warning("LLM generation failed (%s); using deterministic fallback.", str(e))
            return self.fallback.analyze(
                exception_type=exception.exception_type,
                amount_involved=exception.amount_involved,
                variance=exception.variance,
                evidence_graph=evidence_graph,
            )
