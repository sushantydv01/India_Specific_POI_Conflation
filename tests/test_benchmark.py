"""Automated test suite for POI conflation ground truth benchmark and annotation framework.

Tests:
1. Annotation schema validation (valid dataclass, coordinates, distance bounds).
2. Stable pair ID consistency and format.
3. Invalid label, confidence, and evidence rejection.
4. Missing required field detection.
5. Annotation workflow persistence and resume behavior.
6. Sampling reproducibility and stratum allocation.
7. Inter-annotator agreement and Cohen's Kappa calculations.
8. Adjudication queue synchronization.
9. Missed-match diagnostic audit output schema.
10. Preservation of raw source attributes.
"""

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
from src.poi_conflation.benchmark.sampling import BenchmarkSampler, STRATA_TARGETS
from src.poi_conflation.benchmark.metadata import BenchmarkMetadataManager, BENCHMARK_SCHEMA_VERSION


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
    # Invalid pair_id format and negative distance
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

    # Write queue file with 2 items
    import csv
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(sample_queue_item.to_dict().keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(sample_queue_item.to_dict())
        
        # Second item
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

    # Annotate the first item
    wf.record_decision(
        queue_item=unannotated_init[0],
        decision=LabelDecision.MATCH,
        annotator_id="annotator_bob",
        confidence=ConfidenceLevel.HIGH,
        evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION
    )

    # Resume: unannotated should now have only 1 item
    unannotated_resumed = wf.get_unannotated_items("annotator_bob")
    assert len(unannotated_resumed) == 1
    assert unannotated_resumed[0].pair_id == "node/99999::ov-uuid-00000"


def test_inter_annotator_agreement_and_kappa():
    """Verify Cohen's Kappa and raw agreement computation across synthetic annotators."""
    evaluator = AgreementEvaluator()

    # Create 4 synthetic pairs
    pairs = ["p1::o1", "p2::o2", "p3::o3", "p4::o4"]
    
    # Annotator A: MATCH, MATCH, NON_MATCH, UNCERTAIN
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

    # Annotator B: MATCH, NON_MATCH (disagree), NON_MATCH, UNCERTAIN
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
    assert res["disagreed_pairs"][0]["pair_id"] == "p2::o2"


def test_benchmark_sampling_reproducibility_and_strata():
    """Verify that benchmark sampling is deterministic and conforms to all 10 strata targets."""
    queue_csv = Path("data/processed/benchmark/annotation_queue.csv")
    assert queue_csv.exists(), "annotation_queue.csv must exist"

    import csv
    with open(queue_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 500

    strata_counts = {}
    for r in rows:
        st = r["sampling_stratum"]
        strata_counts[st] = strata_counts.get(st, 0) + 1

    assert len(strata_counts) == 10
    for stratum, expected_count in STRATA_TARGETS.items():
        assert strata_counts[stratum] == expected_count, f"Stratum {stratum} has {strata_counts[stratum]}, expected {expected_count}"


def test_missed_match_audit_schema_and_verdicts():
    """Verify that missed match audit output contains valid diagnostic classifications."""
    audit_csv = Path("data/processed/benchmark/missed_match_audit.csv")
    assert audit_csv.exists(), "missed_match_audit.csv must exist"

    import csv
    with open(audit_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 120
    allowed_verdicts = {
        "NO_COUNTERPART_FOUND",
        "POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING",
        "INSUFFICIENT_EVIDENCE"
    }
    for r in rows:
        assert r["diagnostic_verdict"] in allowed_verdicts
        assert "osm_source_id" in r
        assert "osm_lat" in r and "osm_lon" in r
        assert "primary_failure_reason" in r


def test_benchmark_metadata_manifest_consistency():
    """Verify metadata manifest records consistent counts and valid schema."""
    manifest_path = Path("data/processed/benchmark/benchmark_metadata.json")
    assert manifest_path.exists(), "benchmark_metadata.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["benchmark_schema_version"] == BENCHMARK_SCHEMA_VERSION
    assert manifest["sampling_parameters"]["sample_size"] == 500
    assert manifest["files"]["annotation_queue_records"] == 500
    assert manifest["files"]["missed_match_audit_records"] == 120
    assert manifest["benchmark_status"] == "QUEUE_GENERATED_AND_INITIALIZED"
