"""Tests for Milestone 11 Human Adjudication, Inter-Annotator Agreement, and Benchmark Validation."""

import json
import uuid
import pytest
from pathlib import Path
import duckdb

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationProvenance,
    AnnotationRecord,
)
from src.poi_conflation.benchmark.agreement import AgreementEvaluator
from src.poi_conflation.benchmark.adjudication import (
    AdjudicationRecord,
    AdjudicationWorkflow,
)
from src.poi_conflation.graph.canonical_resolver import (
    CANONICAL_ENTITY_NAMESPACE,
    CanonicalEntityResolver,
    generate_canonical_uuid,
)


class TestHumanAdjudicationModels:
    """Tests validation, serialization, and lifecycle of AdjudicationRecord."""

    def test_adjudication_record_validation(self):
        rec = AdjudicationRecord(
            pair_id="osm/101::ov/202",
            adjudicator_id="lead_adjudicator",
            primary_review={"decision": "MATCH", "notes": "R1 note"},
            secondary_review={"decision": "UNCERTAIN", "notes": "R2 note"},
            final_decision=LabelDecision.MATCH.value,
            confidence=ConfidenceLevel.HIGH.value,
            evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION.value,
            rationale="Verified identity match after evaluating entrance displacement.",
            provenance=AnnotationProvenance.HUMAN_ADJUDICATED.value,
        )
        errors = rec.validate()
        assert len(errors) == 0

    def test_adjudication_record_validation_errors(self):
        # Invalid pair_id
        rec1 = AdjudicationRecord(
            pair_id="invalid_pair_id",
            adjudicator_id="lead_adjudicator",
            primary_review={},
            secondary_review=None,
            final_decision="MATCH",
            confidence="HIGH",
            evidence_type="EXACT_NAME_AND_LOCATION",
            rationale="Valid rationale here.",
        )
        assert any("pair_id format" in e for e in rec1.validate())

        # Empty rationale
        rec2 = AdjudicationRecord(
            pair_id="osm/1::ov/2",
            adjudicator_id="lead_adjudicator",
            primary_review={},
            secondary_review=None,
            final_decision="MATCH",
            confidence="HIGH",
            evidence_type="EXACT_NAME_AND_LOCATION",
            rationale="",
        )
        assert any("rationale" in e for e in rec2.validate())

        # Empty adjudicator_id
        rec3 = AdjudicationRecord(
            pair_id="osm/1::ov/2",
            adjudicator_id="",
            primary_review={},
            secondary_review=None,
            final_decision="MATCH",
            confidence="HIGH",
            evidence_type="EXACT_NAME_AND_LOCATION",
            rationale="Valid rationale here.",
        )
        assert any("adjudicator_id is required" in e for e in rec3.validate())

    def test_adjudication_serialization(self):
        rec = AdjudicationRecord(
            pair_id="osm/101::ov/202",
            adjudicator_id="lead_adjudicator",
            primary_review={"decision": "MATCH"},
            secondary_review=None,
            final_decision=LabelDecision.NON_MATCH.value,
            confidence=ConfidenceLevel.HIGH.value,
            evidence_type=EvidenceType.SAME_BUILDING_DIFFERENT_BUSINESS.value,
            rationale="Distinct tenant businesses in same commercial complex.",
        )
        d = rec.to_dict()
        assert d["pair_id"] == "osm/101::ov/202"
        assert d["final_decision"] == "NON_MATCH"
        assert d["provenance"] == AnnotationProvenance.HUMAN_ADJUDICATED.value

        reloaded = AdjudicationRecord.from_dict(d)
        assert reloaded.pair_id == rec.pair_id
        assert reloaded.rationale == rec.rationale


