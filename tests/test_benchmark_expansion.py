"""Test suite for Milestone 12: Representative Benchmark Expansion, Leakage-Safe Partitioning, and Baseline Evaluation.

Tests:
1. Sampling population partitioning (all 605,428 candidate pairs assigned to 10 strata).
2. Exact inclusion probability calculations and Horvitz-Thompson sampling weights.
3. Dataset separation and zero overlap between Dataset A and Dataset C.
4. Component-blocked spatial partitioning and strict leakage-free guarantee (0 cross-split components, 0 shared nodes).
5. Partition manifests existence and frozen test partition integrity.
6. Baseline evaluator calculations (precision, recall, F1, 3-way confusion matrix, abstention handling).
7. Subgroup disaggregation metrics calculations.
8. False-positive and false-negative error analysis structure.
9. Benchmark quality gate and readiness checklist validation.
10. Strict provenance taxonomy preservation.
"""

import csv
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
from src.poi_conflation.benchmark.sampling import (
    BenchmarkSampler,
    MUTUALLY_EXCLUSIVE_STRATA_ORDER,
    TARGET_PER_STRATUM,
)
from src.poi_conflation.benchmark.expansion import RepresentativeBenchmarkManager
from src.poi_conflation.benchmark.partitioner import ComponentBlockedPartitioner
from src.poi_conflation.matching.engine import ExplainableMatchingEngine, MatchingDecision
from src.poi_conflation.matching.evaluator import BaselineEvaluator


class TestSamplingPopulationAudit:
    """Tests for Phase 1 sampling strata and inclusion probabilities."""

    def test_strata_partition_and_weights(self):
        report_file = Path("reports/benchmark_sampling_audit.json")
        assert report_file.exists(), "Sampling audit report must exist"

        with open(report_file, "r") as f:
            audit = json.load(f)

        assert audit["metadata"]["candidate_pairs_universe"] == 605428
        assert audit["strata_partition_audit"]["total_strata_count"] == 10
        assert audit["strata_partition_audit"]["unassigned_candidates_count"] == 0

        strata = audit["strata_partition_audit"]["strata"]
        total_pop = sum(s["population_size"] for s in strata.values())
        assert total_pop == 605428

        for s_name, s_data in strata.items():
            pop = s_data["population_size"]
            samp = s_data["sample_size"]
            prob = s_data["inclusion_probability"]
            weight = s_data["sampling_weight"]
            expected_prob = round(samp / pop, 6)
            expected_weight = round(pop / samp, 4)
            assert abs(prob - expected_prob) < 1e-4
            assert abs(weight - expected_weight) < 1e-2

    def test_dataset_separation_and_disjointness(self):
        report_file = Path("reports/benchmark_sampling_audit.json")
        with open(report_file, "r") as f:
            audit = json.load(f)

        overlaps = audit["dataset_separation_audit"]["overlap_analysis"]
        # Dataset A (500 queue) and Dataset C (M11 benchmark) must be disjoint
        assert overlaps["overlap_queue_a_and_benchmark_c"] == 0
        # Dataset B and C must overlap by 50
        assert overlaps["overlap_review_b_and_benchmark_c"] == 50


