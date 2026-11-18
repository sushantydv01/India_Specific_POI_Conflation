"""Conflict and ambiguity analyzer with human review prioritization.

Identifies structural graph conflicts, competing candidate edges, category contradictions,
and builds an auditable, prioritized review queue for active human adjudication.
"""

from typing import Dict, Any, List, Set, Optional, Tuple

from src.poi_conflation.graph.schema import (
    GraphNode,
    GraphEdge,
    EntityCluster,
    AmbiguityType,
    PrioritizedReviewItem,
    ClusterStructuralPattern,
)


class AmbiguityAnalyzer:
    """Detects graph conflicts and generates prioritized human review queues."""

    def __init__(self, competing_score_delta: float = 0.05):
        self.competing_score_delta = competing_score_delta

    def analyze_conflicts(
        self,
        clusters: List[EntityCluster],
        nodes: Dict[str, GraphNode],
        edges: Dict[str, GraphEdge],
    ) -> Tuple[Dict[str, Any], List[PrioritizedReviewItem]]:
        """Scan all clusters, identify ambiguity types, and rank review priorities."""
        conflict_summary: Dict[str, int] = {
            AmbiguityType.COMPETING_HIGH_SCORE_EDGES.value: 0,
            AmbiguityType.CATEGORY_CONTRADICTION.value: 0,
            AmbiguityType.EXCESSIVE_GEOGRAPHIC_SPREAD.value: 0,
            AmbiguityType.MULTIPLE_BRANCHES_SAME_BRAND.value: 0,
            AmbiguityType.PARENT_CHILD_RELATION.value: 0,
            AmbiguityType.SAME_BUILDING_DISTINCT_BUSINESSES.value: 0,
            AmbiguityType.TRANSITIVE_BRIDGE_EDGE.value: 0,
        }

        review_items: List[PrioritizedReviewItem] = []
        item_counter = 1

        for cluster in clusters:
            # 1. Category Contradictions
            if not cluster.category_consistent and cluster.score_max >= 0.50:
                conflict_summary[AmbiguityType.CATEGORY_CONTRADICTION.value] += 1
                top_edge_id = cluster.edge_pair_ids[0] if cluster.edge_pair_ids else None
                top_edge = edges.get(top_edge_id) if top_edge_id else None
                osm_node = nodes.get(cluster.osm_node_ids[0]) if cluster.osm_node_ids else None
                ov_node = nodes.get(cluster.ov_node_ids[0]) if cluster.ov_node_ids else None

                review_items.append(
                    PrioritizedReviewItem(
                        item_id=f"REV-{item_counter:05d}",
                        priority_rank=1,  # Highest priority: category mismatch with high score
                        ambiguity_type=AmbiguityType.CATEGORY_CONTRADICTION,
                        cluster_id=cluster.cluster_id,
                        pair_id=top_edge_id,
                        osm_id=osm_node.node_id if osm_node else None,
                        ov_id=ov_node.node_id if ov_node else None,
                        osm_name=osm_node.name if osm_node else None,
                        ov_name=ov_node.name if ov_node else None,
                        osm_category=osm_node.category if osm_node else None,
                        ov_category=ov_node.category if ov_node else None,
                        score=cluster.score_max,
                        distance_meters=cluster.geographic_spread_meters,
                        reason_for_prioritization=(
                            f"Incompatible categories ({', '.join(cluster.categories_present)}) "
                            f"in cluster with score {cluster.score_max:.2f}"
                        ),
                    )
                )
                item_counter += 1

            # 2. Competing Edges with Close Scores
            if cluster.competing_edge_count > 0:
                conflict_summary[AmbiguityType.COMPETING_HIGH_SCORE_EDGES.value] += 1
                c_edges = [edges[pid] for pid in cluster.edge_pair_ids if pid in edges]
                c_edges.sort(key=lambda e: e.matching_score, reverse=True)
                if len(c_edges) >= 2:
                    e1, e2 = c_edges[0], c_edges[1]
                    delta = abs(e1.matching_score - e2.matching_score)
                    if delta <= self.competing_score_delta:
                        osm_node = nodes.get(e1.osm_source_id)
                        ov_node = nodes.get(e1.ov_source_id)
                        review_items.append(
                            PrioritizedReviewItem(
                                item_id=f"REV-{item_counter:05d}",
                                priority_rank=2,  # Close competing edges
                                ambiguity_type=AmbiguityType.COMPETING_HIGH_SCORE_EDGES,
                                cluster_id=cluster.cluster_id,
                                pair_id=e1.pair_id,
                                osm_id=e1.osm_source_id,
                                ov_id=e1.ov_source_id,
                                osm_name=osm_node.name if osm_node else None,
                                ov_name=ov_node.name if ov_node else None,
                                osm_category=osm_node.category if osm_node else None,
                                ov_category=ov_node.category if ov_node else None,
                                score=e1.matching_score,
                                distance_meters=e1.distance_meters,
                                reason_for_prioritization=(
                                    f"Competing candidates: top score {e1.matching_score:.2f} vs runner-up "
                                    f"{e2.matching_score:.2f} (delta = {delta:.3f} <= 0.05)"
                                ),
                            )
                        )
                        item_counter += 1

            # 3. Excessive Geographic Spread
            if cluster.geographic_spread_meters > 100.0:
                conflict_summary[AmbiguityType.EXCESSIVE_GEOGRAPHIC_SPREAD.value] += 1
                top_edge_id = cluster.edge_pair_ids[0] if cluster.edge_pair_ids else None
                top_edge = edges.get(top_edge_id) if top_edge_id else None
                osm_node = nodes.get(cluster.osm_node_ids[0]) if cluster.osm_node_ids else None
                ov_node = nodes.get(cluster.ov_node_ids[0]) if cluster.ov_node_ids else None

                review_items.append(
                    PrioritizedReviewItem(
                        item_id=f"REV-{item_counter:05d}",
                        priority_rank=3,
                        ambiguity_type=AmbiguityType.EXCESSIVE_GEOGRAPHIC_SPREAD,
                        cluster_id=cluster.cluster_id,
                        pair_id=top_edge_id,
                        osm_id=osm_node.node_id if osm_node else None,
                        ov_id=ov_node.node_id if ov_node else None,
                        osm_name=osm_node.name if osm_node else None,
                        ov_name=ov_node.name if ov_node else None,
                        osm_category=osm_node.category if osm_node else None,
                        ov_category=ov_node.category if ov_node else None,
                        score=cluster.score_max,
                        distance_meters=cluster.geographic_spread_meters,
                        reason_for_prioritization=(
                            f"Cluster spans {cluster.geographic_spread_meters:.1f}m (> 100m) in urban BBMP"
                        ),
                    )
                )
                item_counter += 1

            # 4. Transitive Bridge Edge Risks in Many-to-Many
            if cluster.pattern in (ClusterStructuralPattern.MANY_TO_MANY, ClusterStructuralPattern.AMBIGUOUS_CLUSTER):
                conflict_summary[AmbiguityType.TRANSITIVE_BRIDGE_EDGE.value] += 1

        # Sort review items by priority_rank, then by score descending
        review_items.sort(key=lambda item: (item.priority_rank, -item.score))

        # Re-assign sequential item IDs after sorting
        for idx, item in enumerate(review_items, 1):
            item.item_id = f"REV-{idx:05d}"

        report = {
            "total_ambiguous_clusters": sum(1 for c in clusters if c.is_ambiguous),
            "conflict_counts_by_type": conflict_summary,
            "total_review_items_queued": len(review_items),
            "priority_tier_counts": {
                "priority_1_category_contradiction": sum(1 for r in review_items if r.priority_rank == 1),
                "priority_2_competing_edges": sum(1 for r in review_items if r.priority_rank == 2),
                "priority_3_excessive_spread": sum(1 for r in review_items if r.priority_rank == 3),
            },
        }

        return report, review_items
