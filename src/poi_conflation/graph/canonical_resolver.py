"""Conservative canonical entity resolution engine.

Converts bipartite conflation graph components into canonical POI entities
while preserving source provenance, isolating parent-child relations,
and preventing transitive over-merging in dense urban environments.
"""

import uuid
from typing import Dict, Any, List, Set, Optional, Tuple

from src.poi_conflation.graph.schema import (
    GraphNode,
    GraphEdge,
    EntityCluster,
    CanonicalEntity,
    CanonicalResolutionDecision,
    ClusterStructuralPattern,
    CANONICAL_RESOLUTION_POLICY_VERSION,
)

CANONICAL_ENTITY_NAMESPACE = uuid.UUID("9a8bf37f-af65-5399-9fab-35bcd714c702")
CANONICAL_NAMESPACE = CANONICAL_ENTITY_NAMESPACE

# Container / Parent POI keywords common in Indian urban centers
CONTAINER_KEYWORDS = {
    "mall", "complex", "plaza", "center", "centre", "arcade",
    "bazaar", "hospital", "campus", "towers", "tower", "enclave"
}


def generate_canonical_uuid(osm_ids: List[str], ov_ids: List[str]) -> str:
    """Generate deterministic, collision-free UUIDv5 from sorted source constituent IDs."""
    key = f"osm:{','.join(sorted(osm_ids))}|ov:{','.join(sorted(ov_ids))}"
    return str(uuid.uuid5(CANONICAL_ENTITY_NAMESPACE, key))