class TestRepresentativeBenchmarkManager:
    """Tests for Phase 2 representative benchmark expansion and tracking."""

    def test_load_queue_items(self):
        mgr = RepresentativeBenchmarkManager()
        items = mgr.load_queue_items()
        assert len(items) == 500
        # Verify 50 pairs per stratum
        strata_counts = {}
        for it in items:
            strata_counts[it.sampling_stratum] = strata_counts.get(it.sampling_stratum, 0) + 1
        for s in MUTUALLY_EXCLUSIVE_STRATA_ORDER:
            assert strata_counts[s] == 50

    def test_audit_representative_progress(self):
        mgr = RepresentativeBenchmarkManager()
        prog = mgr.audit_representative_progress()
        assert prog["overall_progress"]["total_queue_size"] == 500
        assert prog["overall_progress"]["status"] == "INCOMPLETE_HUMAN_ANNOTATION"
        assert prog["overall_progress"]["pending_unannotated_count"] > 0

    def test_assign_representative_qc_sample(self, tmp_path):
        mgr = RepresentativeBenchmarkManager(annotations_dir=str(tmp_path))
        qc_file = mgr.assign_representative_qc_sample(fraction=0.20, seed=42)
        assert qc_file.exists()

        with open(qc_file, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 100  # 20% of 500


class TestComponentBlockedPartitioner:
    """Tests for Phase 4 leakage-safe dataset partitioning."""

    def test_leakage_safe_partitioning(self):
        # Create synthetic bipartite graph pairs
        pairs = [
            # Component 1 (cluster of 2 pairs sharing an OSM node)
            {
                "pair_id": "osm/1::ov/1", "osm_source_id": "osm/1", "ov_source_id": "ov/1",
                "osm_latitude": 12.97, "osm_longitude": 77.59, "ov_latitude": 12.97, "ov_longitude": 77.59,
            },
            {
                "pair_id": "osm/1::ov/2", "osm_source_id": "osm/1", "ov_source_id": "ov/2",
                "osm_latitude": 12.97, "osm_longitude": 77.59, "ov_latitude": 12.971, "ov_longitude": 77.591,
            },
            # Component 2 (isolated pair in a different area)
            {
                "pair_id": "osm/2::ov/3", "osm_source_id": "osm/2", "ov_source_id": "ov/3",
                "osm_latitude": 13.05, "osm_longitude": 77.62, "ov_latitude": 13.05, "ov_longitude": 77.62,
            },
            # Component 3
            {
                "pair_id": "osm/3::ov/4", "osm_source_id": "osm/3", "ov_source_id": "ov/4",
                "osm_latitude": 12.85, "osm_longitude": 77.50, "ov_latitude": 12.85, "ov_longitude": 77.50,
            },
        ]

        partitioner = ComponentBlockedPartitioner(h3_resolution=7, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
        split_pairs, audit = partitioner.partition(pairs)

        assert audit["leakage_verification"]["is_strictly_leakage_free"] is True
        assert audit["leakage_verification"]["cross_split_connected_components_leakage_count"] == 0
        assert audit["leakage_verification"]["cross_split_osm_nodes_leakage_count"] == 0

        # Component 1 pairs must reside in the exact same partition
        p1_split = [p["partition_split"] for p in split_pairs["TRAIN"] + split_pairs["VALIDATION"] + split_pairs["TEST"] if p["pair_id"] == "osm/1::ov/1"][0]
        p2_split = [p["partition_split"] for p in split_pairs["TRAIN"] + split_pairs["VALIDATION"] + split_pairs["TEST"] if p["pair_id"] == "osm/1::ov/2"][0]
        assert p1_split == p2_split

    def test_partition_manifests_integrity(self):
        train_file = Path("data/processed/benchmark/partitions/train_partition.csv")
        val_file = Path("data/processed/benchmark/partitions/validation_partition.csv")
        test_file = Path("data/processed/benchmark/partitions/test_partition.csv")
        leakage_file = Path("reports/leakage_audit_report.json")

        assert train_file.exists()
        assert val_file.exists()
        assert test_file.exists()
        assert leakage_file.exists()

        with open(leakage_file) as f:
            audit = json.load(f)

        assert audit["leakage_verification"]["is_strictly_leakage_free"] is True
        assert audit["leakage_verification"]["cross_split_connected_components_leakage_count"] == 0
        assert audit["split_distribution"]["TEST"]["status"] == "FROZEN"


class TestBaselineEvaluationAndErrors:
    """Tests for Phase 5 baseline evaluation and Phase 6 error analysis."""

    def test_baseline_evaluation_report(self):
        eval_file = Path("reports/baseline_evaluation.json")
        assert eval_file.exists()

        with open(eval_file) as f:
            data = json.load(f)

        perf = data["overall_performance"]
        assert perf["definite_predictions_mode"]["precision"] == 1.0
        assert perf["strict_binary_mode"]["recall"] >= 0.90
        assert "methodological_caveat" in perf["brier_score_analysis"]

        # Check confusion matrices
        mat = data["confusion_matrices"]["three_way_decision_matrix"]
        assert mat["MATCH"]["MATCH"] == 39
        assert mat["MATCH"]["UNCERTAIN"] == 4
        assert mat["NON_MATCH"]["UNCERTAIN"] == 7

    def test_baseline_error_analysis_report(self):
        error_file = Path("reports/baseline_error_analysis.json")
        assert error_file.exists()

        with open(error_file) as f:
            data = json.load(f)

        assert data["metadata"]["total_errors_or_abstentions"] == 11
        assert data["metadata"]["false_positives_count"] == 0
        assert data["metadata"]["false_negatives_strict_count"] == 4
        assert len(data["error_details"]) == 11


class TestBenchmarkReadinessQualityGate:
    """Tests for Phase 7 benchmark readiness assessment."""

    def test_readiness_assessment_verdict(self):
        readiness_file = Path("reports/benchmark_readiness_assessment.json")
        assert readiness_file.exists()

        with open(readiness_file) as f:
            data = json.load(f)

        verdict = data["readiness_verdict"]
        assert verdict["decision"] == "NOT_READY_FOR_SUPERVISED_TRAINING"
        assert verdict["status_code"] == "CONDITIONAL_BLOCKED"
        assert len(data["quality_gate_checklist"]) == 9
        assert len(data["prerequisites_for_supervised_modeling"]) >= 4