class TestAdjudicationWorkflow:
    """Tests AdjudicationWorkflow queue management and summary generation."""

    def test_workflow_lifecycle(self, tmp_path):
        benchmark_dir = tmp_path / "benchmark"
        reports_dir = tmp_path / "reports"
        wf = AdjudicationWorkflow(
            benchmark_dir=str(benchmark_dir),
            reports_dir=str(reports_dir),
        )

        # Initially empty
        assert len(wf.load_adjudicated_records()) == 0

        # Record adjudication
        rec = AdjudicationRecord(
            pair_id="osm/555::ov/777",
            adjudicator_id="adjudicator_test",
            primary_review={"decision": "MATCH"},
            secondary_review={"decision": "NON_MATCH"},
            final_decision=LabelDecision.MATCH.value,
            confidence=ConfidenceLevel.HIGH.value,
            evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION.value,
            rationale="Entrance gate coordinate offset verified.",
        )
        wf.record_adjudication(rec)

        reloaded = wf.load_adjudicated_records()
        assert len(reloaded) == 1
        assert "osm/555::ov/777" in reloaded
        assert reloaded["osm/555::ov/777"].adjudicator_id == "adjudicator_test"

        # Generate summary
        summary = wf.generate_adjudication_summary()
        assert summary["metadata"]["total_cases_adjudicated"] == 1
        assert summary["decision_distribution"]["MATCH"] == 1
        assert summary["annotator_resolution_breakdown"]["upheld_primary_reviewer"] == 1


class TestAgreementEvaluator:
    """Tests inter-annotator agreement metrics and quality control logic."""

    def test_evaluate_pair_agreement(self, tmp_path):
        evaluator = AgreementEvaluator(
            annotations_dir=str(tmp_path / "annotations"),
            reports_dir=str(tmp_path / "reports"),
        )

        # Create mock records
        recs_a = [
            AnnotationRecord(
                pair_id="p1::o1", osm_source_id="p1", ov_source_id="o1",
                osm_name_raw="A", ov_name_raw="A", osm_name_normalized="a", ov_name_normalized="a",
                osm_latitude=12.9, osm_longitude=77.5, ov_latitude=12.9, ov_longitude=77.5,
                distance_meters=5.0, osm_category="retail", ov_category="retail",
                category_compatibility="COMPATIBLE", blocking_strategies="s", sampling_stratum="s",
                decision=LabelDecision.MATCH, annotator_id="ann_a", confidence=ConfidenceLevel.HIGH,
                evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION, provenance=AnnotationProvenance.HUMAN_VERIFIED.value,
            ),
            AnnotationRecord(
                pair_id="p2::o2", osm_source_id="p2", ov_source_id="o2",
                osm_name_raw="B", ov_name_raw="C", osm_name_normalized="b", ov_name_normalized="c",
                osm_latitude=12.9, osm_longitude=77.5, ov_latitude=12.9, ov_longitude=77.5,
                distance_meters=15.0, osm_category="retail", ov_category="retail",
                category_compatibility="COMPATIBLE", blocking_strategies="s", sampling_stratum="s",
                decision=LabelDecision.NON_MATCH, annotator_id="ann_a", confidence=ConfidenceLevel.HIGH,
                evidence_type=EvidenceType.SAME_BUILDING_DIFFERENT_BUSINESS, provenance=AnnotationProvenance.HUMAN_VERIFIED.value,
            ),
        ]

        # Annotator B agrees on p1, disagrees on p2
        recs_b = [
            AnnotationRecord(
                pair_id="p1::o1", osm_source_id="p1", ov_source_id="o1",
                osm_name_raw="A", ov_name_raw="A", osm_name_normalized="a", ov_name_normalized="a",
                osm_latitude=12.9, osm_longitude=77.5, ov_latitude=12.9, ov_longitude=77.5,
                distance_meters=5.0, osm_category="retail", ov_category="retail",
                category_compatibility="COMPATIBLE", blocking_strategies="s", sampling_stratum="s",
                decision=LabelDecision.MATCH, annotator_id="ann_b", confidence=ConfidenceLevel.HIGH,
                evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION, provenance=AnnotationProvenance.HUMAN_VERIFIED.value,
            ),
            AnnotationRecord(
                pair_id="p2::o2", osm_source_id="p2", ov_source_id="o2",
                osm_name_raw="B", ov_name_raw="C", osm_name_normalized="b", ov_name_normalized="c",
                osm_latitude=12.9, osm_longitude=77.5, ov_latitude=12.9, ov_longitude=77.5,
                distance_meters=15.0, osm_category="retail", ov_category="retail",
                category_compatibility="COMPATIBLE", blocking_strategies="s", sampling_stratum="s",
                decision=LabelDecision.UNCERTAIN, annotator_id="ann_b", confidence=ConfidenceLevel.MEDIUM,
                evidence_type=EvidenceType.INSUFFICIENT_EVIDENCE, provenance=AnnotationProvenance.HUMAN_VERIFIED.value,
            ),
        ]

        report = evaluator.evaluate_pair_agreement(
            "ann_a", "ann_b", records_a=recs_a, records_b=recs_b
        )
        assert report["overlapping_pairs"] == 2
        assert report["agreements"] == 1
        assert report["disagreements"] == 1
        assert report["raw_agreement_pct"] == 50.0
        assert len(report["disagreed_pairs"]) == 1
        assert report["disagreed_pairs"][0]["pair_id"] == "p2::o2"

    def test_identical_annotator_raises(self, tmp_path):
        evaluator = AgreementEvaluator(
            annotations_dir=str(tmp_path / "annotations"),
            reports_dir=str(tmp_path / "reports"),
        )
        with pytest.raises(ValueError, match="identical annotator"):
            evaluator.evaluate_pair_agreement("ann_x", "ann_x")


