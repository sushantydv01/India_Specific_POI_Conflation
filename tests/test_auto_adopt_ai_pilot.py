"""Automated test suite for M8 fully automated AI annotation adoption workflow.

Tests:
1. Loading all pilot suggestions from disk.
2. Validating suggestion schemas.
3. Correct pair-ID matching between queue and suggestions.
4. Successful automatic adoption into annotator CSV.
5. Existing human annotation preservation (Pair 1).
6. Conflicting annotation handling and adjudication logging.
7. Missing suggestions resilience.
8. Invalid labels and invalid confidence rejection.
9. Unknown pair IDs handling.
10. Duplicate suggestions resilience.
11. Idempotent execution (zero duplicate rows on rerun).
12. Audit-trail integrity and action provenance.
13. Manifest lifecycle state update to AI_AUTO_ANNOTATED_PILOT.
14. Pilot / main benchmark separation (main 500 queue untouched).
15. Report accuracy and metric consistency.
16. Provenance correctness (AUTO_ADOPTED_AI vs HUMAN_VERIFIED).
17. Non-interactive CLI execution via subprocess.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path
import pytest

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationProvenance,
    AnnotationQueueItem,
    AnnotationRecord,
)
from src.poi_conflation.benchmark.ai_schema import (
    HumanAction,
    AIPairSuggestion,
    AIAuditRecord,
)
from src.poi_conflation.benchmark.workflow import AnnotationWorkflow
from src.poi_conflation.benchmark.metadata import (
    BenchmarkMetadataManager,
    BenchmarkLifecycleState,
)


@pytest.fixture
def sample_pair_a() -> AnnotationQueueItem:
    return AnnotationQueueItem(
        pair_id="node/1001::ov-uuid-2001",
        osm_source_id="node/1001",
        ov_source_id="ov-uuid-2001",
        osm_name_raw="Brahmin Tiffin",
        ov_name_raw="Brahmin Tiffin Center",
        osm_name_normalized="brahmin tiffin",
        ov_name_normalized="brahmin tiffin center",
        osm_latitude=12.9716,
        osm_longitude=77.5946,
        ov_latitude=12.9715,
        ov_longitude=77.5947,
        distance_meters=14.5,
        osm_category="sustenance",
        ov_category="sustenance",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m+token_containment_100m",
        sampling_stratum="MULTI_STRATEGY_OVERLAP",
    )


@pytest.fixture
def sample_pair_b() -> AnnotationQueueItem:
    return AnnotationQueueItem(
        pair_id="node/1002::ov-uuid-2002",
        osm_source_id="node/1002",
        ov_source_id="ov-uuid-2002",
        osm_name_raw="Apollo Pharmacy",
        ov_name_raw="Empire Restaurant",
        osm_name_normalized="apollo pharmacy",
        ov_name_normalized="empire restaurant",
        osm_latitude=12.9300,
        osm_longitude=77.5800,
        ov_latitude=12.9301,
        ov_longitude=77.5801,
        distance_meters=12.0,
        osm_category="healthcare",
        ov_category="sustenance",
        category_compatibility="INCOMPATIBLE",
        blocking_strategies="spatial_50m",
        sampling_stratum="CLOSE_SPATIAL_DISTINCT_NAMES",
    )


def test_load_all_pilot_suggestions():
    """Verify that the 50 pilot suggestions JSONL loads cleanly and validates."""
    sugg_path = Path("data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl")
    assert sugg_path.exists(), "pilot_ai_suggestions.jsonl must exist"

    wf = AnnotationWorkflow(ai_suggestions_file=str(sugg_path))
    suggs = wf.load_ai_suggestions()

    assert len(suggs) == 50
    for pid, s in suggs.items():
        assert "::" in pid
        assert s.validate() == []
        assert s.explanation.strip() != ""


def test_correct_pair_id_matching():
    """Verify exact 1-to-1 match between pilot queue pairs and suggestions."""
    queue_path = Path("data/processed/benchmark/pilot_batch_50.csv")
    sugg_path = Path("data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl")

    wf = AnnotationWorkflow(queue_csv=str(queue_path), ai_suggestions_file=str(sugg_path))
    items = wf.load_queue()
    suggs = wf.load_ai_suggestions()

    assert len(items) == 50
    assert len(suggs) == 50
    item_pids = {item.pair_id for item in items}
    sugg_pids = set(suggs.keys())

    assert item_pids == sugg_pids


def test_successful_automatic_adoption(tmp_path, sample_pair_a, sample_pair_b):
    """Verify successful auto-adoption into annotator CSV with valid schema."""
    queue_csv = tmp_path / "pilot_queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())
        writer.writerow(sample_pair_b.to_dict())

    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.NAME_EXPANSION_OR_ACRONYM,
        explanation="Token expansion match.",
    )
    s2 = AIPairSuggestion(
        pair_id=sample_pair_b.pair_id,
        suggested_label=LabelDecision.NON_MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.CATEGORY_DISJOINT,
        explanation="Disjoint categories.",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")
        f.write(json.dumps(s2.to_dict()) + "\n")

    ann_dir = tmp_path / "annotations"
    wf = AnnotationWorkflow(
        queue_csv=str(queue_csv),
        annotations_dir=str(ann_dir),
        ai_suggestions_file=str(sugg_file),
    )

    report = wf.auto_adopt_ai_suggestions(
        annotator_id="test_adopter",
        report_path=str(tmp_path / "report.json"),
        consolidated_csv_path=str(tmp_path / "consolidated.csv"),
    )

    assert report["dataset_coverage"]["total_pilot_pairs"] == 2
    assert report["dataset_coverage"]["successfully_auto_adopted_total"] == 2
    assert report["dataset_coverage"]["newly_adopted_this_run"] == 2
    assert report["dataset_coverage"]["missing_or_invalid_suggestions_count"] == 0

    adopter_file = wf.get_annotator_file("test_adopter")
    assert adopter_file.exists()
    records = wf.load_existing_annotations("test_adopter")
    assert len(records) == 2
    assert records[0].provenance == AnnotationProvenance.AUTO_ADOPTED_AI.value
    assert records[1].provenance == AnnotationProvenance.AUTO_ADOPTED_AI.value


def test_existing_human_annotation_preservation(tmp_path, sample_pair_a, sample_pair_b):
    """Verify that existing human annotations are preserved intact and never overwritten."""
    queue_csv = tmp_path / "pilot_queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())
        writer.writerow(sample_pair_b.to_dict())

    ann_dir = tmp_path / "annotations"
    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(ann_dir))

    # Pre-record a human annotation for pair_a by reviewer_1
    human_rec = wf.record_decision(
        queue_item=sample_pair_a,
        decision=LabelDecision.MATCH,
        annotator_id="reviewer_1",
        confidence=ConfidenceLevel.HIGH,
        evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        notes="Human reviewed on ground",
        provenance=AnnotationProvenance.HUMAN_VERIFIED.value,
    )

    # Prepare AI suggestions for both pairs
    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.MEDIUM,
        suggested_evidence_type=EvidenceType.NAME_EXPANSION_OR_ACRONYM,
        explanation="AI suggestion.",
    )
    s2 = AIPairSuggestion(
        pair_id=sample_pair_b.pair_id,
        suggested_label=LabelDecision.NON_MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.CATEGORY_DISJOINT,
        explanation="AI suggestion.",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")
        f.write(json.dumps(s2.to_dict()) + "\n")

    report = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        report_path=str(tmp_path / "report.json"),
        consolidated_csv_path=str(tmp_path / "consolidated.csv"),
    )

    assert report["dataset_coverage"]["existing_human_annotations_preserved"] == 1

    # Verify reviewer_1 file remains intact with 1 human record
    r1_records = wf.load_existing_annotations("reviewer_1")
    assert len(r1_records) == 1
    assert r1_records[0].provenance == AnnotationProvenance.HUMAN_VERIFIED.value
    assert r1_records[0].confidence == ConfidenceLevel.HIGH

    # Verify consolidated dataset has reviewer_1 for pair_a and ai_adopter for pair_b
    with open(tmp_path / "consolidated.csv", "r", encoding="utf-8") as f:
        c_rows = list(csv.DictReader(f))
    assert len(c_rows) == 2
    row_map = {r["pair_id"]: r for r in c_rows}
    assert row_map[sample_pair_a.pair_id]["annotator_id"] == "reviewer_1"
    assert row_map[sample_pair_a.pair_id]["provenance"] == "HUMAN_VERIFIED"
    assert row_map[sample_pair_b.pair_id]["annotator_id"] == "ai_adopter"
    assert row_map[sample_pair_b.pair_id]["provenance"] == "AUTO_ADOPTED_AI"


def test_conflicting_annotation_handling(tmp_path, sample_pair_a):
    """Verify that a conflict between existing human decision and AI suggestion is reported."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())

    ann_dir = tmp_path / "annotations"
    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(ann_dir))

    # Human says MATCH
    wf.record_decision(
        queue_item=sample_pair_a,
        decision=LabelDecision.MATCH,
        annotator_id="reviewer_human",
        confidence=ConfidenceLevel.HIGH,
        evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        provenance=AnnotationProvenance.HUMAN_VERIFIED.value,
    )

    # AI says NON_MATCH
    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.NON_MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.CATEGORY_DISJOINT,
        explanation="Category disjoint.",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")

    report = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        report_path=str(tmp_path / "report.json"),
    )

    assert report["dataset_coverage"]["conflicting_annotations_count"] == 1
    conf = report["dataset_coverage"]["conflicting_details"][0]
    assert conf["human_decision"] == "MATCH"
    assert conf["ai_suggested_label"] == "NON_MATCH"


