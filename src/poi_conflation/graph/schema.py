"""Schema definitions and data models for graph-based POI conflation and canonical entity resolution.

Defines enums, node/edge models, cluster representations, canonical entity structures,
and ambiguity classification models.
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Set, Optional, Tuple


GRAPH_SCHEMA_VERSION = "2.0.0"
CANONICAL_RESOLUTION_POLICY_VERSION = "supervised_conflation_v1"


class EdgeDisposition(str, Enum):
    """Final edge resolution disposition after graph consistency & domain safeguards."""
    ACCEPTED_EQUIVALENCE = "ACCEPTED_EQUIVALENCE"
    PARENT_CHILD = "PARENT_CHILD"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class POIRelationshipType(str, Enum):
    """Types of non-equivalence relationships between distinct POI entities."""
    PARENT_CHILD = "PARENT_CHILD"
    FACILITY_ATM = "FACILITY_ATM"
    CAMPUS_FACILITY = "CAMPUS_FACILITY"


class SafeguardType(str, Enum):
    """Domain-specific conflation safeguards preventing invalid pairwise merges."""
    ATM_VS_BANK_FACILITY_DISTINCTION = "ATM_VS_BANK_FACILITY_DISTINCTION"
    PARENT_CHILD_CONTAINER = "PARENT_CHILD_CONTAINER"
    SAME_BRAND_DIFFERENT_BRANCH = "SAME_BRAND_DIFFERENT_BRANCH"
    GENERIC_NAME_COLLISION = "GENERIC_NAME_COLLISION"
    SHARED_HONORIFIC_DISJOINT_BRAND = "SHARED_HONORIFIC_DISJOINT_BRAND"
    CATEGORY_INCOMPATIBLE = "CATEGORY_INCOMPATIBLE"
    EXCESSIVE_SPATIAL_SEPARATION = "EXCESSIVE_SPATIAL_SEPARATION"
    MISSING_OR_EMPTY_NAME = "MISSING_OR_EMPTY_NAME"
    SOURCE_NODE_COLLISION = "SOURCE_NODE_COLLISION"


class GraphEdgeClassification(str, Enum):
    """Classification tiers for candidate edges in the conflation graph."""
    STRONG_MATCH_CANDIDATE = "STRONG_MATCH_CANDIDATE"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"


class ClusterStructuralPattern(str, Enum):
    """Topological structural classification of connected components."""
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"
    AMBIGUOUS_CLUSTER = "AMBIGUOUS_CLUSTER"
    UNRESOLVED = "UNRESOLVED"


class CanonicalResolutionDecision(str, Enum):
    """Decision outcomes for canonical POI entity resolution."""
    RESOLVED_EQUIVALENCE = "RESOLVED_EQUIVALENCE"
    PARENT_CHILD = "PARENT_CHILD"
    DISAMBIGUATED_SINGLETON = "DISAMBIGUATED_SINGLETON"
    UNRESOLVED_AMBIGUOUS = "UNRESOLVED_AMBIGUOUS"


class AmbiguityType(str, Enum):
    """Taxonomy of conflation ambiguities and graph conflicts."""
    COMPETING_HIGH_SCORE_EDGES = "COMPETING_HIGH_SCORE_EDGES"
    CATEGORY_CONTRADICTION = "CATEGORY_CONTRADICTION"
    EXCESSIVE_GEOGRAPHIC_SPREAD = "EXCESSIVE_GEOGRAPHIC_SPREAD"
    MULTIPLE_BRANCHES_SAME_BRAND = "MULTIPLE_BRANCHES_SAME_BRAND"
    PARENT_CHILD_RELATION = "PARENT_CHILD_RELATION"
    SAME_BUILDING_DISTINCT_BUSINESSES = "SAME_BUILDING_DISTINCT_BUSINESSES"
    TRANSITIVE_BRIDGE_EDGE = "TRANSITIVE_BRIDGE_EDGE"


@dataclass
class GraphNode:
    """A single POI node in the bipartite conflation graph."""
    node_id: str                      # Canonical source ID (e.g. node/123 or GERS UUID)
    source: str                       # 'OSM' or 'OVERTURE'
    source_record_id: str
    name: str
    normalized_name: str
    category: str
    latitude: float
    longitude: float
    utm_x: float
    utm_y: float
    h3_res9: Optional[str] = None
    source_release: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    """An undirected bipartite edge between an OSM POI and an Overture Place."""
    pair_id: str                      # Candidate pair identifier (osm_id::ov_id)
    osm_source_id: str
    ov_source_id: str
    matching_score: float
    matching_decision: str            # 'MATCH', 'NON_MATCH', 'UNCERTAIN'
    classification: GraphEdgeClassification
    distance_meters: float
    name_similarity: float
    guardrails: List[str] = field(default_factory=list)
    blocking_strategies: List[str] = field(default_factory=list)
    positive_evidence: List[str] = field(default_factory=list)
    negative_evidence: List[str] = field(default_factory=list)
    model_version: str = "supervised_lgbm_poi_matcher_v1"
    supervised_model_score: Optional[float] = None
    supervised_decision: Optional[str] = None
    disposition: Optional[EdgeDisposition] = None
    disposition_reason: Optional[str] = None
    safeguards: List[str] = field(default_factory=list)
    explanation_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value
        if self.disposition:
            d["disposition"] = self.disposition.value if hasattr(self.disposition, "value") else str(self.disposition)
        return d


@dataclass
class EntityCluster:
    """A connected component or subgraph representing candidate entity relationships."""
    cluster_id: str
    osm_node_ids: List[str]
    ov_node_ids: List[str]
    edge_pair_ids: List[str]
    pattern: ClusterStructuralPattern
    score_min: float
    score_max: float
    score_mean: float
    geographic_spread_meters: float
    category_consistent: bool
    categories_present: List[str]
    competing_edge_count: int
    has_rejected_edges: bool
    is_ambiguous: bool

    @property
    def total_nodes(self) -> int:
        return len(self.osm_node_ids) + len(self.ov_node_ids)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["pattern"] = self.pattern.value
        return d


@dataclass
class CanonicalEntity:
    """A resolved canonical Point of Interest representing a physical establishment."""
    canonical_entity_id: str          # Stable deterministic UUIDv5 identifier
    resolution_decision: CanonicalResolutionDecision
    resolution_policy: str            # Version string, e.g. 'supervised_conflation_v1'
    contributing_osm_ids: List[str]
    contributing_ov_ids: List[str]
    primary_name: str
    source_names: Dict[str, List[str]]
    primary_category: str
    source_categories: Dict[str, List[str]]
    latitude: float
    longitude: float
    utm_x: float
    utm_y: float
    cluster_id: Optional[str] = None
    cluster_pattern: Optional[str] = None
    parent_entity_id: Optional[str] = None
    resolution_evidence: List[str] = field(default_factory=list)
    conflict_notes: List[str] = field(default_factory=list)
    source_coordinates: Dict[str, Dict[str, float]] = field(default_factory=dict)
    address_locality: Optional[str] = None
    address_postcode: Optional[str] = None
    confidence_score: float = 1.0
    alternate_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["resolution_decision"] = self.resolution_decision.value
        return d


@dataclass
class POIRelationship:
    """A non-equivalence relationship between distinct POI entities."""
    relationship_id: str
    relationship_type: POIRelationshipType
    parent_canonical_id: str
    parent_source_id: str
    child_canonical_id: str
    child_source_id: str
    parent_name: str
    child_name: str
    distance_meters: float
    confidence_score: float
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["relationship_type"] = self.relationship_type.value
        return d


@dataclass
class UnresolvedPair:
    """A candidate relationship held in review or unresolved status."""
    candidate_pair_id: str
    osm_source_id: str
    ov_source_id: str
    osm_name: str
    ov_name: str
    osm_category: str
    ov_category: str
    distance_meters: float
    supervised_model_score: float
    supervised_decision: str
    safeguards_triggered: List[str] = field(default_factory=list)
    review_reason: str = ""
    priority_rank: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrioritizedReviewItem:
    """A ranked conflict or ambiguous cluster routed for human review."""
    item_id: str                      # e.g. 'REV-001'
    priority_rank: int                # 1 = highest priority
    ambiguity_type: AmbiguityType
    cluster_id: str
    pair_id: Optional[str]
    osm_id: Optional[str]
    ov_id: Optional[str]
    osm_name: Optional[str]
    ov_name: Optional[str]
    osm_category: Optional[str]
    ov_category: Optional[str]
    score: float
    distance_meters: float
    reason_for_prioritization: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ambiguity_type"] = self.ambiguity_type.value
        return d
