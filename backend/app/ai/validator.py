"""Validator for AI-generated investigation outputs."""
import json
import logging
from typing import Any

from app.ai.schemas import AIAnalysisResult

logger = logging.getLogger(__name__)


class AIOutputValidator:
    """Verifies that AI analysis is mathematically sound and grounded in observed evidence."""

    @staticmethod
    def validate_and_sanitize(
        raw_output: str | dict[str, Any],
        ground_truth_entities: set[str],
    ) -> AIAnalysisResult:
        """
        Parses JSON if necessary, checks against Pydantic schema, and audits
        against hallucinated tokens/values.
        """
        if isinstance(raw_output, str):
            clean_str = raw_output.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            data = json.loads(clean_str.strip())
        else:
            data = raw_output

        parsed = AIAnalysisResult.model_validate(data)

        # Grounding check: verify that supporting evidence elements relate to known data
        hallucination_detected = False
        unsupported_items = []

        for item in parsed.supporting_evidence:
            item_str = str(item).strip()
            # If item is not in ground truth entities nor a substring of any node data
            matched = any(item_str.lower() in gt.lower() or gt.lower() in item_str.lower() for gt in ground_truth_entities)
            if not matched:
                unsupported_items.append(item_str)
                hallucination_detected = True

        if hallucination_detected:
            logger.warning(
                "AI output contained unsupported evidence items: %s. Demoting confidence and flagging human review.",
                unsupported_items,
            )
            # Demote confidence and mandate human review
            sanitized_confidence = max(0.0, min(float(parsed.confidence) - 0.3, 0.5))
            return AIAnalysisResult(
                classification=parsed.classification,
                explanation=f"{parsed.explanation} [NOTE: Certain citations were unverified by audit graph]",
                supporting_evidence=[e for e in parsed.supporting_evidence if e not in unsupported_items],
                confidence=sanitized_confidence,
                recommended_action="ESCALATE_TO_HUMAN",
                missing_information=parsed.missing_information + [f"Unverified claims: {unsupported_items}"],
                requires_human_review=True,
            )

        return parsed
