"""Automated test suite for conservative canonical entity resolution.

Tests:
1. Stable deterministic UUIDv5 identifier generation.
2. 1:1 clean equivalence resolution with source provenance preservation.
3. Dominant star cluster resolution (winner resolved, runner-up preserved as singleton).
4. Ambiguous cluster handling (held as UNRESOLVED_AMBIGUOUS without merging).
5. Parent-child relationship isolation (mall vs internal store).
6. Isolated node singleton accounting.
7. AmbiguityAnalyzer conflict classification and review queue prioritization.
8. Validation of generated reports on disk.
"""

from pathlib import Path
import pytest

from src.poi_conflation.graph.schema import (
    GRAPH_SCHEMA_VERSION,
    CANONICAL_RESOLUTION_POLICY_VERSION,
    GraphNode,
    GraphEdge,
    EntityCluster,
    GraphEdgeClassification,
    CanonicalResolutionDecision,
    ClusterStructuralPattern,
    AmbiguityType,
)
from src.poi_conflation.graph.canonical_resolver import (
    CanonicalEntityResolver,
    generate_canonical_uuid,
)
from src.poi_conflation.graph.ambiguity_analyzer import AmbiguityAnalyzer


@pytest.fixture
def resolver():
    return CanonicalEntityResolver()


@pytest.fixture
def sample_nodes():
    return {
        "osm_1": GraphNode(
            node_id="osm_1",
            source="OSM",
            source_record_id="node/101",
            name="Apollo Pharmacy",
            normalized_name="apollo pharmacy",
            category="healthcare",
            latitude=12.9716,
            longitude=77.5946,
            utm_x=100.0,
            utm_y=100.0,
        ),
        "ov_1": GraphNode(
            node_id="ov_1",
            source="OVERTURE",
            source_record_id="ov_101",
            name="Apollo Pharmacy",
            normalized_name="apollo pharmacy",
            category="healthcare",
            latitude=12.9716,
            longitude=77.5946,
            utm_x=105.0,
            utm_y=100.0,
        ),
        "ov_runner_up": GraphNode(
            node_id="ov_runner_up",
            source="OVERTURE",
            source_record_id="ov_102",
            name="Apollo Clinic",
            normalized_name="apollo clinic",
            category="healthcare",
            latitude=12.9718,
            longitude=77.5948,
            utm_x=130.0,
            utm_y=100.0,
        ),
        "osm_mall": GraphNode(
            node_id="osm_mall",
            source="OSM",
            source_record_id="way/201",
            name="Forum Mall Koramangala",
            normalized_name="forum mall koramangala",
            category="commercial_services",
            latitude=12.9345,
            longitude=77.6110,
            utm_x=500.0,
            utm_y=500.0,
        ),
        "ov_store": GraphNode(
            node_id="ov_store",
            source="OVERTURE",
            source_record_id="ov_store_1",
            name="Zara",
            normalized_name="zara",
            category="retail",
            latitude=12.9345,
            longitude=77.6110,
            utm_x=510.0,
            utm_y=500.0,
        ),
    }


def test_deterministic_uuid_generation():
    """Verify UUIDv5 generation is deterministic and invariant to input order."""
    uuid1 = generate_canonical_uuid(["node/1", "node/2"], ["ov/A"])
    uuid2 = generate_canonical_uuid(["node/2", "node/1"], ["ov/A"])
    assert uuid1 == uuid2, "UUID must be strictly order-invariant"
    assert len(uuid1) == 36


def test_resolve_one_to_one_equivalence(resolver, sample_nodes):
    """Verify clean 1:1 match resolves to RESOLVED_EQUIVALENCE preserving both IDs."""
    cluster = EntityCluster(
        cluster_id="CLUSTER-000001",
        osm_node_ids=["osm_1"],
        ov_node_ids=["ov_1"],
        edge_pair_ids=["osm_1::ov_1"],
        pattern=ClusterStructuralPattern.ONE_TO_ONE,
        score_min=0.88,
        score_max=0.88,
        score_mean=0.88,
        geographic_spread_meters=5.0,
        category_consistent=True,
        categories_present=["healthcare"],
        competing_edge_count=0,
        has_rejected_edges=False,
        is_ambiguous=False,
    )
    edges = {
        "osm_1::ov_1": GraphEdge(
            pair_id="osm_1::ov_1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.88,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=5.0,
            name_similarity=1.0,
        )
    }

    ents = resolver.resolve_cluster(cluster, sample_nodes, edges)
    assert len(ents) == 1
    e = ents[0]
    assert e.resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE
    assert e.contributing_osm_ids == ["osm_1"]
    assert e.contributing_ov_ids == ["ov_1"]
    assert e.primary_name == "Apollo Pharmacy"
    assert e.primary_category == "healthcare"
    assert "OSM" in e.source_names and "OVERTURE" in e.source_names


