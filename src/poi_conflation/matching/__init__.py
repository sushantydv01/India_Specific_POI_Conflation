"""Explainable POI matching package.

Provides configuration loading, deterministic score evaluation, contradiction guardrails,
and structured evidence reporting.
"""

from src.poi_conflation.matching.config import MatchingConfig
from src.poi_conflation.matching.engine import (
    MatchingDecision,
    ExplainableMatchingEngine,
)
from src.poi_conflation.matching.engine_v2 import ExplainableMatchingEngineV2
from src.poi_conflation.matching.normalization import EnhancedNameNormalizer
from src.poi_conflation.matching.evaluator import BaselineEvaluator

__all__ = [
    "MatchingConfig",
    "MatchingDecision",
    "ExplainableMatchingEngine",
    "ExplainableMatchingEngineV2",
    "EnhancedNameNormalizer",
    "BaselineEvaluator",
]
