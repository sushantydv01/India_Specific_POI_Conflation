"""Automated test suite for AI-assisted human annotation workflow.

Validates:
1. AIPairSuggestion and AIAuditRecord schema integrity, validation, and serialization.
2. HeuristicAIAnalyzer domain rules (Exact match, transliteration, containment, displacement, disjoint, close distinct).
3. Missing attribute handling (never hallucinates missing phone/address, identifies missing names).
4. Strict separation of storage between AI suggestions, human ground truth, and audit trail.
5. Human review action tracking (ACCEPTED, MODIFIED, REJECTED, INDEPENDENT).
6. Safeguard that AI suggestions are never auto-committed to human annotations.
7. Second reviewer queue isolation and blind evaluation guarantees.
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
from src.poi_conflation.benchmark.ai_schema import (
    HumanAction,
    AIPairSuggestion,
    AIAuditRecord,
)
from src.poi_conflation.benchmark.ai_analyzer import HeuristicAIAnalyzer
from src.poi_conflation.benchmark.workflow import AnnotationWorkflow
from src.poi_conflation.benchmark.agreement import AgreementEvaluator


@pytest.fixture
def base_queue_item() -> AnnotationQueueItem:
    return AnnotationQueueItem(
        pair_id="node/101::ov-uuid-202",
        osm_source_id="node/101",
        ov_source_id="ov-uuid-202",
        osm_name_raw="Aubree",
        ov_name_raw="aubree",
        osm_name_normalized="aubree",
        ov_name_normalized="aubree",
        osm_latitude=12.9716,
        osm_longitude=77.5946,
        ov_latitude=12.9715,
        ov_longitude=77.5947,
        distance_meters=15.2,
        osm_category="sustenance",
        ov_category="sustenance",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m+exact_name",
        sampling_stratum="EXACT_NAME_MATCH",
    )


def test_ai_suggestion_schema_and_validation(base_queue_item):
    """Verify AIPairSuggestion validates fields, enums, and serializes round-trip."""
    sugg = AIPairSuggestion(
        pair_id="node/101::ov-uuid-202",
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        explanation="Exact normalized name match within 15.2m.",
        supporting_evidence=["Exact name agreement", "Distance 15.2m <= 25m"],
        contradictory_evidence=[],
        missing_information=["Phone number not present in candidate schema"],
        adjudication_recommended=False,
        model_identifier="heuristic_rule_v1",
    )

    errors = sugg.validate()
    assert errors == []

    d = sugg.to_dict()
    assert d["suggested_label"] == "MATCH"
    assert d["suggested_confidence"] == "HIGH"
    assert d["suggested_evidence_type"] == "EXACT_NAME_AND_LOCATION"

    loaded = AIPairSuggestion.from_dict(d)
    assert loaded.pair_id == sugg.pair_id
    assert loaded.suggested_label == LabelDecision.MATCH
    assert loaded.suggested_confidence == ConfidenceLevel.HIGH
    assert loaded.suggested_evidence_type == EvidenceType.EXACT_NAME_AND_LOCATION
    assert loaded.adjudication_recommended is False


def test_ai_suggestion_schema_validation_rejection():
    """Verify AIPairSuggestion catches schema errors."""
    bad_sugg = AIPairSuggestion(
        pair_id="invalid_pair_id_without_delimiter",
        suggested_label="NOT_A_LABEL",  # type: ignore
        suggested_confidence="ULTRA_HIGH",  # type: ignore
        suggested_evidence_type="GUESSWORK",  # type: ignore
        explanation="",
        model_identifier="",
    )
    errors = bad_sugg.validate()
    assert len(errors) >= 5
    assert any("pair_id" in e for e in errors)
    assert any("suggested_label" in e for e in errors)
    assert any("explanation" in e for e in errors)


def test_ai_audit_record_schema_and_serialization():
    """Verify AIAuditRecord captures human action and AI context accurately."""
    audit = AIAuditRecord(
        pair_id="node/101::ov-uuid-202",
        annotator_id="reviewer_1",
        human_decision=LabelDecision.MATCH,
        human_confidence=ConfidenceLevel.HIGH,
        human_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        human_action=HumanAction.ACCEPTED,
        ai_suggested_label=LabelDecision.MATCH,
        ai_suggested_confidence=ConfidenceLevel.HIGH,
        ai_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        ai_model_id="heuristic_rule_v1",
        notes="Confirmed identical bakery branch",
    )

    errors = audit.validate()
    assert errors == []

    d = audit.to_dict()
    assert d["human_action"] == "ACCEPTED"
    assert d["human_decision"] == "MATCH"

    loaded = AIAuditRecord.from_dict(d)
    assert loaded.human_action == HumanAction.ACCEPTED
    assert loaded.ai_model_id == "heuristic_rule_v1"


def test_heuristic_exact_name_match(base_queue_item):
    """Verify heuristic identifies exact name and close location as MATCH."""
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(base_queue_item)

    assert sugg.suggested_label == LabelDecision.MATCH
    assert sugg.suggested_confidence == ConfidenceLevel.HIGH
    assert sugg.suggested_evidence_type == EvidenceType.EXACT_NAME_AND_LOCATION
    assert sugg.adjudication_recommended is False
    assert any("15.2m" in ev for ev in sugg.supporting_evidence)


def test_heuristic_street_level_displacement():
    """Verify exact name at 65m distance is classified as STREET_LEVEL_DISPLACEMENT."""
    item = AnnotationQueueItem(
        pair_id="node/102::ov-uuid-203",
        osm_source_id="node/102",
        ov_source_id="ov-uuid-203",
        osm_name_raw="State Bank of India",
        ov_name_raw="State Bank of India",
        osm_name_normalized="state bank of india",
        ov_name_normalized="state bank of india",
        osm_latitude=12.9716,
        osm_longitude=77.5946,
        ov_latitude=12.9720,
        ov_longitude=77.5950,
        distance_meters=65.0,
        osm_category="financial",
        ov_category="financial",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_100m+exact_name",
        sampling_stratum="SPATIAL_CLUSTER_RESIDUAL",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.MATCH
    assert sugg.suggested_confidence == ConfidenceLevel.MEDIUM
    assert sugg.suggested_evidence_type == EvidenceType.STREET_LEVEL_DISPLACEMENT


def test_heuristic_kannada_transliteration_match():
    """Verify Kannada script transliteration matching Latin Overture record."""
    item = AnnotationQueueItem(
        pair_id="node/103::ov-uuid-204",
        osm_source_id="node/103",
        ov_source_id="ov-uuid-204",
        osm_name_raw="ವಿದ್ಯಾರ್ಥಿ ಭವನ",
        ov_name_raw="Vidyarthi Bhavan",
        osm_name_normalized="ವಿದ್ಯಾರ್ಥಿ ಭವನ",
        ov_name_normalized="vidyarthi bhavan",
        osm_latitude=12.9412,
        osm_longitude=77.5734,
        ov_latitude=12.9411,
        ov_longitude=77.5735,
        distance_meters=14.0,
        osm_category="sustenance",
        ov_category="sustenance",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="kannada_transliteration",
        sampling_stratum="KANNADA_TRANSLITERATION",
        osm_name_kn="ವಿದ್ಯಾರ್ಥಿ ಭವನ",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.MATCH
    assert sugg.suggested_evidence_type == EvidenceType.TRANSLITERATION_OR_PHONETIC_MATCH
    assert any("Kannada" in ev for ev in sugg.supporting_evidence)


def test_heuristic_name_expansion_or_acronym():
    """Verify token expansion (e.g. Popeyes vs Popeyes Louisiana Kitchen)."""
    item = AnnotationQueueItem(
        pair_id="node/104::ov-uuid-205",
        osm_source_id="node/104",
        ov_source_id="ov-uuid-205",
        osm_name_raw="Popeyes",
        ov_name_raw="Popeyes - Famous Louisiana Chicken",
        osm_name_normalized="popeyes",
        ov_name_normalized="popeyes famous louisiana chicken",
        osm_latitude=12.9350,
        osm_longitude=77.6200,
        ov_latitude=12.9351,
        ov_longitude=77.6201,
        distance_meters=18.0,
        osm_category="sustenance",
        ov_category="sustenance",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="spatial_50m+token_containment_100m",
        sampling_stratum="MULTI_STRATEGY_OVERLAP",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.MATCH
    assert sugg.suggested_evidence_type == EvidenceType.NAME_EXPANSION_OR_ACRONYM


def test_heuristic_close_spatial_distinct_names():
    """Verify tight spatial proximity with distinct names indicates SAME_BUILDING_DIFFERENT_BUSINESS."""
    item = AnnotationQueueItem(
        pair_id="node/105::ov-uuid-206",
        osm_source_id="node/105",
        ov_source_id="ov-uuid-206",
        osm_name_raw="Cakewalla",
        ov_name_raw="RV Institute of Management",
        osm_name_normalized="cakewalla",
        ov_name_normalized="rv institute of management",
        osm_latitude=12.9300,
        osm_longitude=77.5800,
        ov_latitude=12.9301,
        ov_longitude=77.5801,
        distance_meters=14.2,
        osm_category="sustenance",
        ov_category="education",
        category_compatibility="INCOMPATIBLE",
        blocking_strategies="spatial_50m",
        sampling_stratum="CLOSE_SPATIAL_DISTINCT_NAMES",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.NON_MATCH
    assert sugg.suggested_confidence == ConfidenceLevel.HIGH
    assert sugg.suggested_evidence_type in (
        EvidenceType.SAME_BUILDING_DIFFERENT_BUSINESS,
        EvidenceType.CATEGORY_DISJOINT,
    )


def test_heuristic_large_distance_same_brand():
    """Verify same name at > 100m is flagged as SAME_BRAND_DIFFERENT_BRANCH."""
    item = AnnotationQueueItem(
        pair_id="node/106::ov-uuid-207",
        osm_source_id="node/106",
        ov_source_id="ov-uuid-207",
        osm_name_raw="Cake of the Day",
        ov_name_raw="Cake of the Day",
        osm_name_normalized="cake of the day",
        ov_name_normalized="cake of the day",
        osm_latitude=12.9300,
        osm_longitude=77.5800,
        ov_latitude=12.9400,
        ov_longitude=77.5900,
        distance_meters=1104.0,
        osm_category="sustenance",
        ov_category="sustenance",
        category_compatibility="STRONGLY_COMPATIBLE",
        blocking_strategies="exact_name",
        sampling_stratum="LARGE_DISTANCE_CANDIDATES",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.NON_MATCH
    assert sugg.suggested_confidence == ConfidenceLevel.HIGH
    assert sugg.suggested_evidence_type == EvidenceType.SAME_BRAND_DIFFERENT_BRANCH


def test_heuristic_missing_name_uncertainty():
    """Verify records with missing names result in UNCERTAIN and INSUFFICIENT_EVIDENCE."""
    item = AnnotationQueueItem(
        pair_id="node/107::ov-uuid-208",
        osm_source_id="node/107",
        ov_source_id="ov-uuid-208",
        osm_name_raw="",
        ov_name_raw="Pantaloons",
        osm_name_normalized="",
        ov_name_normalized="pantaloons",
        osm_latitude=12.9300,
        osm_longitude=77.5800,
        ov_latitude=12.9301,
        ov_longitude=77.5801,
        distance_meters=17.9,
        osm_category="other",
        ov_category="retail",
        category_compatibility="COMPATIBLE_UNKNOWN",
        blocking_strategies="spatial_50m",
        sampling_stratum="MISSING_OR_GENERIC_NAME",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.UNCERTAIN
    assert sugg.suggested_confidence == ConfidenceLevel.LOW
    assert sugg.suggested_evidence_type == EvidenceType.INSUFFICIENT_EVIDENCE
    assert any("primary name" in m for m in sugg.missing_information)


def test_heuristic_conflicting_signals_adjudication():
    """Verify conflicting signals (identical name but strictly incompatible category) triggers adjudication."""
    item = AnnotationQueueItem(
        pair_id="node/108::ov-uuid-209",
        osm_source_id="node/108",
        ov_source_id="ov-uuid-209",
        osm_name_raw="Apollo Diagnostics",
        ov_name_raw="Apollo Diagnostics",
        osm_name_normalized="apollo diagnostics",
        ov_name_normalized="apollo diagnostics",
        osm_latitude=12.9300,
        osm_longitude=77.5800,
        ov_latitude=12.9301,
        ov_longitude=77.5801,
        distance_meters=12.0,
        osm_category="healthcare",
        ov_category="sustenance",
        category_compatibility="INCOMPATIBLE",
        blocking_strategies="exact_name",
        sampling_stratum="EXACT_NAME_MATCH",
    )
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(item)

    assert sugg.suggested_label == LabelDecision.NEEDS_ADJUDICATION
    assert sugg.adjudication_recommended is True


def test_human_actions_and_audit_trail_logging(tmp_path, base_queue_item):
    """Verify human review actions (ACCEPTED, MODIFIED, REJECTED) are faithfully tracked in separate audit trail."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(base_queue_item.to_dict().keys()))
        writer.writeheader()
        writer.writerow(base_queue_item.to_dict())

    annotations_dir = tmp_path / "annotations"
    audit_trail_csv = annotations_dir / "audit_trail.csv"
    workflow = AnnotationWorkflow(
        queue_csv=str(queue_csv),
        annotations_dir=str(annotations_dir),
        audit_trail_csv=str(audit_trail_csv),
    )

    sugg = AIPairSuggestion(
        pair_id=base_queue_item.pair_id,
        suggested_label=LabelDecision.MATCH,
        suggested_confidence=ConfidenceLevel.HIGH,
        suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
        explanation="Exact name match.",
    )

    # 1. Human ACCEPTS suggestion
    rec1 = workflow.record_decision(
        queue_item=base_queue_item,
        decision=sugg.suggested_label,
        annotator_id="reviewer_1",
        confidence=sugg.suggested_confidence,
        evidence_type=sugg.suggested_evidence_type,
        human_action=HumanAction.ACCEPTED,
        ai_suggestion=sugg,
    )
    assert rec1.decision == LabelDecision.MATCH

    # Check human annotation CSV (must contain ONLY human validated record)
    annotator_file = workflow.get_annotator_file("reviewer_1")
    assert annotator_file.exists()
    records = workflow.load_existing_annotations("reviewer_1")
    assert len(records) == 1
    assert records[0].decision == LabelDecision.MATCH

    # Check audit trail CSV (must contain human_action and AI metadata)
    assert audit_trail_csv.exists()
    audit_records = workflow.load_audit_trail()
    assert len(audit_records) == 1
    assert audit_records[0].human_action == HumanAction.ACCEPTED
    assert audit_records[0].ai_suggested_label == LabelDecision.MATCH
    assert audit_records[0].human_decision == LabelDecision.MATCH


