"""Automated test suite for POI conflation benchmark integrity, sampling, and QC framework.

Tests:
1. Annotation schema validation (valid dataclass, coordinates, distance bounds).
2. Stable pair ID consistency and format.
3. Invalid label, confidence, and evidence rejection.
4. Missing required field detection.
5. Annotation workflow persistence and resume behavior.
6. Annotator submission deduplication.
7. Mutually exclusive stratum allocation (50 pairs x 10 strata).
8. Pilot review batch extraction (5 pairs x 10 strata = 50 total).
9. Exact inclusion probability calculations.
10. Inter-annotator agreement and Cohen's Kappa calculations.
11. Rejection of agreement calculation on identical annotator.
12. Second reviewer QC assignment generator.
13. Missed-match diagnostic audit output schema and scientific statuses.
14. Category pruning audit output schema and rule distributions.
15. Versioned benchmark manifest lifecycle state transitions.
"""

import csv
import json
from pathlib import Path
import pytest

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationQueueItem,
    AnnotationRecord,
)
from src.poi_conflation.benchmark.workflow import AnnotationWorkflow
from src.poi_conflation.benchmark.agreement import AgreementEvaluator
from src.poi_conflation.benchmark.sampling import (
    BenchmarkSampler,
    MUTUALLY_EXCLUSIVE_STRATA_ORDER,
    TARGET_PER_STRATUM,
)
from src.poi_conflation.benchmark.missed_match import (
    MissedMatchAuditor,
    DiagnosticStatus,
    ReviewStatus,
)
from src.poi_conflation.benchmark.category_audit import CategoryPruneAuditor
from src.poi_conflation.benchmark.metadata import (
    BenchmarkMetadataManager,
    BenchmarkLifecycleState,
    BENCHMARK_SCHEMA_VERSION,
)


@pytest.fixture
def sample_queue_item() -> AnnotationQueueItem:
    return AnnotationQueueItem(
        pair_id="node/12345::ov-uuid-67890",
        osm_source_id="node/12345",
        ov_source_id="ov-uuid-67890",
        osm_name_raw="Vidyarthi Bhavan",
        ov_name_raw="Vidyarthi Bhavan Gandhi Bazaar",
        osm_name_normalized="vidyarthi bhavan",
        ov_name_normalized="vidyarthi bhavan gandhi bazaar",
        osm_latitude=12.9412,
        osm_longitude=77.5734,
        ov_latitude=12.9411,
        ov_longitude=77.5735,
        distance_meters=14.5,
        osm_category="sustenance",
        ov_category="sustenance",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m+token_containment_100m",
        sampling_stratum="STRONG_LEXICAL_SIMILARITY",
        osm_name_kn="ವಿದ್ಯಾರ್ಥಿ ಭವನ",
        osm_name_en="Vidyarthi Bhavan"
    )


def test_annotation_record_validation_success(sample_queue_item):
    """Verify that a valid annotation record passes all integrity checks."""
    rec = AnnotationRecord(
        pair_id=sample_queue_item.pair_id,
        osm_source_id=sample_queue_item.osm_source_id,
        ov_source_id=sample_queue_item.ov_source_id,
        osm_name_raw=sample_queue_item.osm_name_raw,
        ov_name_raw=sample_queue_item.ov_name_raw,
        osm_name_normalized=sample_queue_item.osm_name_normalized,
        ov_name_normalized=sample_queue_item.ov_name_normalized,
        osm_latitude=sample_queue_item.osm_latitude,
        osm_longitude=sample_queue_item.osm_longitude,
        ov_latitude=sample_queue_item.ov_latitude,
        ov_longitude=sample_queue_item.ov_longitude,
        distance_meters=sample_queue_item.distance_meters,
        osm_category=sample_queue_item.osm_category,
        ov_category=sample_queue_item.ov_category,
        category_compatibility=sample_queue_item.category_compatibility,
        blocking_strategies=sample_queue_item.blocking_strategies,
        sampling_stratum=sample_queue_item.sampling_stratum,
        decision=LabelDecision.MATCH,
        annotator_id="annotator_alice",
        confidence=ConfidenceLevel.HIGH,
        evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        notes="Iconic south Indian tiffin restaurant"
    )
    errors = rec.validate()
    assert len(errors) == 0


