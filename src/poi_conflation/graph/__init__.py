"""Graph-based POI conflation and canonical entity resolution package.

Provides bipartite graph representation, connected component analysis,
edge classification, conservative canonical resolution, and ambiguity detection.
"""

from src.poi_conflation.graph.schema import (
    GRAPH_SCHEMA_VERSION,
    CANONICAL_RESOLUTION_POLICY_VERSION,
    GraphEdgeClassification,
    ClusterStructuralPattern,
    CanonicalResolutionDecision,
    AmbiguityType,
    GraphNode,
    GraphEdge,
    EntityCluster,
    CanonicalEntity,
    PrioritizedReviewItem,
)
from src.poi_conflation.graph.edge_classifier import (
    EdgeClassifier,
    HARD_REJECTION_GUARDRAILS,
)
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph
from src.poi_conflation.graph.canonical_resolver import (
    CanonicalEntityResolver,
    CANONICAL_ENTITY_NAMESPACE,
    generate_canonical_uuid,
)
from src.poi_conflation.graph.ambiguity_analyzer import AmbiguityAnalyzer

__all__ = [
    "GRAPH_SCHEMA_VERSION",
    "CANONICAL_RESOLUTION_POLICY_VERSION",
    "GraphEdgeClassification",
    "ClusterStructuralPattern",
    "CanonicalResolutionDecision",
    "AmbiguityType",
    "GraphNode",
    "GraphEdge",
    "EntityCluster",
    "CanonicalEntity",
    "PrioritizedReviewItem",
    "CANONICAL_ENTITY_NAMESPACE",
    "generate_canonical_uuid",
    "EdgeClassifier",
    "HARD_REJECTION_GUARDRAILS",
    "BipartiteConflationGraph",
    "CanonicalEntityResolver",
    "AmbiguityAnalyzer",
]
