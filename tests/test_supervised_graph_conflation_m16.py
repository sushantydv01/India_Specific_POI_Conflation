"""Automated test suite for Milestone 16 — Supervised Graph Conflation & Entity Resolution.

Tests:
1. Normal valid 1:1 matches resolve to RESOLVED_EQUIVALENCE with deterministic attributes.
2. ATM vs. bank branch distinction (ATM_VS_BANK_FACILITY_DISTINCTION) prevents entity merge.
3. Same-brand different branches distinction (SAME_BRAND_DIFFERENT_BRANCH) prevents merge.
4. Parent-child commercial containers (PARENT_CHILD_CONTAINER) creates relationship without merge.
5. Generic-name collisions (GENERIC_NAME_COLLISION) are intercepted and prevented from merging.
6. Contradictory categories (CATEGORY_INCOMPATIBLE) are hard rejected.
7. Excessive spatial separation (>50m without exact name) is hard rejected.
8. Graph star cluster resolution with dominance margin check.
9. Ambiguous / complex clusters held as UNRESOLVED_AMBIGUOUS without transitive over-merging.
10. Complete source inventory accounting (zero lost, zero duplicate source IDs).
11. Collision-free deterministic UUIDv5 canonical identifiers.
12. Validation of exported Parquet and GeoJSON files on disk.
"""

import json
from pathlib import Path
import pytest
import duckdb
import pyarrow.parquet as pq

from src.poi_conflation.graph.schema import (
    GRAPH_SCHEMA_VERSION,
    CANONICAL_RESOLUTION_POLICY_VERSION,
    GraphNode,
    GraphEdge,
    EntityCluster,
    CanonicalEntity,
    CanonicalResolutionDecision,
    ClusterStructuralPattern,
    GraphEdgeClassification,
    EdgeDisposition,
    POIRelationshipType,
    SafeguardType,
    POIRelationship,
    UnresolvedPair,
)
from src.poi_conflation.graph.safeguards import ConflationSafeguardValidator
from src.poi_conflation.graph.supervised_resolver import SupervisedCanonicalResolver
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph
from src.poi_conflation.graph.canonical_resolver import generate_canonical_uuid


@pytest.fixture
def validator():
    return ConflationSafeguardValidator()


@pytest.fixture
def resolver():
    return SupervisedCanonicalResolver()


# 1. Normal valid match test
def test_valid_match_resolution(validator, resolver):
    """Test clean 1:1 match passes safeguards and resolves to equivalence."""
    res = validator.validate_candidate_edge(
        osm_name="Hotel Navayuga",
        ov_name="Hotel Navayuga",
        osm_category="sustenance",
        ov_category="sustenance",
        distance_meters=2.5,
        supervised_model_score=0.998,
        supervised_decision="MATCH",
    )
    assert res.disposition == EdgeDisposition.ACCEPTED_EQUIVALENCE
    assert len(res.safeguards_triggered) == 0

    node_osm = GraphNode("node/1", "OSM", "node/1", "Hotel Navayuga", "hotel navayuga", "sustenance", 12.97, 77.59, 100.0, 100.0)
    node_ov = GraphNode("ov/1", "OVERTURE", "ov/1", "Hotel Navayuga", "hotel navayuga", "sustenance", 12.97002, 77.59002, 102.5, 100.0)
    edge = GraphEdge("node/1::ov/1", "node/1", "ov/1", 0.998, "MATCH", GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 2.5, 1.0, supervised_model_score=0.998, supervised_decision="MATCH")

    cluster = EntityCluster("c1", ["node/1"], ["ov/1"], ["node/1::ov/1"], ClusterStructuralPattern.ONE_TO_ONE, 0.998, 0.998, 0.998, 2.5, True, ["sustenance"], 0, False, False)
    entities, unresolved = resolver._resolve_one_to_one(cluster, {"node/1": node_osm, "ov/1": node_ov}, {"node/1::ov/1": edge})

    assert len(entities) == 1
    assert entities[0].resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE
    assert entities[0].primary_name == "Hotel Navayuga"
    assert entities[0].contributing_osm_ids == ["node/1"]
    assert entities[0].contributing_ov_ids == ["ov/1"]
    assert len(unresolved) == 0