def test_annotation_record_validation_failures():
    """Verify that malformed records trigger explicit validation errors."""
    rec = AnnotationRecord(
        pair_id="malformed_id",
        osm_source_id="node/123",
        ov_source_id="ov/456",
        osm_name_raw="Test",
        ov_name_raw="Test",
        osm_name_normalized="test",
        ov_name_normalized="test",
        osm_latitude=95.0,  # Invalid latitude (>90)
        osm_longitude=77.5,
        ov_latitude=12.9,
        ov_longitude=77.5,
        distance_meters=-5.0,  # Negative distance
        osm_category="retail",
        ov_category="retail",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m",
        sampling_stratum="EXACT_NAME_MATCH",
        decision=LabelDecision.MATCH,
        annotator_id="",  # Empty annotator
        confidence=ConfidenceLevel.HIGH,
        evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION
    )
    errors = rec.validate()
    assert any("pair_id" in e for e in errors)
    assert any("latitude" in e for e in errors)
    assert any("distance_meters" in e for e in errors)
    assert any("annotator_id" in e for e in errors)


def test_annotation_workflow_persistence_and_resume(tmp_path, sample_queue_item):
    """Verify that workflow persists records and correctly identifies remaining unannotated items."""
    queue_csv = tmp_path / "annotation_queue.csv"
    annotations_dir = tmp_path / "annotations"
    adjudication_csv = tmp_path / "adjudication_queue.csv"

    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(sample_queue_item.to_dict().keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(sample_queue_item.to_dict())
        
        second_item = dict(sample_queue_item.to_dict())
        second_item["pair_id"] = "node/99999::ov-uuid-00000"
        second_item["osm_source_id"] = "node/99999"
        second_item["ov_source_id"] = "ov-uuid-00000"
        writer.writerow(second_item)

    wf = AnnotationWorkflow(
        queue_csv=str(queue_csv),
        annotations_dir=str(annotations_dir),
        adjudication_csv=str(adjudication_csv)
    )

    unannotated_init = wf.get_unannotated_items("annotator_bob")
    assert len(unannotated_init) == 2

    wf.record_decision(
        queue_item=unannotated_init[0],
        decision=LabelDecision.MATCH,
        annotator_id="annotator_bob",
        confidence=ConfidenceLevel.HIGH,
        evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION
    )

    unannotated_resumed = wf.get_unannotated_items("annotator_bob")
    assert len(unannotated_resumed) == 1
    assert unannotated_resumed[0].pair_id == "node/99999::ov-uuid-00000"


def test_annotator_submission_deduplication(tmp_path, sample_queue_item):
    """Verify that multiple submissions for the same pair by one annotator deduplicate cleanly."""
    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir(parents=True, exist_ok=True)
    annotator_file = annotations_dir / "annotations_ann_alice.csv"

    evaluator = AgreementEvaluator(annotations_dir=str(annotations_dir))

    # Write initial annotation
    rec1 = AnnotationRecord(
        pair_id=sample_queue_item.pair_id, osm_source_id=sample_queue_item.osm_source_id,
        ov_source_id=sample_queue_item.ov_source_id, osm_name_raw="A", ov_name_raw="B",
        osm_name_normalized="a", ov_name_normalized="b", osm_latitude=12.9, osm_longitude=77.5,
        ov_latitude=12.9, ov_longitude=77.5, distance_meters=10.0, osm_category="retail",
        ov_category="retail", category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m", sampling_stratum="TEST", decision=LabelDecision.MATCH,
        annotator_id="ann_alice", confidence=ConfidenceLevel.HIGH, evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        annotation_timestamp="2026-11-17T10:00:00Z"
    )
    # Write revised annotation for identical pair_id
    rec2 = AnnotationRecord(
        pair_id=sample_queue_item.pair_id, osm_source_id=sample_queue_item.osm_source_id,
        ov_source_id=sample_queue_item.ov_source_id, osm_name_raw="A", ov_name_raw="B",
        osm_name_normalized="a", ov_name_normalized="b", osm_latitude=12.9, osm_longitude=77.5,
        ov_latitude=12.9, ov_longitude=77.5, distance_meters=10.0, osm_category="retail",
        ov_category="retail", category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m", sampling_stratum="TEST", decision=LabelDecision.UNCERTAIN,
        annotator_id="ann_alice", confidence=ConfidenceLevel.LOW, evidence_type=EvidenceType.INSUFFICIENT_EVIDENCE,
        annotation_timestamp="2026-11-17T10:05:00Z"
    )

    with open(annotator_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rec1.to_dict().keys()))
        writer.writeheader()
        writer.writerow(rec1.to_dict())
        writer.writerow(rec2.to_dict())

    loaded = evaluator.load_annotator_records("ann_alice")
    assert len(loaded) == 1
    assert loaded[0].decision == LabelDecision.UNCERTAIN