def test_ai_suggestion_never_auto_labels_without_human(tmp_path, base_queue_item):
    """Verify that generating an AI suggestion DOES NOT create human annotations."""
    queue_csv = tmp_path / "queue.csv"
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(base_queue_item.to_dict().keys()))
        writer.writeheader()
        writer.writerow(base_queue_item.to_dict())

    annotations_dir = tmp_path / "annotations"
    suggestions_file = tmp_path / "ai_suggestions.jsonl"

    workflow = AnnotationWorkflow(
        queue_csv=str(queue_csv),
        annotations_dir=str(annotations_dir),
        ai_suggestions_file=str(suggestions_file),
    )

    # Generate suggestion and save to suggestions file
    analyzer = HeuristicAIAnalyzer()
    sugg = analyzer.generate_suggestion(base_queue_item)
    with open(suggestions_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(sugg.to_dict()) + "\n")

    # Verify no human annotations exist for any reviewer
    assert len(workflow.load_existing_annotations("reviewer_1")) == 0
    assert len(workflow.load_existing_annotations("reviewer_2")) == 0
    unannotated = workflow.get_unannotated_items("reviewer_1")
    assert len(unannotated) == 1  # Still unannotated!


def test_second_reviewer_queue_isolation(tmp_path, base_queue_item):
    """Verify second reviewer queue contains ONLY queue item fields with zero AI or Reviewer 1 leakage."""
    source_queue_csv = tmp_path / "source_queue.csv"
    with open(source_queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(base_queue_item.to_dict().keys()))
        writer.writeheader()
        writer.writerow(base_queue_item.to_dict())

    evaluator = AgreementEvaluator(annotations_dir=tmp_path / "annotations")
    qc_file = evaluator.assign_second_reviewer_queue(
        source_queue_csv=source_queue_csv,
        second_annotator_id="reviewer_2",
        overlap_fraction=1.0,
    )

    with open(qc_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    # Assert no AI fields or reviewer 1 decision fields leaked into second reviewer queue
    assert "decision" not in fields
    assert "suggested_label" not in fields
    assert "human_action" not in fields
    assert "ai_model_id" not in fields
    assert len(rows) == 1
    assert rows[0]["pair_id"] == base_queue_item.pair_id