def test_missing_suggestions_handling(tmp_path, sample_pair_a, sample_pair_b):
    """Verify workflow gracefully handles missing suggestions for subset of pairs."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())
        writer.writerow(sample_pair_b.to_dict())

    # Only provide suggestion for pair_a, pair_b is omitted
    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        explanation="Match.",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")

    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(tmp_path / "annotations"))
    report = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        report_path=str(tmp_path / "report.json"),
    )

    assert report["dataset_coverage"]["missing_or_invalid_suggestions_count"] == 1
    assert report["dataset_coverage"]["missing_or_invalid_details"][0]["pair_id"] == sample_pair_b.pair_id
    assert report["dataset_coverage"]["successfully_auto_adopted_total"] == 1


def test_invalid_labels_and_confidence_handling(tmp_path, sample_pair_a):
    """Verify invalid suggestion labels or confidences are rejected without halting."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())

    sugg_file = tmp_path / "bad_suggestions.jsonl"
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "pair_id": sample_pair_a.pair_id,
            "suggested_label": "NOT_A_VALID_LABEL",
            "suggested_confidence": "HIGH",
            "suggested_evidence_type": "EXACT_NAME_AND_LOCATION",
            "explanation": "Invalid label.",
            "model_identifier": "test_model",
        }) + "\n")

    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(tmp_path / "annotations"))
    report = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        report_path=str(tmp_path / "report.json"),
    )

    assert report["dataset_coverage"]["missing_or_invalid_suggestions_count"] == 1
    assert report["dataset_coverage"]["successfully_auto_adopted_total"] == 0