class TestM10AuditReconciliation:
    """Verifies that Milestone 10 audit findings are correctly codified."""

    def test_canonical_uuidv5_namespace_permanence(self):
        expected_namespace = uuid.UUID("9a8bf37f-af65-5399-9fab-35bcd714c702")
        assert CANONICAL_ENTITY_NAMESPACE == expected_namespace

        # Verify deterministic generation
        uid1 = generate_canonical_uuid(["node/123"], ["ov_456"])
        uid2 = generate_canonical_uuid(["node/123"], ["ov_456"])
        assert uid1 == uid2
        assert uuid.UUID(uid1).version == 5

    def test_canonical_resolver_threshold_configurability(self):
        resolver = CanonicalEntityResolver(min_equivalence_score=0.75)
        assert resolver.min_equivalence_score == 0.75

        default_resolver = CanonicalEntityResolver()
        assert default_resolver.min_equivalence_score == 0.70


class TestHumanBenchmarkArtifacts:
    """Verifies the integrity of generated benchmark dataset and summary reports."""

    def test_benchmark_dataset_integrity(self):
        import pyarrow.parquet as pq
        csv_path = Path("data/processed/benchmark/human_verified/benchmark_human_verified_v1.csv")
        parquet_path = Path("data/processed/benchmark/human_verified/benchmark_human_verified_v1.parquet")

        assert csv_path.exists(), "Benchmark CSV artifact must exist"
        assert parquet_path.exists(), "Benchmark Parquet artifact must exist"

        table = pq.read_table(str(parquet_path))
        assert table.num_rows == 50, "Benchmark must contain exactly 50 validated pairs"

        # Check provenance
        prov_col = table.column("provenance").to_pylist()
        assert "HUMAN_VERIFIED" in prov_col
        assert "HUMAN_ADJUDICATED" in prov_col
        assert len(prov_col) == 50

    def test_inter_annotator_agreement_report(self):
        report_path = Path("reports/inter_annotator_agreement.json")
        assert report_path.exists()

        with open(report_path) as f:
            data = json.load(f)

        assert data["overlapping_pairs"] == 20
        assert data["raw_agreement_pct"] == 85.0
        assert data["cohens_kappa"] >= 0.70
        assert data["disagreements"] == 3

    def test_adjudication_summary_report(self):
        report_path = Path("reports/adjudication_summary.json")
        assert report_path.exists()

        with open(report_path) as f:
            data = json.load(f)

        assert data["metadata"]["total_cases_adjudicated"] == 3
        assert data["metadata"]["provenance_standard"] == "HUMAN_ADJUDICATED"
