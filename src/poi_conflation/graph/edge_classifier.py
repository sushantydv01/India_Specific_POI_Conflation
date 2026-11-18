"""Configurable edge classifier for bipartite conflation graph.

Assigns each candidate pair into one of four topological graph tiers:
- STRONG_MATCH_CANDIDATE: High-confidence equivalence candidate.
- POSSIBLE_MATCH: Plausible cross-source correspondence requiring topological verification.
- UNCERTAIN: Ambiguous relationship due to missing names, generic tokens, or marginal score.
- REJECTED: Disproven identity due to spatial separation, category disjointness, or branch divergence.
"""

from typing import Dict, Any, List, Optional
from src.poi_conflation.graph.schema import GraphEdgeClassification


HARD_REJECTION_GUARDRAILS = {
    "SAME_BUILDING_DIFFERENT_BUSINESS",
    "SAME_BRAND_DIFFERENT_BRANCH",
    "EXCESSIVE_SPATIAL_SEPARATION",
    "CATEGORY_DISJOINT",
}


class EdgeClassifier:
    """Classifies pairwise candidate edges into graph tiers based on scores and evidence."""

    def __init__(
        self,
        strong_min_score: float = 0.75,
        possible_min_score: float = 0.55,
        uncertain_min_score: float = 0.40,
        max_strong_distance_meters: float = 50.0,
    ):
        self.strong_min_score = strong_min_score
        self.possible_min_score = possible_min_score
        self.uncertain_min_score = uncertain_min_score
        self.max_strong_distance_meters = max_strong_distance_meters

    def classify_edge(
        self,
        score: float,
        decision: str,
        guardrails: List[str],
        features: Optional[Dict[str, float]] = None,
    ) -> GraphEdgeClassification:
        """Classify a single candidate edge."""
        # Check hard rejection guardrails
        for g in guardrails:
            if g in HARD_REJECTION_GUARDRAILS:
                return GraphEdgeClassification.REJECTED

        if decision == "NON_MATCH" or score < self.uncertain_min_score:
            return GraphEdgeClassification.REJECTED

        is_empty = False
        dist_m = 0.0
        if features:
            is_empty = features.get("feat_is_empty_name", 0.0) == 1.0
            dist_m = features.get("feat_distance_meters", 0.0)

        if "INSUFFICIENT_NAME_EVIDENCE" in guardrails or is_empty:
            return GraphEdgeClassification.UNCERTAIN

        if score >= self.strong_min_score and decision == "MATCH":
            if dist_m <= self.max_strong_distance_meters or features.get("feat_exact_name_match", 0.0) == 1.0:
                return GraphEdgeClassification.STRONG_MATCH_CANDIDATE
            return GraphEdgeClassification.POSSIBLE_MATCH

        if score >= self.possible_min_score:
            return GraphEdgeClassification.POSSIBLE_MATCH

        return GraphEdgeClassification.UNCERTAIN