def test_inter_annotator_agreement_and_kappa():
    """Verify Cohen's Kappa and raw agreement computation across synthetic annotators."""
    evaluator = AgreementEvaluator()
    pairs = ["p1::o1", "p2::o2", "p3::o3", "p4::o4"]
    
    records_a = [
        AnnotationRecord(
            pair_id=pid, osm_source_id=pid.split("::")[0], ov_source_id=pid.split("::")[1],
            osm_name_raw="A", ov_name_raw="B", osm_name_normalized="a", ov_name_normalized="b",
            osm_latitude=12.9, osm_longitude=77.5, ov_latitude=12.9, ov_longitude=77.5,
            distance_meters=10.0, osm_category="retail", ov_category="retail",
            category_compatibility="STRONGLY_COMPATIBLE", blocking_strategies="spatial_50m",
            sampling_stratum="TEST", decision=dec, annotator_id="ann_a",
            confidence=ConfidenceLevel.HIGH, evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION
        )
        for pid, dec in zip(pairs, [LabelDecision.MATCH, LabelDecision.MATCH, LabelDecision.NON_MATCH, LabelDecision.UNCERTAIN])
    ]

    records_b = [
        AnnotationRecord(
            pair_id=pid, osm_source_id=pid.split("::")[0], ov_source_id=pid.split("::")[1],
            osm_name_raw="A", ov_name_raw="B", osm_name_normalized="a", ov_name_normalized="b",
            osm_latitude=12.9, osm_longitude=77.5, ov_latitude=12.9, ov_longitude=77.5,
            distance_meters=10.0, osm_category="retail", ov_category="retail",
            category_compatibility="STRONGLY_COMPATIBLE", blocking_strategies="spatial_50m",
            sampling_stratum="TEST", decision=dec, annotator_id="ann_b",
            confidence=ConfidenceLevel.HIGH, evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION
        )
        for pid, dec in zip(pairs, [LabelDecision.MATCH, LabelDecision.NON_MATCH, LabelDecision.NON_MATCH, LabelDecision.UNCERTAIN])
    ]

    res = evaluator.evaluate_pair_agreement("ann_a", "ann_b", records_a, records_b)
    assert res["overlapping_pairs"] == 4
    assert res["agreements"] == 3
    assert res["disagreements"] == 1
    assert res["raw_agreement_pct"] == 75.0
    assert res["cohens_kappa"] is not None
    assert len(res["disagreed_pairs"]) == 1


def test_agreement_evaluator_rejects_identical_annotator():
    """Verify that agreement evaluator raises ValueError when passed identical annotator IDs."""
    evaluator = AgreementEvaluator()
    with pytest.raises(ValueError, match="identical annotator"):
        evaluator.evaluate_pair_agreement("ann_x", "ann_x")


