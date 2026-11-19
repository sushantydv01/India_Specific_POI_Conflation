"""Supervised canonical entity resolver and cluster disambiguation engine.

Resolves bipartite conflation graph components into canonical POI entities
while enforcing domain safeguards, preserving source provenance, isolating
parent-child relations, and ensuring 100% source-record inventory accounting.
"""

import logging
import uuid
from typing import Dict, Any, List, Set, Optional, Tuple
from collections import defaultdict

from src.poi_conflation.graph.schema import (
    GraphNode,
    GraphEdge,
    EntityCluster,
    CanonicalEntity,
    CanonicalResolutionDecision,
    ClusterStructuralPattern,
    EdgeDisposition,
    POIRelationship,
    POIRelationshipType,
    UnresolvedPair,
    CANONICAL_RESOLUTION_POLICY_VERSION,
)
from src.poi_conflation.graph.canonical_resolver import (
    generate_canonical_uuid,
    CANONICAL_ENTITY_NAMESPACE,
)

logger = logging.getLogger("supervised_resolver")


class SupervisedCanonicalResolver:
    """Resolves bipartite entity clusters into canonical POIs with full provenance accounting."""

    def __init__(
        self,
        policy_version: str = "supervised_conflation_v1",
        dominance_margin_threshold: float = 0.15,
        min_equivalence_score: float = 0.55,
        max_equivalence_distance: float = 50.0,
    ):
        self.policy_version = policy_version
        self.dominance_margin_threshold = dominance_margin_threshold
        self.min_equivalence_score = min_equivalence_score
        self.max_equivalence_distance = max_equivalence_distance

    def resolve_graph(
        self,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
        clusters: List[EntityCluster],
        relationships: List[POIRelationship],
    ) -> Tuple[List[CanonicalEntity], List[UnresolvedPair]]:
        """Resolve all clusters and singletons into canonical entities and extract unresolved pairs."""
        canonical_entities: List[CanonicalEntity] = []
        unresolved_pairs: List[UnresolvedPair] = []
        clustered_node_ids: Set[str] = set()

        # Track node usage to guarantee 100% accounting and zero duplicates
        assigned_osm_nodes: Set[str] = set()
        assigned_ov_nodes: Set[str] = set()

        for cluster in clusters:
            clustered_node_ids.update(cluster.osm_node_ids)
            clustered_node_ids.update(cluster.ov_node_ids)

            cluster_entities, cluster_unresolved = self._resolve_cluster(
                cluster, nodes, edges
            )
            for ent in cluster_entities:
                canonical_entities.append(ent)
                for osm_id in ent.contributing_osm_ids:
                    assert osm_id not in assigned_osm_nodes, f"Duplicate OSM assignment: {osm_id}"
                    assigned_osm_nodes.add(osm_id)
                for ov_id in ent.contributing_ov_ids:
                    assert ov_id not in assigned_ov_nodes, f"Duplicate Overture assignment: {ov_id}"
                    assigned_ov_nodes.add(ov_id)

            unresolved_pairs.extend(cluster_unresolved)

        # Account for all unclustered / isolated source POIs as singletons
        for node_id, node in nodes.items():
            if node_id not in clustered_node_ids:
                singleton = self._create_singleton(node)
                canonical_entities.append(singleton)
                if node.source == "OSM":
                    assert node_id not in assigned_osm_nodes, f"Duplicate unclustered OSM assignment: {node_id}"
                    assigned_osm_nodes.add(node_id)
                else:
                    assert node_id not in assigned_ov_nodes, f"Duplicate unclustered Overture assignment: {node_id}"
                    assigned_ov_nodes.add(node_id)

        # Verification of complete accounting
        osm_total = sum(1 for n in nodes.values() if n.source == "OSM")
        ov_total = sum(1 for n in nodes.values() if n.source == "OVERTURE")

        assert len(assigned_osm_nodes) == osm_total, (
            f"OSM accounting mismatch: {len(assigned_osm_nodes)} assigned vs {osm_total} total"
        )
        assert len(assigned_ov_nodes) == ov_total, (
            f"Overture accounting mismatch: {len(assigned_ov_nodes)} assigned vs {ov_total} total"
        )
        assert len(canonical_entities) == len({e.canonical_entity_id for e in canonical_entities}), (
            "Collision detected in canonical entity IDs!"
        )

        return canonical_entities, unresolved_pairs

    def _resolve_cluster(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> Tuple[List[CanonicalEntity], List[UnresolvedPair]]:
        """Resolve a single entity cluster based on structural pattern."""
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
    ) -> Tuple[List[CanonicalEntity], List[UnresolvedPair]]:
        """Resolve a 1:1 clean equivalence cluster."""
        osm_id = cluster.osm_node_ids[0]
        ov_id = cluster.ov_node_ids[0]
        osm_node = nodes[osm_id]
        ov_node = nodes[ov_id]

        pair_id = cluster.edge_pair_ids[0]
        edge = edges[pair_id]

        # Equivalence resolution
        can_id = generate_canonical_uuid([osm_id], [ov_id])
        prim_name, alt_names = self._select_display_name(osm_node, ov_node)
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
                f"1:1 Equivalence: model_score={edge.supervised_model_score:.4f}, distance={edge.distance_meters:.1f}m",
                f"Taxonomies: OSM='{osm_node.category}', Overture='{ov_node.category}'",
            ],
            source_coordinates={
                "OSM": {"latitude": osm_node.latitude, "longitude": osm_node.longitude},
                "OVERTURE": {"latitude": ov_node.latitude, "longitude": ov_node.longitude},
            },
            confidence_score=edge.supervised_model_score or 1.0,
            alternate_names=alt_names,
        )
        return [entity], []

    def _resolve_star_cluster(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> Tuple[List[CanonicalEntity], List[UnresolvedPair]]:
        """Resolve a star cluster using dominance margin check."""
        cluster_edges = [edges[pid] for pid in cluster.edge_pair_ids if pid in edges]
        cluster_edges.sort(key=lambda e: (e.supervised_model_score or 0.0), reverse=True)

        if not cluster_edges:
            return self._create_unresolved_entities(cluster, nodes), []

        top_edge = cluster_edges[0]
        top_score = top_edge.supervised_model_score or 0.0
        second_score = cluster_edges[1].supervised_model_score or 0.0 if len(cluster_edges) > 1 else 0.0
        margin = top_score - second_score

        # Check for dominance: top score >= 0.70 and margin >= 0.15
        if top_score >= 0.70 and margin >= self.dominance_margin_threshold:
            resolved_osm = top_edge.osm_source_id
            resolved_ov = top_edge.ov_source_id
            osm_node = nodes[resolved_osm]
            ov_node = nodes[resolved_ov]

            can_id = generate_canonical_uuid([resolved_osm], [resolved_ov])
            prim_name, alt_names = self._select_display_name(osm_node, ov_node)
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
                    f"Dominant star winner: score={top_score:.4f}, margin={margin:.4f} over runner-up ({second_score:.4f})",
                ],
                source_coordinates={
                    "OSM": {"latitude": osm_node.latitude, "longitude": osm_node.longitude},
                    "OVERTURE": {"latitude": ov_node.latitude, "longitude": ov_node.longitude},
                },
                confidence_score=top_score,
                alternate_names=alt_names,
            )

            entities = [dominant_entity]
            unresolved = []

            # Remaining nodes become disambiguated singletons
            for oid in cluster.osm_node_ids:
                if oid != resolved_osm:
                    entities.append(self._create_singleton(nodes[oid], cluster.cluster_id))
            for ovid in cluster.ov_node_ids:
                if ovid != resolved_ov:
                    entities.append(self._create_singleton(nodes[ovid], cluster.cluster_id))

            # Runner-up edges queued in unresolved pairs
            for edge in cluster_edges[1:]:
                o_n = nodes[edge.osm_source_id]
                ov_n = nodes[edge.ov_source_id]
                unresolved.append(
                    UnresolvedPair(
                        candidate_pair_id=edge.pair_id,
                        osm_source_id=edge.osm_source_id,
                        ov_source_id=edge.ov_source_id,
                        osm_name=o_n.name,
                        ov_name=ov_n.name,
                        osm_category=o_n.category,
                        ov_category=ov_n.category,
                        distance_meters=edge.distance_meters,
                        supervised_model_score=edge.supervised_model_score or 0.0,
                        supervised_decision=edge.supervised_decision or "UNCERTAIN",
                        safeguards_triggered=["STAR_RUNNER_UP_SUBORDINATED"],
                        review_reason=f"Subordinated star candidate: score={edge.supervised_model_score:.4f} defeated by dominant winner ({top_score:.4f})",
                        priority_rank=2,
                    )
                )

            return entities, unresolved

        # Competing close edges without dominance: hold all nodes as UNRESOLVED_AMBIGUOUS
        unresolved_entities = self._create_unresolved_entities(cluster, nodes)
        unresolved_edges = []
        for edge in cluster_edges:
            o_n = nodes[edge.osm_source_id]
            ov_n = nodes[edge.ov_source_id]
            unresolved_edges.append(
                UnresolvedPair(
                    candidate_pair_id=edge.pair_id,
                    osm_source_id=edge.osm_source_id,
                    ov_source_id=edge.ov_source_id,
                    osm_name=o_n.name,
                    ov_name=ov_n.name,
                    osm_category=o_n.category,
                    ov_category=ov_n.category,
                    distance_meters=edge.distance_meters,
                    supervised_model_score=edge.supervised_model_score or 0.0,
                    supervised_decision=edge.supervised_decision or "UNCERTAIN",
                    safeguards_triggered=["CLOSE_COMPETING_STAR_EDGES"],
                    review_reason=f"Ambiguous star collision: top score {top_score:.4f} vs runner-up {second_score:.4f} (margin {margin:.4f} < {self.dominance_margin_threshold})",
                    priority_rank=1,
                )
            )

        return unresolved_entities, unresolved_edges

    def _resolve_ambiguous_cluster(
        self,
        cluster: EntityCluster,
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> Tuple[List[CanonicalEntity], List[UnresolvedPair]]:
        """Preserve complex multi-node clusters as unresolved ambiguous entities without merging."""
        entities = self._create_unresolved_entities(cluster, nodes)
        unresolved = []
        for pid in cluster.edge_pair_ids:
            if pid in edges:
                e = edges[pid]
                o_n = nodes[e.osm_source_id]
                ov_n = nodes[e.ov_source_id]
                unresolved.append(
                    UnresolvedPair(
                        candidate_pair_id=e.pair_id,
                        osm_source_id=e.osm_source_id,
                        ov_source_id=e.ov_source_id,
                        osm_name=o_n.name,
                        ov_name=ov_n.name,
                        osm_category=o_n.category,
                        ov_category=ov_n.category,
                        distance_meters=e.distance_meters,
                        supervised_model_score=e.supervised_model_score or 0.0,
                        supervised_decision=e.supervised_decision or "UNCERTAIN",
                        safeguards_triggered=["COMPLEX_N_M_GRAPH_CLUSTER"],
                        review_reason=f"Complex multi-node component ({len(cluster.osm_node_ids)} OSM, {len(cluster.ov_node_ids)} Overture); held for manual graph resolution",
                        priority_rank=1,
                    )
                )
        return entities, unresolved

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
            primary_name=node.name or node.normalized_name or "Unnamed POI",
            source_names={node.source: [node.name]},
            primary_category=node.category or "other",
            source_categories={node.source: [node.category]},
            latitude=node.latitude,
            longitude=node.longitude,
            utm_x=node.utm_x,
            utm_y=node.utm_y,
            cluster_id=cluster_id,
            resolution_evidence=["Single-source entity; no valid counterpart edge found"],
            source_coordinates={
                node.source: {"latitude": node.latitude, "longitude": node.longitude}
            },
            confidence_score=1.0,
            alternate_names=[],
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
            if cluster.geographic_spread_meters > 50.0:
                conflicts.append(f"Geographic spread across candidates: {cluster.geographic_spread_meters:.1f}m")
            if not cluster.category_consistent:
                conflicts.append(f"Incompatible categories present: {', '.join(cluster.categories_present)}")
            if cluster.competing_edge_count > 0:
                conflicts.append(f"Competing edges with close scores ({cluster.competing_edge_count})")

            entities.append(
                CanonicalEntity(
                    canonical_entity_id=can_id,
                    resolution_decision=CanonicalResolutionDecision.UNRESOLVED_AMBIGUOUS,
                    resolution_policy=self.policy_version,
                    contributing_osm_ids=osm_ids,
                    contributing_ov_ids=ov_ids,
                    primary_name=node.name or node.normalized_name or "Unnamed POI",
                    source_names={node.source: [node.name]},
                    primary_category=node.category or "other",
                    source_categories={node.source: [node.category]},
                    latitude=node.latitude,
                    longitude=node.longitude,
                    utm_x=node.utm_x,
                    utm_y=node.utm_y,
                    cluster_id=cluster.cluster_id,
                    cluster_pattern=cluster.pattern.value,
                    resolution_evidence=["Held in UNRESOLVED_AMBIGUOUS status pending manual adjudication"],
                    conflict_notes=conflicts,
                    source_coordinates={
                        node.source: {"latitude": node.latitude, "longitude": node.longitude}
                    },
                    confidence_score=cluster.score_max,
                    alternate_names=[],
                )
            )
        return entities

    def _select_display_name(self, osm_node: GraphNode, ov_node: GraphNode) -> Tuple[str, List[str]]:
        """Select primary display name deterministically and compile alternate names."""
        osm_name = (osm_node.name or "").strip()
        ov_name = (ov_node.name or "").strip()

        alternates: List[str] = []
        if osm_name and ov_name and osm_name != ov_name:
            alternates.append(ov_name)

        # Prefer non-empty official name
        # If OSM name has English and is not generic, prefer OSM name; else Overture
        if osm_name and not ov_name:
            return osm_name, alternates
        if ov_name and not osm_name:
            return ov_name, alternates

        # If both exist: prefer the more descriptive, non-abbreviated name
        if len(osm_name) >= len(ov_name):
            return osm_name, alternates
        return ov_name, [osm_name]
