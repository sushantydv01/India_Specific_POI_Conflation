"""Explainable POI matching package.

Provides configuration loading, deterministic score evaluation, contradiction guardrails,
and structured evidence reporting.
"""

from src.poi_conflation.matching.config import MatchingConfig
from src.poi_conflation.matching.engine import (
    MatchingDecision,
    ExplainableMatchingEngine,
)

__all__ = [
    "MatchingConfig",
    "MatchingDecision",
    "ExplainableMatchingEngine",
]
