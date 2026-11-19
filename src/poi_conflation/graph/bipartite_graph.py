"""Bipartite conflation graph and connected component analysis.

Constructs an auditable bipartite graph between OpenStreetMap POIs (left partition)
and Overture Places (right partition), indexes multi-channel relationships,
discovers connected components, and evaluates structural patterns.
"""

import math
from typing import Dict, Any, List, Set, Optional, Tuple
from collections import defaultdict

from src.poi_conflation.graph.schema import (
    GraphNode,
    GraphEdge,
    EntityCluster,
    GraphEdgeClassification,
    ClusterStructuralPattern,
)
from src.poi_conflation.blocking.category import (
    CategoryCompatibilityClassifier,
    CategoryCompatibility,
)


class BipartiteConflationGraph:
    """Represents the bipartite graph between OSM and Overture POIs with clustering capabilities."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        # Full adjacency: node_id -> {neighbor_id: pair_id}
        self.adj: Dict[str, Dict[str, str]] = defaultdict(dict)
        # Active matching adjacency (STRONG and POSSIBLE match edges only)
        self.active_adj: Dict[str, Dict[str, str]] = defaultdict(dict)

    def add_node(self, node: GraphNode) -> None:
        """Register a POI node into the graph partition."""
        self.nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a bipartite candidate edge."""
        self.edges[edge.pair_id] = edge
        osm_id = edge.osm_source_id
        ov_id = edge.ov_source_id

        self.adj[osm_id][ov_id] = edge.pair_id
        self.adj[ov_id][osm_id] = edge.pair_id

        is_active = False
        if edge.disposition is not None:
            disp_val = edge.disposition.value if hasattr(edge.disposition, "value") else str(edge.disposition)
            is_active = (disp_val == "ACCEPTED_EQUIVALENCE")
        elif edge.classification in (
            GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            GraphEdgeClassification.POSSIBLE_MATCH,
        ):
            is_active = True

        if is_active:
            self.active_adj[osm_id][ov_id] = edge.pair_id
            self.active_adj[ov_id][osm_id] = edge.pair_id

    @property
    def osm_nodes_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.source == "OSM")

    @property
    def overture_nodes_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.source == "OVERTURE")

    @property
    def total_edges_count(self) -> int:
        return len(self.edges)

    def get_edge_classification_counts(self) -> Dict[str, int]:
        """Return counts of edges by classification tier."""
        counts = {cls.value: 0 for cls in GraphEdgeClassification}
        for edge in self.edges.values():
            counts[edge.classification.value] += 1
        return counts

    def find_connected_components(self, active_only: bool = True) -> List[EntityCluster]:
        """Discover connected components using BFS and construct EntityCluster objects."""
        target_adj = self.active_adj if active_only else self.adj
        visited: Set[str] = set()
        clusters: List[EntityCluster] = []
        cluster_idx = 1

        # Only iterate over nodes that have edges in target_adj
        active_nodes = sorted(list(target_adj.keys()))

        for start_node in active_nodes:
            if start_node in visited:
                continue

            # BFS traversal
            queue = [start_node]
            visited.add(start_node)
            comp_nodes: Set[str] = set()
            comp_edges: Set[str] = set()

            while queue:
                curr = queue.pop(0)
                comp_nodes.add(curr)
                for neighbor, pair_id in target_adj[curr].items():
                    comp_edges.add(pair_id)
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            cluster_id = f"CLUSTER-{cluster_idx:06d}"
            cluster = self._analyze_cluster(cluster_id, comp_nodes, list(comp_edges))
            clusters.append(cluster)
            cluster_idx += 1

        return clusters

    def _analyze_cluster(
        self,
        cluster_id: str,
        node_ids: Set[str],
        edge_pair_ids: List[str],
    ) -> EntityCluster:
        """Calculate metrics and classify topological pattern for a connected component."""
        osm_nodes = [nid for nid in node_ids if self.nodes[nid].source == "OSM"]
        ov_nodes = [nid for nid in node_ids if self.nodes[nid].source == "OVERTURE"]

        edges = [self.edges[pid] for pid in edge_pair_ids]
        scores = [e.matching_score for e in edges]
        min_score = min(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        mean_score = sum(scores) / len(scores) if scores else 0.0

        # Calculate geographic spread in UTM coordinates
        geo_spread = self._calculate_geographic_spread(node_ids)

        # Category consistency check
        categories = list(set(self.nodes[nid].category for nid in node_ids if self.nodes[nid].category))
        category_consistent = self._check_category_consistency(categories)

        # Competing edge detection (nodes with >1 active edges having |Delta S| <= 0.05)
        competing_count = self._detect_competing_edges(node_ids)

        # Check if any full graph edge between these nodes was rejected
        has_rejected = self._has_rejected_edges_between_nodes(node_ids)

        n_osm = len(osm_nodes)
        n_ov = len(ov_nodes)

        # Classify structural pattern
        is_ambiguous = (
            geo_spread > 100.0
            or not category_consistent
            or competing_count > 0
            or has_rejected
        )

        if n_osm == 1 and n_ov == 1:
            pattern = ClusterStructuralPattern.ONE_TO_ONE
        elif n_osm == 1 and n_ov > 1:
            pattern = ClusterStructuralPattern.AMBIGUOUS_CLUSTER if is_ambiguous else ClusterStructuralPattern.ONE_TO_MANY
        elif n_osm > 1 and n_ov == 1:
            pattern = ClusterStructuralPattern.AMBIGUOUS_CLUSTER if is_ambiguous else ClusterStructuralPattern.MANY_TO_ONE
        elif n_osm > 1 and n_ov > 1:
            pattern = ClusterStructuralPattern.AMBIGUOUS_CLUSTER if is_ambiguous else ClusterStructuralPattern.MANY_TO_MANY
        else:
            pattern = ClusterStructuralPattern.UNRESOLVED

        return EntityCluster(
            cluster_id=cluster_id,
            osm_node_ids=sorted(osm_nodes),
            ov_node_ids=sorted(ov_nodes),
            edge_pair_ids=sorted(edge_pair_ids),
            pattern=pattern,
            score_min=round(min_score, 4),
            score_max=round(max_score, 4),
            score_mean=round(mean_score, 4),
            geographic_spread_meters=round(geo_spread, 2),
            category_consistent=category_consistent,
            categories_present=sorted(categories),
            competing_edge_count=competing_count,
            has_rejected_edges=has_rejected,
            is_ambiguous=is_ambiguous,
        )

    def _calculate_geographic_spread(self, node_ids: Set[str]) -> float:
        """Calculate maximum pairwise planar distance (in metres) across cluster nodes."""
        coords = [(self.nodes[nid].utm_x, self.nodes[nid].utm_y) for nid in node_ids]
        if len(coords) <= 1:
            return 0.0

        # For small clusters (<= 15 nodes), compute exact maximum pairwise distance
        if len(coords) <= 15:
            max_d = 0.0
            for i in range(len(coords)):
                for j in range(i + 1, len(coords)):
                    dx = coords[i][0] - coords[j][0]
                    dy = coords[i][1] - coords[j][1]
                    d = math.sqrt(dx * dx + dy * dy)
                    if d > max_d:
                        max_d = d
            return max_d

        # For larger clusters, use bounding box diagonal as an upper bound
        min_x = min(c[0] for c in coords)
        max_x = max(c[0] for c in coords)
        min_y = min(c[1] for c in coords)
        max_y = max(c[1] for c in coords)
        return math.sqrt((max_x - min_x) ** 2 + (max_y - min_y) ** 2)

    def _check_category_consistency(self, categories: List[str]) -> bool:
        """Check if all categories in the cluster are mutually compatible."""
        if len(categories) <= 1:
            return True
        for i in range(len(categories)):
            for j in range(i + 1, len(categories)):
                compat, _ = CategoryCompatibilityClassifier.evaluate(categories[i], categories[j])
                if compat == CategoryCompatibility.INCOMPATIBLE:
                    return False
        return True

    def _detect_competing_edges(self, node_ids: Set[str]) -> int:
        """Detect nodes with multiple incident active edges whose scores are within 0.05."""
        competing = 0
        for nid in node_ids:
            incident = self.active_adj.get(nid, {})
            if len(incident) > 1:
                scores = [self.edges[pid].matching_score for pid in incident.values()]
                scores.sort(reverse=True)
                for i in range(len(scores) - 1):
                    if abs(scores[i] - scores[i + 1]) <= 0.05:
                        competing += 1
                        break
        return competing

    def _has_rejected_edges_between_nodes(self, node_ids: Set[str]) -> bool:
        """Check if any edge connecting members of this cluster was marked REJECTED."""
        for nid in node_ids:
            for neighbor_id, pid in self.adj.get(nid, {}).items():
                if neighbor_id in node_ids and pid in self.edges:
                    if self.edges[pid].classification == GraphEdgeClassification.REJECTED:
                        return True
        return False
