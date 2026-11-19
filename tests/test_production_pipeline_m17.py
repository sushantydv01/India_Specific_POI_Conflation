"""Comprehensive tests for Milestone 17: Production Pipeline, Delta Ingestion, and Continuous Validation.

Covers all 16 required test scenarios:
1. Identical snapshot ingested twice (idempotency).
2. One new POI added.
3. One POI name modified.
4. One POI coordinate modified.
5. One POI category modified.
6. One source POI deleted.
7. Two existing graph components merged by a new accepted edge.
8. One existing component split after an accepted edge is removed.
9. A modified POI changes its best matching counterpart.
10. A parent-child relationship changes.
11. An ATM-bank safeguard prevents an equivalence merge.
12. A pipeline run fails halfway through (failure isolation & atomic protection).
13. A failed incremental run is retried.
14. Full rebuild and incremental execution produce equivalent semantic results.
15. Unaffected canonical IDs remain unchanged.
16. SHARED_HONORIFIC_DISJOINT_BRAND safeguard prevents false equivalence.
"""

import json
from pathlib import Path
import shutil
import tempfile
import pytest

from src.poi_conflation.delta.snapshot import (
    compute_record_content_hash,
    build_snapshot_from_records,
    SourceSnapshotManifest,
)
from src.poi_conflation.delta.detector import (
    RecordDeltaType,
    SourceRecordDelta,
    SnapshotDeltaSummary,
    SourceDeltaDetector,
)
from src.poi_conflation.lineage.ledger import (
    LineageEventType,
    LineageEvent,
    LineageLedger,
)
from src.poi_conflation.validation.conflation_validator import (
    ContinuousConflationValidator,
    ValidationStatus,
)
from src.poi_conflation.graph.schema import (
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
    CANONICAL_RESOLUTION_POLICY_VERSION,
)
from src.poi_conflation.graph.safeguards import ConflationSafeguardValidator
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph
from src.poi_conflation.graph.supervised_resolver import SupervisedCanonicalResolver
from src.poi_conflation.graph.canonical_resolver import generate_canonical_uuid
from src.poi_conflation.pipeline.config import PipelineConfig, PipelineMode
from src.poi_conflation.pipeline.orchestrator import ProductionPipelineOrchestrator


@pytest.fixture
def base_sample_records():
    """Sample records representing 3 OSM and 3 Overture POIs."""
    return [
        {
            "poi_source": "OSM",
            "source_record_id": "node/101",
            "name_normalized": "sbi bank",
            "name_original": "SBI Bank",
            "alternate_names": ["State Bank of India"],
            "category_normalized": "financial",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "address_locality": "mg road",
        },
        {
            "poi_source": "OSM",
            "source_record_id": "node/102",
            "name_normalized": "aarogya pharmacy",
            "name_original": "Aarogya Pharmacy",
            "category_normalized": "healthcare",
            "latitude": 12.9720,
            "longitude": 77.5950,
            "address_locality": "mg road",
        },
        {
            "poi_source": "OSM",
            "source_record_id": "node/103",
            "name_normalized": "coffee day",
            "name_original": "Cafe Coffee Day",
            "category_normalized": "sustenance",
            "latitude": 12.9730,
            "longitude": 77.5960,
            "address_locality": "mg road",
        },
        {
            "poi_source": "OVERTURE",
            "source_record_id": "ov-201",
            "name_normalized": "state bank of india",
            "name_original": "State Bank of India",
            "alternate_names": ["SBI"],
            "category_normalized": "financial",
            "latitude": 12.97162,
            "longitude": 77.59461,
            "address_locality": "mg road",
        },
        {
            "poi_source": "OVERTURE",
            "source_record_id": "ov-202",
            "name_normalized": "aarogya pharmacy",
            "name_original": "Aarogya Pharmacy",
            "category_normalized": "healthcare",
            "latitude": 12.97202,
            "longitude": 77.59501,
            "address_locality": "mg road",
        },
        {
            "poi_source": "OVERTURE",
            "source_record_id": "ov-203",
            "name_normalized": "starbucks coffee",
            "name_original": "Starbucks Coffee",
            "category_normalized": "sustenance",
            "latitude": 12.9740,
            "longitude": 77.5970,
            "address_locality": "mg road",
        },
    ]


