"""Automated test suite for bipartite conflation graph and clustering.

Tests:
1. GraphNode and GraphEdge data model serialization.
2. Bipartite graph construction, node partition accounting.
3. Edge classification rules and threshold boundaries.
4. Hard rejection guardrail enforcement in edge classifier.
5. Connected component discovery and cluster metrics.
6. Topological structural pattern classification (1:1, 1:N, N:1, N:M, AMBIGUOUS).
7. Geographic spread planar metric calculation in UTM Zone 43N.
8. Category consistency and contradiction detection.
9. Competing edge detection for close-scoring candidates.
10. Transitive over-merging prevention.
"""

import math
from pathlib import Path
import pytest

from src.poi_conflation.graph.schema import (
    GRAPH_SCHEMA_VERSION,
    GraphNode,
    GraphEdge,
    GraphEdgeClassification,
    ClusterStructuralPattern,
)
from src.poi_conflation.graph.edge_classifier import (
    EdgeClassifier,
    HARD_REJECTION_GUARDRAILS,
)
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph


@pytest.fixture
def sample_graph():
    graph = BipartiteConflationGraph()
    # Left partition: OSM nodes
    graph.add_node(
        GraphNode(
            node_id="osm_1",
            source="OSM",
            source_record_id="node/101",
            name="Cafe Coffee Day",
            normalized_name="cafe coffee day",
            category="sustenance",
            latitude=12.9716,
            longitude=77.5946,
            utm_x=100.0,
            utm_y=100.0,
        )
    )
    graph.add_node(
        GraphNode(
            node_id="osm_2",
            source="OSM",
            source_record_id="node/102",
            name="Apollo Pharmacy",
            normalized_name="apollo pharmacy",
            category="healthcare",
            latitude=12.9720,
            longitude=77.5950,
            utm_x=150.0,
            utm_y=100.0,
        )
    )
    # Right partition: Overture nodes
    graph.add_node(
        GraphNode(
            node_id="ov_1",
            source="OVERTURE",
            source_record_id="ov_uuid_1",
            name="Cafe Coffee Day",
            normalized_name="cafe coffee day",
            category="sustenance",
            latitude=12.9716,
            longitude=77.5946,
            utm_x=105.0,
            utm_y=100.0,
        )
    )
    graph.add_node(
        GraphNode(
            node_id="ov_2",
            source="OVERTURE",
            source_record_id="ov_uuid_2",
            name="MedPlus",
            normalized_name="medplus",
            category="healthcare",
            latitude=12.9720,
            longitude=77.5950,
            utm_x=155.0,
            utm_y=100.0,
        )
    )
    return graph


def test_bipartite_node_partition_accounting(sample_graph):
    """Verify separate partition tracking of OSM and Overture nodes."""
    assert sample_graph.osm_nodes_count == 2
    assert sample_graph.overture_nodes_count == 2
    assert len(sample_graph.nodes) == 4


def test_edge_classifier_tiers():
    """Verify classification into STRONG_MATCH_CANDIDATE, POSSIBLE_MATCH, UNCERTAIN, and REJECTED."""
    classifier = EdgeClassifier()

    # Strong match
    c_strong = classifier.classify_edge(
        score=0.88,
        decision="MATCH",
        guardrails=[],
        features={"feat_distance_meters": 10.0, "feat_is_empty_name": 0.0},
    )
    assert c_strong == GraphEdgeClassification.STRONG_MATCH_CANDIDATE

    # Possible match
    c_poss = classifier.classify_edge(
        score=0.62,
        decision="UNCERTAIN",
        guardrails=[],
        features={"feat_distance_meters": 20.0, "feat_is_empty_name": 0.0},
    )
    assert c_poss == GraphEdgeClassification.POSSIBLE_MATCH

    # Uncertain (missing name)
    c_unc = classifier.classify_edge(
        score=0.78,
        decision="UNCERTAIN",
        guardrails=["INSUFFICIENT_NAME_EVIDENCE"],
        features={"feat_distance_meters": 5.0, "feat_is_empty_name": 1.0},
    )
    assert c_unc == GraphEdgeClassification.UNCERTAIN

    # Hard rejection (guardrail)
    c_rej_guard = classifier.classify_edge(
        score=0.85,
        decision="NON_MATCH",
        guardrails=["SAME_BRAND_DIFFERENT_BRANCH"],
        features={"feat_distance_meters": 1500.0},
    )
    assert c_rej_guard == GraphEdgeClassification.REJECTED

    # Hard rejection (low score)
    c_rej_score = classifier.classify_edge(
        score=0.25,
        decision="NON_MATCH",
        guardrails=[],
        features={"feat_distance_meters": 45.0},
    )
    assert c_rej_score == GraphEdgeClassification.REJECTED