# 2. ATM vs Bank branch safeguard test
def test_atm_vs_bank_distinction(validator):
    """Test ATM vs Bank branch distinction prohibits equivalence and creates facility relationship."""
    # Bank branch vs ATM kiosk with shared brand
    res = validator.validate_candidate_edge(
        osm_name="State Bank of India",
        ov_name="State Bank of India ATM",
        osm_category="commercial_services",
        ov_category="commercial_services",
        distance_meters=12.0,
        supervised_model_score=0.997,
        supervised_decision="MATCH",
    )
    assert res.disposition == EdgeDisposition.PARENT_CHILD
    assert SafeguardType.ATM_VS_BANK_FACILITY_DISTINCTION in res.safeguards_triggered
    assert res.relationship_type == POIRelationshipType.FACILITY_ATM
    assert res.parent_source == "OSM"  # OSM is bank branch, Overture is ATM

    # Reverse orientation
    res_rev = validator.validate_candidate_edge(
        osm_name="HDFC Bank ATM",
        ov_name="HDFC Bank",
        osm_category="commercial_services",
        ov_category="commercial_services",
        distance_meters=18.5,
        supervised_model_score=0.996,
        supervised_decision="MATCH",
    )
    assert res_rev.disposition == EdgeDisposition.PARENT_CHILD
    assert SafeguardType.ATM_VS_BANK_FACILITY_DISTINCTION in res_rev.safeguards_triggered
    assert res_rev.parent_source == "OVERTURE"


# 3. Same-brand different branches distinction test
def test_same_brand_different_branches(validator):
    """Test same-brand different branches with conflicting localities are rejected."""
    res = validator.validate_candidate_edge(
        osm_name="Dominos Pizza Koramangala",
        ov_name="Dominos Pizza Indiranagar",
        osm_category="sustenance",
        ov_category="sustenance",
        distance_meters=35.0,
        supervised_model_score=0.94,
        supervised_decision="MATCH",
    )
    assert res.disposition == EdgeDisposition.REJECTED
    assert SafeguardType.SAME_BRAND_DIFFERENT_BRANCH in res.safeguards_triggered

    # Conflicting block numbers
    res_block = validator.validate_candidate_edge(
        osm_name="Nandhini Restaurant 4th Block",
        ov_name="Nandhini Restaurant 9th Block",
        osm_category="sustenance",
        ov_category="sustenance",
        distance_meters=28.0,
        supervised_model_score=0.91,
        supervised_decision="MATCH",
    )
    assert res_block.disposition == EdgeDisposition.REJECTED
    assert SafeguardType.SAME_BRAND_DIFFERENT_BRANCH in res_block.safeguards_triggered


# 4. Parent-child commercial containers test
def test_parent_child_container(validator):
    """Test commercial container parent-child relations are identified without merging."""
    # Shopping Mall vs internal store
    res_mall = validator.validate_candidate_edge(
        osm_name="Phoenix Marketcity",
        ov_name="Zara",
        osm_category="retail",
        ov_category="retail",
        distance_meters=22.0,
        supervised_model_score=0.88,
        supervised_decision="MATCH",
    )
    assert res_mall.disposition == EdgeDisposition.PARENT_CHILD
    assert SafeguardType.PARENT_CHILD_CONTAINER in res_mall.safeguards_triggered
    assert res_mall.relationship_type == POIRelationshipType.PARENT_CHILD

    # IT Park vs Cafeteria
    res_techpark = validator.validate_candidate_edge(
        osm_name="Manyata Tech Park",
        ov_name="Subway Food Court",
        osm_category="commercial_services",
        ov_category="sustenance",
        distance_meters=30.0,
        supervised_model_score=0.85,
        supervised_decision="MATCH",
    )
    assert res_techpark.disposition == EdgeDisposition.PARENT_CHILD
    assert SafeguardType.PARENT_CHILD_CONTAINER in res_techpark.safeguards_triggered
    assert res_techpark.relationship_type == POIRelationshipType.CAMPUS_FACILITY