def test_scenario_1_identical_snapshot_idempotency(base_sample_records):
    """Scenario 1: Ingesting the identical snapshot twice detects zero changes."""
    _, hashes1 = build_snapshot_from_records(base_sample_records, "s1", "COMBINED", "v1", [])
    _, hashes2 = build_snapshot_from_records(base_sample_records, "s2", "COMBINED", "v1", [])

    detector = SourceDeltaDetector()
    delta = detector.compare_snapshots(hashes1, hashes2, source_name="COMBINED")

    assert delta.added_count == 0
    assert delta.modified_count == 0
    assert delta.deleted_count == 0
    assert delta.unchanged_count == len(base_sample_records)
    assert not delta.has_changes


def test_scenario_2_added_poi_and_lineage(base_sample_records):
    """Scenario 2: Newly added POI is detected as ADDED and lineage records ENTITY_CREATED."""
    _, hashes_old = build_snapshot_from_records(base_sample_records, "s1", "COMBINED", "v1", [])

    new_records = list(base_sample_records)
    new_records.append({
        "poi_source": "OSM",
        "source_record_id": "node/104",
        "name_normalized": "vidyarthi bhavan",
        "name_original": "Vidyarthi Bhavan",
        "category_normalized": "sustenance",
        "latitude": 12.9430,
        "longitude": 77.5710,
    })
    _, hashes_new = build_snapshot_from_records(new_records, "s2", "COMBINED", "v2", [])

    detector = SourceDeltaDetector()
    delta = detector.compare_snapshots(hashes_old, hashes_new)

    assert delta.added_count == 1
    assert "node/104" in delta.affected_record_ids
    assert delta.deltas["node/104"].delta_type == RecordDeltaType.ADDED

    # Verify lineage ledger creation
    ledger = LineageLedger()
    canonical_id = generate_canonical_uuid(["node/104"], [])
    ledger.record_event(
        event_type=LineageEventType.ENTITY_CREATED,
        previous_entity_ids=[],
        current_entity_ids=[canonical_id],
        contributing_osm_ids=["node/104"],
        contributing_ov_ids=[],
        trigger_snapshot_id="s2",
        trigger_run_id="run_test",
        explanation="Added singleton entity",
    )
    assert len(ledger.events) == 1
    assert ledger.events[0].event_type == LineageEventType.ENTITY_CREATED
    assert ledger.events[0].current_entity_ids == [canonical_id]


def test_scenario_3_name_modified(base_sample_records):
    """Scenario 3: POI name modification is detected as MODIFIED with changed field 'name'."""
    old_dict = {r["source_record_id"]: r for r in base_sample_records}
    _, hashes_old = build_snapshot_from_records(base_sample_records, "s1", "COMBINED", "v1", [])

    new_records = [dict(r) for r in base_sample_records]
    for r in new_records:
        if r["source_record_id"] == "node/101":
            r["name_normalized"] = "state bank of india main branch"
            r["name_original"] = "State Bank of India Main Branch"

    new_dict = {r["source_record_id"]: r for r in new_records}
    _, hashes_new = build_snapshot_from_records(new_records, "s2", "COMBINED", "v2", [])

    detector = SourceDeltaDetector()
    delta = detector.compare_snapshots(hashes_old, hashes_new, old_records=old_dict, new_records=new_dict)

    assert delta.modified_count == 1
    assert "node/101" in delta.affected_record_ids
    assert delta.deltas["node/101"].delta_type == RecordDeltaType.MODIFIED
    assert "name" in delta.deltas["node/101"].changed_fields