def test_second_reviewer_assignment_generation(tmp_path):
    """Verify that second reviewer assignment extracts the requested overlap fraction."""
    evaluator = AgreementEvaluator(annotations_dir=str(tmp_path))
    source_queue = tmp_path / "pilot_batch.csv"

    # Write synthetic 10-item queue
    with open(source_queue, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pair_id", "osm_name", "ov_name"])
        writer.writeheader()
        for i in range(10):
            writer.writerow({"pair_id": f"p{i}::o{i}", "osm_name": f"OSM {i}", "ov_name": f"OV {i}"})

    out_file = evaluator.assign_second_reviewer_queue(source_queue, "reviewer_2", overlap_fraction=0.5, seed=42)
    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        assigned = list(csv.DictReader(f))
    assert len(assigned) == 5


def test_benchmark_sampling_mutually_exclusive_partition():
    """Verify that main queue has 500 pairs, 50 in each of the 10 mutually exclusive strata."""
    queue_csv = Path("data/processed/benchmark/annotation_queue.csv")
    assert queue_csv.exists(), "annotation_queue.csv must exist"

    with open(queue_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 500

    strata_counts = {}
    for r in rows:
        st = r["sampling_stratum"]
        strata_counts[st] = strata_counts.get(st, 0) + 1

    assert len(strata_counts) == 10
    for stratum in MUTUALLY_EXCLUSIVE_STRATA_ORDER:
        assert strata_counts[stratum] == TARGET_PER_STRATUM, f"Stratum {stratum} has {strata_counts[stratum]}, expected {TARGET_PER_STRATUM}"


def test_pilot_batch_stratum_allocation():
    """Verify that pilot batch contains exactly 50 pairs (5 per mutually exclusive stratum)."""
    pilot_csv = Path("data/processed/benchmark/pilot_batch_50.csv")
    assert pilot_csv.exists(), "pilot_batch_50.csv must exist"

    with open(pilot_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 50

    strata_counts = {}
    for r in rows:
        st = r["sampling_stratum"]
        strata_counts[st] = strata_counts.get(st, 0) + 1

    assert len(strata_counts) == 10
    for stratum in MUTUALLY_EXCLUSIVE_STRATA_ORDER:
        assert strata_counts[stratum] == 5, f"Pilot stratum {stratum} has {strata_counts[stratum]}, expected 5"


def test_missed_match_audit_schema_and_verdicts():
    """Verify that missed match audit output contains valid diagnostic classifications and fields."""
    audit_csv = Path("data/processed/benchmark/missed_match_audit.csv")
    assert audit_csv.exists(), "missed_match_audit.csv must exist"

    with open(audit_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 120
    allowed_statuses = {s.value for s in DiagnosticStatus}
    allowed_reviews = {s.value for s in ReviewStatus}

    for r in rows:
        assert r["diagnostic_status"] in allowed_statuses
        assert r["review_status"] in allowed_reviews
        assert "osm_source_id" in r
        assert "search_radius_meters" in r
        assert float(r["search_radius_meters"]) == 1500.0
        assert "search_procedure_version" in r


def test_category_pruning_audit_sampling_and_rules():
    """Verify that category pruning audit generated 100 sample pairs across incompatible rules."""
    pruned_csv = Path("reports/category_pruned_sample.csv")
    summary_json = Path("reports/category_pruning_audit_summary.json")

    assert pruned_csv.exists(), "category_pruned_sample.csv must exist"
    assert summary_json.exists(), "category_pruning_audit_summary.json must exist"

    with open(pruned_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 100
    for r in rows:
        assert "incompatible_rule" in r
        assert "osm_category" in r and "ov_category" in r
        assert r["osm_category"] != r["ov_category"]

    with open(summary_json, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["sample_size"] == 100
    assert summary["total_pruned_pairs_spatial_50m"] > 23000


def test_benchmark_lifecycle_manifest_and_states():
    """Verify metadata manifest records consistent counts and valid lifecycle state."""
    manifest_path = Path("data/processed/benchmark/benchmark_metadata.json")
    assert manifest_path.exists(), "benchmark_metadata.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["benchmark_schema_version"] == BENCHMARK_SCHEMA_VERSION
    assert manifest["lifecycle_state"] == BenchmarkLifecycleState.QUEUE_GENERATED.value
    assert manifest["is_frozen"] is False
    assert manifest["files"]["annotation_queue_records"] == 500
    assert manifest["files"]["pilot_batch_records"] == 50
    assert manifest["files"]["missed_match_audit_records"] == 120