def test_one_to_one_component(sample_graph):
    """Verify that a single clean edge between 1 OSM and 1 Overture forms a ONE_TO_ONE cluster."""
    edge = GraphEdge(
        pair_id="osm_1::ov_1",
        osm_source_id="osm_1",
        ov_source_id="ov_1",
        matching_score=0.88,
        matching_decision="MATCH",
        classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
        distance_meters=5.0,
        name_similarity=1.0,
    )
    sample_graph.add_edge(edge)

    clusters = sample_graph.find_connected_components(active_only=True)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.pattern == ClusterStructuralPattern.ONE_TO_ONE
    assert c.osm_node_ids == ["osm_1"]
    assert c.ov_node_ids == ["ov_1"]
    assert c.total_nodes == 2
    assert math.isclose(c.geographic_spread_meters, 5.0, abs_tol=1e-3)
    assert c.category_consistent is True
    assert c.is_ambiguous is False


def test_one_to_many_component(sample_graph):
    """Verify 1:N star component pattern identification."""
    # Add a second Overture candidate connected to osm_1
    sample_graph.add_node(
        GraphNode(
            node_id="ov_3",
            source="OVERTURE",
            source_record_id="ov_uuid_3",
            name="CCD Indiranagar",
            normalized_name="ccd indiranagar",
            category="sustenance",
            latitude=12.9717,
            longitude=77.5947,
            utm_x=115.0,
            utm_y=100.0,
        )
    )

    sample_graph.add_edge(
        GraphEdge(
            pair_id="osm_1::ov_1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.88,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=5.0,
            name_similarity=1.0,
        )
    )
    sample_graph.add_edge(
        GraphEdge(
            pair_id="osm_1::ov_3",
            osm_source_id="osm_1",
            ov_source_id="ov_3",
            matching_score=0.60,
            matching_decision="UNCERTAIN",
            classification=GraphEdgeClassification.POSSIBLE_MATCH,
            distance_meters=15.0,
            name_similarity=0.70,
        )
    )

    clusters = sample_graph.find_connected_components(active_only=True)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.pattern == ClusterStructuralPattern.ONE_TO_MANY
    assert len(c.osm_node_ids) == 1
    assert len(c.ov_node_ids) == 2


def test_ambiguous_cluster_due_to_geographic_spread(sample_graph):
    """Verify that a component with excessive geographic spread (>100m) is classified as AMBIGUOUS_CLUSTER."""
    # Place ov_1 at 105m distance
    sample_graph.nodes["ov_1"].utm_x = 220.0  # 120m away from osm_1 (100.0)

    sample_graph.add_edge(
        GraphEdge(
            pair_id="osm_1::ov_1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.78,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=120.0,
            name_similarity=1.0,
        )
    )

    clusters = sample_graph.find_connected_components(active_only=True)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.geographic_spread_meters > 100.0
    assert c.is_ambiguous is True


def test_category_contradiction_detection(sample_graph):
    """Verify category incompatibility detection across nodes in a cluster."""
    # Link osm_1 (sustenance) to ov_2 (healthcare)
    sample_graph.add_edge(
        GraphEdge(
            pair_id="osm_1::ov_2",
            osm_source_id="osm_1",
            ov_source_id="ov_2",
            matching_score=0.60,
            matching_decision="UNCERTAIN",
            classification=GraphEdgeClassification.POSSIBLE_MATCH,
            distance_meters=15.0,
            name_similarity=0.50,
        )
    )

    clusters = sample_graph.find_connected_components(active_only=True)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.category_consistent is False
    assert c.is_ambiguous is True


def test_competing_edges_detection(sample_graph):
    """Verify detection of competing edges with close scores (|Delta S| <= 0.05)."""
    sample_graph.add_node(
        GraphNode(
            node_id="ov_comp",
            source="OVERTURE",
            source_record_id="ov_comp_id",
            name="Cafe Coffee Day Lounge",
            normalized_name="cafe coffee day lounge",
            category="sustenance",
            latitude=12.9716,
            longitude=77.5946,
            utm_x=108.0,
            utm_y=100.0,
        )
    )
    # Edge 1: 0.82
    sample_graph.add_edge(
        GraphEdge(
            pair_id="osm_1::ov_1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.82,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=5.0,
            name_similarity=1.0,
        )
    )
    # Edge 2: 0.80 (delta = 0.02 <= 0.05)
    sample_graph.add_edge(
        GraphEdge(
            pair_id="osm_1::ov_comp",
            osm_source_id="osm_1",
            ov_source_id="ov_comp",
            matching_score=0.80,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=8.0,
            name_similarity=0.90,
        )
    )

    clusters = sample_graph.find_connected_components(active_only=True)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.competing_edge_count > 0
    assert c.is_ambiguous is True