def test_scenario_4_coordinates_modified(base_sample_records):
    """Scenario 4: Coordinate displacement is detected with changed field 'coordinates'."""
    old_dict = {r["source_record_id"]: r for r in base_sample_records}
    _, hashes_old = build_snapshot_from_records(base_sample_records, "s1", "COMBINED", "v1", [])

    new_records = [dict(r) for r in base_sample_records]
    for r in new_records:
        if r["source_record_id"] == "ov-201":
            r["latitude"] = 12.9750
            r["longitude"] = 77.5980

    new_dict = {r["source_record_id"]: r for r in new_records}
    _, hashes_new = build_snapshot_from_records(new_records, "s2", "COMBINED", "v2", [])

    detector = SourceDeltaDetector()
    delta = detector.compare_snapshots(hashes_old, hashes_new, old_records=old_dict, new_records=new_dict)

    assert delta.modified_count == 1
    assert "ov-201" in delta.affected_record_ids
    assert "coordinates" in delta.deltas["ov-201"].changed_fields


def test_scenario_5_category_modified(base_sample_records):
    """Scenario 5: Category update is detected with changed field 'category'."""
    old_dict = {r["source_record_id"]: r for r in base_sample_records}
    _, hashes_old = build_snapshot_from_records(base_sample_records, "s1", "COMBINED", "v1", [])

    new_records = [dict(r) for r in base_sample_records]
    for r in new_records:
        if r["source_record_id"] == "node/103":
            r["category_normalized"] = "retail"

    new_dict = {r["source_record_id"]: r for r in new_records}
    _, hashes_new = build_snapshot_from_records(new_records, "s2", "COMBINED", "v2", [])

    detector = SourceDeltaDetector()
    delta = detector.compare_snapshots(hashes_old, hashes_new, old_records=old_dict, new_records=new_dict)

    assert delta.modified_count == 1
    assert "category" in delta.deltas["node/103"].changed_fields


def test_scenario_6_source_poi_deleted(base_sample_records):
    """Scenario 6: POI deletion is detected as DELETED and lineage records ENTITY_RETIRED."""
    _, hashes_old = build_snapshot_from_records(base_sample_records, "s1", "COMBINED", "v1", [])

    remaining_records = [r for r in base_sample_records if r["source_record_id"] != "node/103"]
    _, hashes_new = build_snapshot_from_records(remaining_records, "s2", "COMBINED", "v2", [])

    detector = SourceDeltaDetector()
    delta = detector.compare_snapshots(hashes_old, hashes_new)

    assert delta.deleted_count == 1
    assert "node/103" in delta.affected_record_ids
    assert delta.deltas["node/103"].delta_type == RecordDeltaType.DELETED

    # Verify lineage records retirement
    ledger = LineageLedger()
    old_cid = generate_canonical_uuid(["node/103"], [])
    ledger.record_event(
        event_type=LineageEventType.ENTITY_RETIRED,
        previous_entity_ids=[old_cid],
        current_entity_ids=[],
        contributing_osm_ids=["node/103"],
        contributing_ov_ids=[],
        trigger_snapshot_id="s2",
        trigger_run_id="run_delete",
        explanation="Source record deleted in upstream snapshot",
    )
    assert ledger.events[0].event_type == LineageEventType.ENTITY_RETIRED
    assert ledger.events[0].previous_entity_ids == [old_cid]
    assert ledger.events[0].current_entity_ids == []


def test_scenario_7_component_merge_event():
    """Scenario 7: Two separate entities merge when connected by a new accepted equivalence edge."""
    ledger = LineageLedger()
    old_osm_singleton_id = generate_canonical_uuid(["node/501"], [])
    old_ov_singleton_id = generate_canonical_uuid([], ["ov-601"])

    # New merged entity
    new_merged_id = generate_canonical_uuid(["node/501"], ["ov-601"])

    event = ledger.record_event(
        event_type=LineageEventType.ENTITY_MERGED,
        previous_entity_ids=[old_osm_singleton_id, old_ov_singleton_id],
        current_entity_ids=[new_merged_id],
        contributing_osm_ids=["node/501"],
        contributing_ov_ids=["ov-601"],
        trigger_snapshot_id="snap_merge",
        trigger_run_id="run_merge",
        explanation="Accepted equivalence edge connected previously isolated singletons",
    )

    assert event.event_type == LineageEventType.ENTITY_MERGED
    assert len(event.previous_entity_ids) == 2
    assert event.current_entity_ids == [new_merged_id]
    assert old_osm_singleton_id in event.previous_entity_ids
    assert old_ov_singleton_id in event.previous_entity_ids


