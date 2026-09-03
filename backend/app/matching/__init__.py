"""Matching engine package for RECON-X.

Provides deterministic multi-level transaction matching (L1 to L4),
confidence scoring, and conflict resolution without relying on LLMs.
"""
from app.matching.engine import MatchingEngine
from app.matching.scorer import MatchStatus, ScoredMatch

__all__ = ["MatchingEngine", "MatchStatus", "ScoredMatch"]