class CanonicalEntityResolver:
    """Resolves bipartite entity clusters into canonical POI representations."""

    def __init__(
        self,
        policy_version: str = CANONICAL_RESOLUTION_POLICY_VERSION,
        dominance_margin_threshold: float = 0.25,
        max_equivalence_distance: float = 50.0,
        min_equivalence_score: float = 0.70,
    ):
        self.policy_version = policy_version
        self.dominance_margin_threshold = dominance_margin_threshold
        self.max_equivalence_distance = max_equivalence_distance
        self.min_equivalence_score = min_equivalence_score

    def resolve_cluster(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> List[CanonicalEntity]:
        """Resolve an EntityCluster into one or more CanonicalEntity records."""
        # 1. 1:1 Clean Pairwise Component
        if cluster.pattern == ClusterStructuralPattern.ONE_TO_ONE:
            return self._resolve_one_to_one(cluster, nodes, edges)

        # 2. 1:N or N:1 Star Component
        if cluster.pattern in (ClusterStructuralPattern.ONE_TO_MANY, ClusterStructuralPattern.MANY_TO_ONE):
            return self._resolve_star_cluster(cluster, nodes, edges)

        # 3. Many-to-Many or Ambiguous Component
        return self._resolve_ambiguous_cluster(cluster, nodes, edges)

    def _resolve_one_to_one(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> List[CanonicalEntity]:
        """Resolve a 1:1 component."""
        osm_id = cluster.osm_node_ids[0]
        ov_id = cluster.ov_node_ids[0]
        osm_node = nodes[osm_id]
        ov_node = nodes[ov_id]

        pair_id = cluster.edge_pair_ids[0]
        edge = edges[pair_id]

        # Check for container parent-child relationship
        is_parent_child, parent_node, child_node = self._check_parent_child(osm_node, ov_node, edge)
        if is_parent_child and parent_node and child_node:
            parent_id = generate_canonical_uuid([parent_node.node_id] if parent_node.source == "OSM" else [], [parent_node.node_id] if parent_node.source == "OVERTURE" else [])
            parent_entity = CanonicalEntity(
                canonical_entity_id=parent_id,
                resolution_decision=CanonicalResolutionDecision.PARENT_CHILD,
                resolution_policy=self.policy_version,
                contributing_osm_ids=[parent_node.node_id] if parent_node.source == "OSM" else [],
                contributing_ov_ids=[parent_node.node_id] if parent_node.source == "OVERTURE" else [],
                primary_name=parent_node.name or parent_node.normalized_name,
                source_names={parent_node.source: [parent_node.name]},
                primary_category=parent_node.category,
                source_categories={parent_node.source: [parent_node.category]},
                latitude=parent_node.latitude,
                longitude=parent_node.longitude,
                utm_x=parent_node.utm_x,
                utm_y=parent_node.utm_y,
                cluster_id=cluster.cluster_id,
                cluster_pattern=cluster.pattern.value,
                resolution_evidence=[f"Container entity parent ({parent_node.name})"],
            )

            child_id = generate_canonical_uuid([child_node.node_id] if child_node.source == "OSM" else [], [child_node.node_id] if child_node.source == "OVERTURE" else [])
            child_entity = CanonicalEntity(
                canonical_entity_id=child_id,
                resolution_decision=CanonicalResolutionDecision.PARENT_CHILD,
                resolution_policy=self.policy_version,
                contributing_osm_ids=[child_node.node_id] if child_node.source == "OSM" else [],
                contributing_ov_ids=[child_node.node_id] if child_node.source == "OVERTURE" else [],
                primary_name=child_node.name or child_node.normalized_name,
                source_names={child_node.source: [child_node.name]},
                primary_category=child_node.category,
                source_categories={child_node.source: [child_node.category]},
                latitude=child_node.latitude,
                longitude=child_node.longitude,
                utm_x=child_node.utm_x,
                utm_y=child_node.utm_y,
                cluster_id=cluster.cluster_id,
                cluster_pattern=cluster.pattern.value,
                parent_entity_id=parent_id,
                resolution_evidence=[f"Collocated child establishment ({child_node.name}) inside {parent_node.name}"],
            )
            return [parent_entity, child_entity]

        # Equivalence resolution
        if edge.matching_score >= self.min_equivalence_score and edge.distance_meters <= self.max_equivalence_distance and cluster.category_consistent:
            can_id = generate_canonical_uuid([osm_id], [ov_id])
            # Primary name: prefer OSM name if available, else Overture
            prim_name = osm_node.name or ov_node.name or osm_node.normalized_name
            # Primary category: prefer specific category over 'other'
            prim_cat = osm_node.category if osm_node.category != "other" else ov_node.category

            entity = CanonicalEntity(
                canonical_entity_id=can_id,
                resolution_decision=CanonicalResolutionDecision.RESOLVED_EQUIVALENCE,
                resolution_policy=self.policy_version,
                contributing_osm_ids=[osm_id],
                contributing_ov_ids=[ov_id],
                primary_name=prim_name,
                source_names={"OSM": [osm_node.name], "OVERTURE": [ov_node.name]},
                primary_category=prim_cat,
                source_categories={"OSM": [osm_node.category], "OVERTURE": [ov_node.category]},
                latitude=osm_node.latitude,
                longitude=osm_node.longitude,
                utm_x=osm_node.utm_x,
                utm_y=osm_node.utm_y,
                cluster_id=cluster.cluster_id,
                cluster_pattern=cluster.pattern.value,
                resolution_evidence=[
                    f"1:1 Equivalence: Score={edge.matching_score:.2f}, Dist={edge.distance_meters:.1f}m",
                    f"Categories: OSM='{osm_node.category}', Overture='{ov_node.category}'",
                ],
            )
            return [entity]

        # Otherwise ambiguous 1:1
        return self._create_unresolved_entities(cluster, nodes)

    def _resolve_star_cluster(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> List[CanonicalEntity]:
        """Resolve a 1:N or N:1 cluster with dominance or ambiguity detection."""
        cluster_edges = [edges[pid] for pid in cluster.edge_pair_ids if pid in edges]
        cluster_edges.sort(key=lambda e: e.matching_score, reverse=True)

        if not cluster_edges:
            return self._create_unresolved_entities(cluster, nodes)

        top_edge = cluster_edges[0]
        second_score = cluster_edges[1].matching_score if len(cluster_edges) > 1 else 0.0
        margin = top_edge.matching_score - second_score

        # If top edge is dominant (score >= 0.75 and margin >= 0.25)
        if top_edge.matching_score >= 0.75 and margin >= self.dominance_margin_threshold:
            resolved_osm = top_edge.osm_source_id
            resolved_ov = top_edge.ov_source_id
            osm_node = nodes[resolved_osm]
            ov_node = nodes[resolved_ov]

            can_id = generate_canonical_uuid([resolved_osm], [resolved_ov])
            prim_name = osm_node.name or ov_node.name or osm_node.normalized_name
            prim_cat = osm_node.category if osm_node.category != "other" else ov_node.category

            dominant_entity = CanonicalEntity(
                canonical_entity_id=can_id,
                resolution_decision=CanonicalResolutionDecision.RESOLVED_EQUIVALENCE,
                resolution_policy=self.policy_version,
                contributing_osm_ids=[resolved_osm],
                contributing_ov_ids=[resolved_ov],
                primary_name=prim_name,
                source_names={"OSM": [osm_node.name], "OVERTURE": [ov_node.name]},
                primary_category=prim_cat,
                source_categories={"OSM": [osm_node.category], "OVERTURE": [ov_node.category]},
                latitude=osm_node.latitude,
                longitude=osm_node.longitude,
                utm_x=osm_node.utm_x,
                utm_y=osm_node.utm_y,
                cluster_id=cluster.cluster_id,
                cluster_pattern=cluster.pattern.value,
                resolution_evidence=[
                    f"Dominant star edge resolved: Score={top_edge.matching_score:.2f}, Margin={margin:.2f} over runner-up ({second_score:.2f})",
                ],
            )

            results = [dominant_entity]

            # Remaining nodes become disambiguated singletons
            for oid in cluster.osm_node_ids:
                if oid != resolved_osm:
                    results.append(self._create_singleton(nodes[oid], cluster.cluster_id))
            for ovid in cluster.ov_node_ids:
                if ovid != resolved_ov:
                    results.append(self._create_singleton(nodes[ovid], cluster.cluster_id))

            return results

        # If margin is small or top edge is weak, hold as unresolved ambiguous
        return self._create_unresolved_entities(cluster, nodes)

    def _resolve_ambiguous_cluster(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> List[CanonicalEntity]:
        """Mark cluster members as unresolved ambiguous entities to prevent over-merging."""
        return self._create_unresolved_entities(cluster, nodes)

    def _create_singleton(self, node: GraphNode, cluster_id: Optional[str] = None) -> CanonicalEntity:
        """Create a single-source canonical POI entity."""
        osm_ids = [node.node_id] if node.source == "OSM" else []
        ov_ids = [node.node_id] if node.source == "OVERTURE" else []
        can_id = generate_canonical_uuid(osm_ids, ov_ids)

        return CanonicalEntity(
            canonical_entity_id=can_id,
            resolution_decision=CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON,
            resolution_policy=self.policy_version,
            contributing_osm_ids=osm_ids,
            contributing_ov_ids=ov_ids,
            primary_name=node.name or node.normalized_name,
            source_names={node.source: [node.name]},
            primary_category=node.category,
            source_categories={node.source: [node.category]},
            latitude=node.latitude,
            longitude=node.longitude,
            utm_x=node.utm_x,
            utm_y=node.utm_y,
            cluster_id=cluster_id,
            resolution_evidence=["Single-source entity; no valid counterpart edge found"],
        )

    def _create_unresolved_entities(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
    ) -> List[CanonicalEntity]:
        """Preserve cluster members as unresolved ambiguous entities without merging."""
        entities = []
        for nid in cluster.osm_node_ids + cluster.ov_node_ids:
            node = nodes[nid]
            osm_ids = [node.node_id] if node.source == "OSM" else []
            ov_ids = [node.node_id] if node.source == "OVERTURE" else []
            can_id = generate_canonical_uuid(osm_ids, ov_ids)

            conflicts = []
            if cluster.geographic_spread_meters > 100.0:
                conflicts.append(f"Excessive geographic spread: {cluster.geographic_spread_meters:.1f}m")
            if not cluster.category_consistent:
                conflicts.append(f"Incompatible categories in cluster: {', '.join(cluster.categories_present)}")
            if cluster.competing_edge_count > 0:
                conflicts.append(f"Competing edges with close scores ({cluster.competing_edge_count})")
            if cluster.has_rejected_edges:
                conflicts.append("Contains hard-rejected candidate edges between members")

            entities.append(
                CanonicalEntity(
                    canonical_entity_id=can_id,
                    resolution_decision=CanonicalResolutionDecision.UNRESOLVED_AMBIGUOUS,
                    resolution_policy=self.policy_version,
                    contributing_osm_ids=osm_ids,
                    contributing_ov_ids=ov_ids,
                    primary_name=node.name or node.normalized_name,
                    source_names={node.source: [node.name]},
                    primary_category=node.category,
                    source_categories={node.source: [node.category]},
                    latitude=node.latitude,
                    longitude=node.longitude,
                    utm_x=node.utm_x,
                    utm_y=node.utm_y,
                    cluster_id=cluster.cluster_id,
                    cluster_pattern=cluster.pattern.value,
                    resolution_evidence=["Held in UNRESOLVED_AMBIGUOUS status pending adjudication"],
                    conflict_notes=conflicts,
                )
            )
        return entities

    def _check_parent_child(
        self,
        node_a: GraphNode,
        node_b: GraphNode,
        edge: GraphEdge,
    ) -> Tuple[bool, Optional[GraphNode], Optional[GraphNode]]:
        """Detect parent-child relation (e.g. mall containing store, hospital containing pharmacy)."""
        name_a = (node_a.name or "").lower()
        name_b = (node_b.name or "").lower()

        is_a_container = any(k in name_a for k in CONTAINER_KEYWORDS)
        is_b_container = any(k in name_b for k in CONTAINER_KEYWORDS)

        # One entity is container and the other is a distinct specific commercial business
        if is_a_container and not is_b_container and edge.distance_meters <= 50.0:
            if node_a.category in ("commercial_services", "civic_religious", "healthcare") and node_b.category in ("retail", "sustenance", "healthcare"):
                return (True, node_a, node_b)

        if is_b_container and not is_a_container and edge.distance_meters <= 50.0:
            if node_b.category in ("commercial_services", "civic_religious", "healthcare") and node_a.category in ("retail", "sustenance", "healthcare"):
                return (True, node_b, node_a)

        return (False, None, None)