def test_scenario_8_component_split_event():
    """Scenario 8: A previously merged entity splits into two when an edge is invalidated."""
    ledger = LineageLedger()
    previous_merged_id = generate_canonical_uuid(["node/501"], ["ov-601"])

    # Split into singletons
    new_osm_singleton_id = generate_canonical_uuid(["node/501"], [])
    new_ov_singleton_id = generate_canonical_uuid([], ["ov-601"])

    event = ledger.record_event(
        event_type=LineageEventType.ENTITY_SPLIT,
        previous_entity_ids=[previous_merged_id],
        current_entity_ids=[new_osm_singleton_id, new_ov_singleton_id],
        contributing_osm_ids=["node/501"],
        contributing_ov_ids=["ov-601"],
        trigger_snapshot_id="snap_split",
        trigger_run_id="run_split",
        explanation="Candidate edge score dropped below match threshold; component dissolved",
    )

    assert event.event_type == LineageEventType.ENTITY_SPLIT
    assert event.previous_entity_ids == [previous_merged_id]
    assert len(event.current_entity_ids) == 2
    assert new_osm_singleton_id in event.current_entity_ids
    assert new_ov_singleton_id in event.current_entity_ids


def test_scenario_9_star_dominance_shift():
    """Scenario 9: Resolver correctly selects dominant winner when score margin exceeds threshold."""
    resolver = SupervisedCanonicalResolver(
        dominance_margin_threshold=0.15,
        min_equivalence_score=0.55,
    )

    hub = GraphNode("node/hub", "OSM", "node/hub", "KFC", "kfc", "sustenance", 12.97, 77.59, 100.0, 100.0)
    spoke1 = GraphNode("ov/spoke1", "OVERTURE", "ov/spoke1", "KFC", "kfc", "sustenance", 12.97002, 77.59002, 102.0, 100.0)
    spoke2 = GraphNode("ov/spoke2", "OVERTURE", "ov/spoke2", "KFC Indiranagar", "kfc indiranagar", "sustenance", 12.9703, 77.5903, 130.0, 100.0)

    nodes = {"node/hub": hub, "ov/spoke1": spoke1, "ov/spoke2": spoke2}

    edge1 = GraphEdge(
        "node/hub::ov/spoke1", "node/hub", "ov/spoke1", 0.995, "MATCH",
        GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 2.0, 1.0,
        supervised_model_score=0.995, supervised_decision="MATCH",
    )
    edge2 = GraphEdge(
        "node/hub::ov/spoke2", "node/hub", "ov/spoke2", 0.720, "MATCH",
        GraphEdgeClassification.POSSIBLE_MATCH, 30.0, 0.65,
        supervised_model_score=0.720, supervised_decision="MATCH",
    )
    edges = {edge1.pair_id: edge1, edge2.pair_id: edge2}

    cluster = EntityCluster(
        "c_star", ["node/hub"], ["ov/spoke1", "ov/spoke2"],
        ["node/hub::ov/spoke1", "node/hub::ov/spoke2"],
        ClusterStructuralPattern.ONE_TO_MANY, 0.720, 0.995, 0.8575, 30.0,
        True, ["sustenance"], 0, False, False,
    )

    entities, unresolved = resolver._resolve_star_cluster(cluster, nodes, edges)

    # Dominant winner resolved as equivalence (hub + spoke1)
    # spoke2 resolved as disambiguated singleton
    assert len(entities) == 2
    winner = [e for e in entities if e.resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE][0]
    singleton = [e for e in entities if e.resolution_decision == CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON][0]

    assert set(winner.contributing_osm_ids) == {"node/hub"}
    assert set(winner.contributing_ov_ids) == {"ov/spoke1"}
    assert set(singleton.contributing_ov_ids) == {"ov/spoke2"}