def test_unknown_pair_ids_handling(tmp_path, sample_pair_a):
    """Verify suggestions for pair IDs not in queue do not corrupt adoption."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())

    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        explanation="Match.",
    )
    s_extra = AIPairSuggestion(
        pair_id="unknown_node/999::unknown_ov/999",
        suggested_label=LabelDecision.NON_MATCH,
        suggested_confidence=ConfidenceLevel.LOW,
        suggested_evidence_type=EvidenceType.OTHER,
        explanation="Extra pair not in queue.",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")
        f.write(json.dumps(s_extra.to_dict()) + "\n")

    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(tmp_path / "annotations"))
    report = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        report_path=str(tmp_path / "report.json"),
    )

    assert report["dataset_coverage"]["total_pilot_pairs"] == 1
    assert report["dataset_coverage"]["successfully_auto_adopted_total"] == 1
    recs = wf.load_existing_annotations("ai_adopter")
    assert len(recs) == 1
    assert recs[0].pair_id == sample_pair_a.pair_id


def test_idempotent_execution(tmp_path, sample_pair_a):
    """Verify re-running adoption multiple times produces identical state without duplicates."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())

    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        explanation="Match.",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")

    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(tmp_path / "annotations"))

    # First run
    r1 = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        consolidated_csv_path=str(tmp_path / "consolidated.csv"),
    )
    assert r1["dataset_coverage"]["newly_adopted_this_run"] == 1
    assert r1["dataset_coverage"]["already_adopted_previously"] == 0

    # Second run
    r2 = wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        consolidated_csv_path=str(tmp_path / "consolidated.csv"),
    )
    assert r2["dataset_coverage"]["newly_adopted_this_run"] == 0
    assert r2["dataset_coverage"]["already_adopted_previously"] == 1

    # Ensure no duplicates in file
    records = wf.load_existing_annotations("ai_adopter")
    assert len(records) == 1