# 5. Generic-name collision test
def test_generic_name_collision(validator):
    """Test generic establishment descriptors sharing prefix but disjoint brands are not merged."""
    res = validator.validate_candidate_edge(
        osm_name="Hotel Sagar",
        ov_name="Hotel Green Orchid",
        osm_category="sustenance",
        ov_category="sustenance",
        distance_meters=34.0,
        supervised_model_score=0.90,
        supervised_decision="MATCH",
    )
    assert res.disposition == EdgeDisposition.REVIEW
    assert SafeguardType.GENERIC_NAME_COLLISION in res.safeguards_triggered

    # Pure generic name without unique brand
    res_pure = validator.validate_candidate_edge(
        osm_name="Medical Store",
        ov_name="Medical Store",
        osm_category="healthcare",
        ov_category="healthcare",
        distance_meters=20.0,
        supervised_model_score=0.80,
        supervised_decision="MATCH",
    )
    assert res_pure.disposition == EdgeDisposition.REVIEW
    assert SafeguardType.GENERIC_NAME_COLLISION in res_pure.safeguards_triggered


# 6. Category incompatibility test
def test_category_incompatible_rejection(validator):
    """Test strictly incompatible categories are rejected."""
    res = validator.validate_candidate_edge(
        osm_name="Apollo Clinic",
        ov_name="Apollo Restaurant",
        osm_category="healthcare",
        ov_category="sustenance",
        distance_meters=15.0,
        supervised_model_score=0.89,
        supervised_decision="MATCH",
    )
    assert res.disposition == EdgeDisposition.REJECTED
    assert SafeguardType.CATEGORY_INCOMPATIBLE in res.safeguards_triggered


# 7. Excessive spatial separation test
def test_excessive_spatial_separation(validator):
    """Test candidate pairs with excessive distance are rejected."""
    # Distance > 50m without exact name
    res_50m = validator.validate_candidate_edge(
        osm_name="Kalmane Koffees",
        ov_name="Kalmane Coffee Express",
        osm_category="sustenance",
        ov_category="sustenance",
        distance_meters=65.0,
        supervised_model_score=0.82,
        supervised_decision="MATCH",
    )
    assert res_50m.disposition == EdgeDisposition.REJECTED
    assert SafeguardType.EXCESSIVE_SPATIAL_SEPARATION in res_50m.safeguards_triggered

    # Distance > 80m under all conditions
    res_80m = validator.validate_candidate_edge(
        osm_name="Mi Home",
        ov_name="Mi Home",
        osm_category="retail",
        ov_category="retail",
        distance_meters=88.2,
        supervised_model_score=0.81,
        supervised_decision="MATCH",
    )
    assert res_80m.disposition == EdgeDisposition.REJECTED
    assert SafeguardType.EXCESSIVE_SPATIAL_SEPARATION in res_80m.safeguards_triggered


# 8. Dominant star cluster resolution test
def test_dominant_star_cluster_resolution(resolver):
    """Test star cluster where top edge is dominant: winner resolved, runner-up preserved as singleton."""
    node_osm = GraphNode("node/1", "OSM", "node/1", "KFC", "kfc", "sustenance", 12.97, 77.59, 100.0, 100.0)
    node_ov1 = GraphNode("ov/1", "OVERTURE", "ov/1", "KFC", "kfc", "sustenance", 12.97002, 77.59002, 102.0, 100.0)
    node_ov2 = GraphNode("ov/2", "OVERTURE", "ov/2", "KFC Indiranagar", "kfc indiranagar", "sustenance", 12.9703, 77.5903, 130.0, 100.0)

    nodes = {"node/1": node_osm, "ov/1": node_ov1, "ov/2": node_ov2}
    edges = {
        "node/1::ov/1": GraphEdge("node/1::ov/1", "node/1", "ov/1", 0.995, "MATCH", GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 2.0, 1.0, supervised_model_score=0.995, supervised_decision="MATCH"),
        "node/1::ov/2": GraphEdge("node/1::ov/2", "node/1", "ov/2", 0.720, "MATCH", GraphEdgeClassification.POSSIBLE_MATCH, 30.0, 0.65, supervised_model_score=0.720, supervised_decision="MATCH"),
    }

    cluster = EntityCluster("c_star", ["node/1"], ["ov/1", "ov/2"], ["node/1::ov/1", "node/1::ov/2"], ClusterStructuralPattern.ONE_TO_MANY, 0.720, 0.995, 0.8575, 30.0, True, ["sustenance"], 0, False, False)
    entities, unresolved = resolver._resolve_star_cluster(cluster, nodes, edges)

    assert len(entities) == 2
    # Winner: 1:1 equivalence between node/1 and ov/1
    winner = [e for e in entities if e.resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE][0]
    assert winner.contributing_osm_ids == ["node/1"]
    assert winner.contributing_ov_ids == ["ov/1"]

    # Runner-up: ov/2 preserved as single-source singleton
    singleton = [e for e in entities if e.resolution_decision == CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON][0]
    assert singleton.contributing_osm_ids == []
    assert singleton.contributing_ov_ids == ["ov/2"]

    # Subordinated edge recorded in unresolved pairs
    assert len(unresolved) == 1
    assert unresolved[0].candidate_pair_id == "node/1::ov/2"
    assert "STAR_RUNNER_UP_SUBORDINATED" in unresolved[0].safeguards_triggered