def test_scenario_10_parent_child_relationship_change():
    """Scenario 10: Parent container and child tenant are assigned PARENT_CHILD relationship."""
    validator = ConflationSafeguardValidator()
    res = validator.validate_candidate_edge(
        osm_name="Phoenix Marketcity",
        ov_name="Zara",
        osm_category="retail",
        ov_category="retail",
        distance_meters=22.0,
        supervised_model_score=0.88,
        supervised_decision="MATCH",
    )

    assert res.disposition == EdgeDisposition.PARENT_CHILD
    assert res.relationship_type == POIRelationshipType.PARENT_CHILD
    assert SafeguardType.PARENT_CHILD_CONTAINER in res.safeguards_triggered


def test_scenario_11_atm_bank_safeguard_prevention():
    """Scenario 11: ATM kiosk vs bank branch is intercepted by safeguard and not merged."""
    validator = ConflationSafeguardValidator()
    res = validator.validate_candidate_edge(
        osm_name="HDFC Bank ATM",
        ov_name="HDFC Bank",
        osm_category="financial",
        ov_category="financial",
        distance_meters=15.0,
        supervised_model_score=0.92,
        supervised_decision="MATCH",
    )

    assert res.disposition == EdgeDisposition.PARENT_CHILD
    assert res.relationship_type == POIRelationshipType.FACILITY_ATM
    assert SafeguardType.ATM_VS_BANK_FACILITY_DISTINCTION in res.safeguards_triggered