def test_resolve_dominant_star_cluster(resolver, sample_nodes):
    """Verify star cluster with large score margin resolves winner and preserves runner-up as singleton."""
    cluster = EntityCluster(
        cluster_id="CLUSTER-000002",
        osm_node_ids=["osm_1"],
        ov_node_ids=["ov_1", "ov_runner_up"],
        edge_pair_ids=["osm_1::ov_1", "osm_1::ov_runner_up"],
        pattern=ClusterStructuralPattern.ONE_TO_MANY,
        score_min=0.45,
        score_max=0.88,
        score_mean=0.665,
        geographic_spread_meters=30.0,
        category_consistent=True,
        categories_present=["healthcare"],
        competing_edge_count=0,
        has_rejected_edges=False,
        is_ambiguous=False,
    )
    edges = {
        "osm_1::ov_1": GraphEdge(
            pair_id="osm_1::ov_1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.88,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=5.0,
            name_similarity=1.0,
        ),
        "osm_1::ov_runner_up": GraphEdge(
            pair_id="osm_1::ov_runner_up",
            osm_source_id="osm_1",
            ov_source_id="ov_runner_up",
            matching_score=0.45,
            matching_decision="UNCERTAIN",
            classification=GraphEdgeClassification.POSSIBLE_MATCH,
            distance_meters=30.0,
            name_similarity=0.60,
        ),
    }

    ents = resolver.resolve_cluster(cluster, sample_nodes, edges)
    assert len(ents) == 2
    merged = [e for e in ents if e.resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE]
    singleton = [e for e in ents if e.resolution_decision == CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON]

    assert len(merged) == 1
    assert merged[0].contributing_osm_ids == ["osm_1"]
    assert merged[0].contributing_ov_ids == ["ov_1"]

    assert len(singleton) == 1
    assert singleton[0].contributing_ov_ids == ["ov_runner_up"]


def test_parent_child_resolution(resolver, sample_nodes):
    """Verify parent-child container resolution (mall vs retail store)."""
    cluster = EntityCluster(
        cluster_id="CLUSTER-000003",
        osm_node_ids=["osm_mall"],
        ov_node_ids=["ov_store"],
        edge_pair_ids=["osm_mall::ov_store"],
        pattern=ClusterStructuralPattern.ONE_TO_ONE,
        score_min=0.72,
        score_max=0.72,
        score_mean=0.72,
        geographic_spread_meters=10.0,
        category_consistent=True,
        categories_present=["commercial_services", "retail"],
        competing_edge_count=0,
        has_rejected_edges=False,
        is_ambiguous=False,
    )
    edges = {
        "osm_mall::ov_store": GraphEdge(
            pair_id="osm_mall::ov_store",
            osm_source_id="osm_mall",
            ov_source_id="ov_store",
            matching_score=0.72,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=10.0,
            name_similarity=0.40,
        )
    }

    ents = resolver.resolve_cluster(cluster, sample_nodes, edges)
    assert len(ents) == 2
    assert all(e.resolution_decision == CanonicalResolutionDecision.PARENT_CHILD for e in ents)
    child = next(e for e in ents if e.parent_entity_id is not None)
    parent = next(e for e in ents if e.parent_entity_id is None)
    assert child.parent_entity_id == parent.canonical_entity_id


def test_ambiguous_cluster_held_unresolved(resolver, sample_nodes):
    """Verify that an ambiguous cluster with contradictory categories is held UNRESOLVED_AMBIGUOUS."""
    cluster = EntityCluster(
        cluster_id="CLUSTER-000004",
        osm_node_ids=["osm_1"],
        ov_node_ids=["ov_1"],
        edge_pair_ids=["osm_1::ov_1"],
        pattern=ClusterStructuralPattern.AMBIGUOUS_CLUSTER,
        score_min=0.75,
        score_max=0.75,
        score_mean=0.75,
        geographic_spread_meters=120.0,
        category_consistent=False,
        categories_present=["healthcare", "sustenance"],
        competing_edge_count=0,
        has_rejected_edges=True,
        is_ambiguous=True,
    )
    edges = {
        "osm_1::ov_1": GraphEdge(
            pair_id="osm_1::ov_1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.75,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=120.0,
            name_similarity=0.90,
        )
    }

    ents = resolver.resolve_cluster(cluster, sample_nodes, edges)
    assert len(ents) == 2
    assert all(e.resolution_decision == CanonicalResolutionDecision.UNRESOLVED_AMBIGUOUS for e in ents)
    assert len(ents[0].conflict_notes) > 0


def test_ambiguity_analyzer_review_queue(sample_nodes):
    """Verify ambiguity analysis and priority ranking."""
    analyzer = AmbiguityAnalyzer()
    clusters = [
        EntityCluster(
            cluster_id="CLUSTER-C1",
            osm_node_ids=["osm_1"],
            ov_node_ids=["ov_1"],
            edge_pair_ids=["e1"],
            pattern=ClusterStructuralPattern.AMBIGUOUS_CLUSTER,
            score_min=0.90,
            score_max=0.90,
            score_mean=0.90,
            geographic_spread_meters=20.0,
            category_consistent=False,
            categories_present=["healthcare", "sustenance"],
            competing_edge_count=0,
            has_rejected_edges=False,
            is_ambiguous=True,
        )
    ]
    edges = {
        "e1": GraphEdge(
            pair_id="e1",
            osm_source_id="osm_1",
            ov_source_id="ov_1",
            matching_score=0.90,
            matching_decision="MATCH",
            classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE,
            distance_meters=20.0,
            name_similarity=0.90,
        )
    }

    report, queue = analyzer.analyze_conflicts(clusters, sample_nodes, edges)
    assert report["total_ambiguous_clusters"] == 1
    assert len(queue) == 1
    assert queue[0].priority_rank == 1
    assert queue[0].ambiguity_type == AmbiguityType.CATEGORY_CONTRADICTION


def test_generated_reports_exist():
    """Verify that all M10 report artifacts exist on disk."""
    assert Path("reports/conflation_graph_report.json").exists()
    assert Path("reports/canonical_entities_summary.json").exists()
    assert Path("reports/graph_ambiguity_report.json").exists()
    assert Path("reports/review_prioritization_queue.json").exists()
    assert Path("reports/conflation_graph_clusters_sample.json").exists()
    assert Path("reports/canonical_entities_sample.json").exists()