# 9. Ambiguous star cluster resolution test
def test_ambiguous_star_cluster_resolution(resolver):
    """Test star cluster with close competing scores is held as UNRESOLVED_AMBIGUOUS without merging."""
    node_osm = GraphNode("node/1", "OSM", "node/1", "Nandhini Hotel", "nandhini hotel", "sustenance", 12.97, 77.59, 100.0, 100.0)
    node_ov1 = GraphNode("ov/1", "OVERTURE", "ov/1", "Nandhini", "nandhini", "sustenance", 12.9701, 77.5901, 110.0, 100.0)
    node_ov2 = GraphNode("ov/2", "OVERTURE", "ov/2", "Hotel Nandhini", "hotel nandhini", "sustenance", 12.97012, 77.59012, 112.0, 100.0)

    nodes = {"node/1": node_osm, "ov/1": node_ov1, "ov/2": node_ov2}
    edges = {
        "node/1::ov/1": GraphEdge("node/1::ov/1", "node/1", "ov/1", 0.950, "MATCH", GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 10.0, 0.85, supervised_model_score=0.950, supervised_decision="MATCH"),
        "node/1::ov/2": GraphEdge("node/1::ov/2", "node/1", "ov/2", 0.930, "MATCH", GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 12.0, 0.95, supervised_model_score=0.930, supervised_decision="MATCH"),
    }

    cluster = EntityCluster("c_star_ambig", ["node/1"], ["ov/1", "ov/2"], ["node/1::ov/1", "node/1::ov/2"], ClusterStructuralPattern.ONE_TO_MANY, 0.930, 0.950, 0.940, 12.0, True, ["sustenance"], 1, False, True)
    entities, unresolved = resolver._resolve_star_cluster(cluster, nodes, edges)

    # All 3 nodes must be preserved as UNRESOLVED_AMBIGUOUS without collapsing
    assert len(entities) == 3
    for ent in entities:
        assert ent.resolution_decision == CanonicalResolutionDecision.UNRESOLVED_AMBIGUOUS

    # Both competing edges routed to unresolved pairs
    assert len(unresolved) == 2
    for u in unresolved:
        assert "CLOSE_COMPETING_STAR_EDGES" in u.safeguards_triggered