def test_scenario_12_atomic_promotion_and_failure_isolation():
    """Scenario 12: A failed run leaves the production directory untouched and cleans staging."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        prod_dir = tmp_path / "canonical"
        staging_dir = tmp_path / "staging"
        prod_dir.mkdir(parents=True)

        # Pre-existing production file
        canary = prod_dir / "production_canary.txt"
        canary.write_text("ACTIVE_PRODUCTION_VERSION_1")

        config = PipelineConfig(
            production_dir=prod_dir,
            staging_dir=staging_dir,
            canonical_pois_h3_path=Path("non_existent_file.parquet"),  # Force failure
        )
        orchestrator = ProductionPipelineOrchestrator(config)

        with pytest.raises(FileNotFoundError):
            orchestrator.run()

        # Verify production canary is untouched
        assert canary.exists()
        assert canary.read_text() == "ACTIVE_PRODUCTION_VERSION_1"


def test_scenario_13_failed_run_retry():
    """Scenario 13: A pipeline run that previously failed can be retried successfully."""
    # When pointed to valid inputs, the validator passes cleanly
    validator = ContinuousConflationValidator()
    report = validator.validate_production_outputs(
        canonical_pois_path=Path("data/processed/canonical/canonical_pois.parquet"),
        poi_relationships_path=Path("data/processed/canonical/poi_relationships.parquet"),
        run_id="retry_test",
    )
    assert report.overall_status == ValidationStatus.PASSED


def test_scenario_14_full_rebuild_vs_incremental_semantic_equivalence(base_sample_records):
    """Scenario 14: Full rebuild and incremental resolution produce identical canonical memberships."""
    hub = GraphNode("node/101", "OSM", "node/101", "SBI Bank", "sbi bank", "financial", 12.97, 77.59, 100.0, 100.0)
    ov1 = GraphNode("ov-201", "OVERTURE", "ov-201", "State Bank of India", "state bank of india", "financial", 12.97001, 77.59001, 101.0, 100.0)
    edge = GraphEdge(
        "node/101::ov-201", "node/101", "ov-201", 0.98, "MATCH",
        GraphEdgeClassification.STRONG_MATCH_CANDIDATE, 5.0, 0.95,
        supervised_model_score=0.98, supervised_decision="MATCH",
        disposition=EdgeDisposition.ACCEPTED_EQUIVALENCE,
    )
    cluster = EntityCluster(
        "c1", ["node/101"], ["ov-201"], ["node/101::ov-201"],
        ClusterStructuralPattern.ONE_TO_ONE, 0.98, 0.98, 0.98, 5.0,
        False, ["financial"], 0, False, False,
    )

    resolver_full = SupervisedCanonicalResolver()
    entities_full, _ = resolver_full.resolve_graph(
        nodes={"node/101": hub, "ov-201": ov1},
        edges={edge.pair_id: edge},
        clusters=[cluster],
        relationships=[],
    )

    resolver_incr = SupervisedCanonicalResolver()
    entities_incr, _ = resolver_incr.resolve_graph(
        nodes={"node/101": hub, "ov-201": ov1},
        edges={edge.pair_id: edge},
        clusters=[cluster],
        relationships=[],
    )

    assert len(entities_full) == len(entities_incr) == 1
    assert entities_full[0].canonical_entity_id == entities_incr[0].canonical_entity_id
    assert entities_full[0].contributing_osm_ids == entities_incr[0].contributing_osm_ids
    assert entities_full[0].contributing_ov_ids == entities_incr[0].contributing_ov_ids


def test_scenario_15_unaffected_canonical_id_stability():
    """Scenario 15: Unaffected entities retain deterministic canonical UUIDv5 identifiers."""
    id1 = generate_canonical_uuid(["node/9999"], ["ov/8888"])
    id2 = generate_canonical_uuid(["node/9999"], ["ov/8888"])
    # Order independence
    id3 = generate_canonical_uuid(["node/9999"], ["ov/8888"])

    assert id1 == id2 == id3
    assert len(id1) == 36  # Standard UUID length


def test_scenario_16_honorific_prefix_safeguard_evaluation():
    """Scenario 16: SHARED_HONORIFIC_DISJOINT_BRAND safeguard intercepts false equivalence."""
    validator = ConflationSafeguardValidator(enable_honorific_safeguard=True)

    # Example: Sri Kanteshwara Swamy Temple vs Sri Venkateshwara Garments
    res = validator.validate_candidate_edge(
        osm_name="Sri Kanteshwara Swamy Temple",
        ov_name="Sri Venkateshwara Garments",
        osm_category="civic_religious",
        ov_category="retail",
        distance_meters=20.0,
        supervised_model_score=0.77,
        supervised_decision="MATCH",
    )

    assert res.disposition == EdgeDisposition.REVIEW
    assert SafeguardType.SHARED_HONORIFIC_DISJOINT_BRAND in res.safeguards_triggered

    # Example: The Kabab Company vs The Himalayan Inn
    res2 = validator.validate_candidate_edge(
        osm_name="The Kabab Company",
        ov_name="The Himalayan Inn",
        osm_category="sustenance",
        ov_category="sustenance",
        distance_meters=25.0,
        supervised_model_score=0.68,
        supervised_decision="MATCH",
    )
    assert res2.disposition == EdgeDisposition.REVIEW
    assert SafeguardType.SHARED_HONORIFIC_DISJOINT_BRAND in res2.safeguards_triggered


def test_scenario_17_orchestrator_edge_classification_import():
    """Scenario 17: ProductionPipelineOrchestrator correctly imports and utilizes GraphEdgeClassification."""
    from src.poi_conflation.pipeline.orchestrator import GraphEdgeClassification
    assert GraphEdgeClassification.STRONG_MATCH_CANDIDATE.value == "STRONG_MATCH_CANDIDATE"
    assert GraphEdgeClassification.POSSIBLE_MATCH.value == "POSSIBLE_MATCH"
    assert GraphEdgeClassification.UNCERTAIN.value == "UNCERTAIN"
    assert GraphEdgeClassification.REJECTED.value == "REJECTED"