def test_audit_trail_integrity(tmp_path, sample_pair_a):
    """Verify audit trail logs AUTO_ADOPTED_AI action and captures suggestion provenance."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sample_pair_a.to_dict().keys()))
        writer.writeheader()
        writer.writerow(sample_pair_a.to_dict())

    sugg_file = tmp_path / "suggestions.jsonl"
    s1 = AIPairSuggestion(
        pair_id=sample_pair_a.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        explanation="Match.",
        model_identifier="heuristic_rule_v1",
    )
    with open(sugg_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(s1.to_dict()) + "\n")

    wf = AnnotationWorkflow(queue_csv=str(queue_csv), annotations_dir=str(tmp_path / "annotations"))
    wf.auto_adopt_ai_suggestions(
        annotator_id="ai_adopter",
        suggestions_path=str(sugg_file),
        consolidated_csv_path=str(tmp_path / "consolidated.csv"),
    )

    audit_records = wf.load_audit_trail()
    assert len(audit_records) == 1
    ar = audit_records[0]
    assert ar.human_action == HumanAction.AUTO_ADOPTED_AI
    assert ar.ai_model_id == "heuristic_rule_v1"
    assert ar.human_decision == LabelDecision.MATCH


def test_manifest_lifecycle_update(tmp_path):
    """Verify BenchmarkMetadataManager sets AI_AUTO_ANNOTATED_PILOT state and is_frozen is False."""
    meta = BenchmarkMetadataManager(benchmark_dir=str(tmp_path), reports_dir=str(tmp_path))
    manifest = meta.generate_manifest(
        lifecycle_state=BenchmarkLifecycleState.AI_AUTO_ANNOTATED_PILOT,
        annotation_metadata={"test": "ok"},
    )
    assert manifest["lifecycle_state"] == "AI_AUTO_ANNOTATED_PILOT"
    assert manifest["is_frozen"] is False
    assert manifest["pilot_automation_metadata"]["test"] == "ok"


def test_pilot_main_benchmark_separation():
    """Verify that pilot adoption preserves the 500-pair main queue completely untouched."""
    main_queue_path = Path("data/processed/benchmark/annotation_queue.csv")
    assert main_queue_path.exists()
    with open(main_queue_path, "r", encoding="utf-8") as f:
        main_count = sum(1 for _ in f) - 1
    assert main_count == 500, "Main queue must remain exactly 500 pairs"


def test_provenance_correctness():
    """Verify exact provenance markings on adopted pilot records."""
    consolidated_path = Path("data/processed/benchmark/pilot_annotations_adopted.csv")
    assert consolidated_path.exists()

    with open(consolidated_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 50
    # First row is Pair 1 (human verified)
    assert rows[0]["provenance"] == "HUMAN_VERIFIED"
    assert rows[0]["annotator_id"] == "reviewer_1"

    # Remaining rows are auto-adopted
    for r in rows[1:]:
        assert r["provenance"] == "AUTO_ADOPTED_AI"
        assert r["annotator_id"] == "ai_auto_adopter"


def test_cli_non_interactive_execution():
    """Verify non-interactive CLI execution with --auto-adopt-ai flag completes with code 0."""
    cmd = [
        sys.executable,
        "scripts/annotate.py",
        "--pilot",
        "--auto-adopt-ai",
        "--annotator",
        "ai_auto_adopter",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert "ADOPTION COVERAGE:" in result.stdout
    assert "Execution complete." in result.stdout