# 10. Complete source inventory accounting test
def test_source_inventory_accounting(resolver):
    """Test that resolve_graph accounts for 100% of source nodes with zero duplication."""
    nodes = {
        "osm_1": GraphNode("osm_1", "OSM", "osm_1", "Place A", "place a", "retail", 12.97, 77.59, 100.0, 100.0),
        "osm_2": GraphNode("osm_2", "OSM", "osm_2", "Place B", "place b", "sustenance", 12.98, 77.60, 200.0, 200.0),
        "ov_1": GraphNode("ov_1", "OVERTURE", "ov_1", "Place A", "place a", "retail", 12.97001, 77.59001, 101.0, 100.0),
        "ov_2": GraphNode("ov_2", "OVERTURE", "ov_2", "Place C", "place c", "healthcare", 12.99, 77.61, 300.0, 300.0),
    }

    edges = {
        "osm_1::ov_1": GraphEdge("osm_1::ov_1", "osm_1", "ov_1", 0.99, "MATCH", GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 1.0, 1.0, supervised_model_score=0.99, supervised_decision="MATCH"),
    }

    cluster = EntityCluster("c1", ["osm_1"], ["ov_1"], ["osm_1::ov_1"], ClusterStructuralPattern.ONE_TO_ONE, 0.99, 0.99, 0.99, 1.0, True, ["retail"], 0, False, False)
    entities, unresolved = resolver.resolve_graph(nodes, edges, [cluster], [])

    # Expected: 1 equivalence (osm_1 + ov_1) + 2 singletons (osm_2, ov_2) = 3 canonical entities
    assert len(entities) == 3

    accounted_osm = set()
    accounted_ov = set()
    for e in entities:
        accounted_osm.update(e.contributing_osm_ids)
        accounted_ov.update(e.contributing_ov_ids)

    assert accounted_osm == {"osm_1", "osm_2"}
    assert accounted_ov == {"ov_1", "ov_2"}


# 11. Deterministic UUIDv5 canonical identifiers test
def test_deterministic_canonical_uuid():
    """Test UUIDv5 generation is deterministic and order-invariant."""
    id1 = generate_canonical_uuid(["node/101"], ["ov_202"])
    id2 = generate_canonical_uuid(["node/101"], ["ov_202"])
    assert id1 == id2
    assert len(id1) == 36

    # Order invariance in source IDs
    id_multi_1 = generate_canonical_uuid(["node/101", "node/102"], ["ov_202", "ov_203"])
    id_multi_2 = generate_canonical_uuid(["node/102", "node/101"], ["ov_203", "ov_202"])
    assert id_multi_1 == id_multi_2


# 12. Export datasets integrity on disk
def test_canonical_export_datasets_on_disk():
    """Verify all 5 generated canonical export files exist on disk and meet schema requirements."""
    canonical_dir = Path("data/processed/canonical")
    pois_parquet = canonical_dir / "canonical_pois.parquet"
    pois_geojson = canonical_dir / "canonical_pois.geojson"
    edges_parquet = canonical_dir / "conflation_edges.parquet"
    unresolved_parquet = canonical_dir / "unresolved_pairs.parquet"
    relationships_parquet = canonical_dir / "poi_relationships.parquet"
    summary_report = Path("reports/m16_conflation_summary.json")

    assert pois_parquet.exists()
    assert pois_geojson.exists()
    assert edges_parquet.exists()
    assert unresolved_parquet.exists()
    assert relationships_parquet.exists()
    assert summary_report.exists()

    # Verify Parquet record counts
    con = duckdb.connect()
    can_count = con.execute(f"SELECT count(*) FROM '{pois_parquet}'").fetchone()[0]
    edge_count = con.execute(f"SELECT count(*) FROM '{edges_parquet}'").fetchone()[0]
    unres_count = con.execute(f"SELECT count(*) FROM '{unresolved_parquet}'").fetchone()[0]
    rel_count = con.execute(f"SELECT count(*) FROM '{relationships_parquet}'").fetchone()[0]

    assert can_count == 238083
    assert edge_count == 605428
    assert unres_count == 2842
    assert rel_count == 985

    # Verify GeoJSON valid JSON and feature count
    with open(pois_geojson, "r", encoding="utf-8") as f:
        geo_data = json.load(f)
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) == 238083

    # Sample coordinate check
    sample_coord = geo_data["features"][0]["geometry"]["coordinates"]
    assert 77.4 <= sample_coord[0] <= 77.9  # Longitude
    assert 12.8 <= sample_coord[1] <= 13.2  # Latitude

    # Verify summary JSON
    with open(summary_report, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["source_inventory"]["accounted_source_count"] == 246856
    assert summary["source_inventory"]["unaccounted_source_count"] == 0
    assert summary["source_inventory"]["accounting_completeness_pct"] == 100.0
    assert summary["canonical_entity_summary"]["duplicate_canonical_id_count"] == 0
    assert summary["cluster_topology"]["invalid_cluster_count"] == 0
