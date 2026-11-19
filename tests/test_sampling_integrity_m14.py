"""Unit and integration test suite for Milestone 14:
Sampling Integrity Repair, Independent Baseline Validation, and Leakage-Safe Evaluation Design.
"""

import csv
import json
import pytest
from pathlib import Path

from src.poi_conflation.benchmark.sampling import (
    MUTUALLY_EXCLUSIVE_STRATA_ORDER,
    TARGET_PER_STRATUM,
)
from src.poi_conflation.matching.engine import ExplainableMatchingEngine
from src.poi_conflation.matching.engine_v2 import ExplainableMatchingEngineV2


class TestSamplingIntegrityAuditM14:
    """Tests for Phase 1: Population reconciliation, exhaustiveness, mutual exclusivity, and weights."""

    def test_population_reconciliation_exact_sum(self):
        audit_file = Path("reports/sampling_integrity_audit_m14.json")
        assert audit_file.exists(), "Sampling integrity audit report must exist"

        with open(audit_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        recon = data["population_reconciliation"]
        assert recon["total_candidate_pairs"] == 605428
        assert recon["distinct_candidate_pair_ids"] == 605428
        assert recon["total_stratified_sum"] == 605428
        assert recon["unassigned_candidate_count"] == 0
        assert recon["is_exhaustive"] is True
        assert recon["is_mutually_exclusive"] is True
        assert recon["cross_strata_duplicates_count"] == 0

    def test_strata_weights_and_inclusion_probabilities(self):
        audit_file = Path("reports/sampling_integrity_audit_m14.json")
        with open(audit_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        strata = data["verified_strata_breakdown"]
        assert len(strata) == 10

        running_sum = 0
        for s_name in MUTUALLY_EXCLUSIVE_STRATA_ORDER:
            assert s_name in strata, f"Missing stratum: {s_name}"
            s_info = strata[s_name]
            pop = s_info["population_size"]
            sample = s_info["sample_size"]
            assert sample == TARGET_PER_STRATUM

            # Check inclusion probability and Horvitz-Thompson weight
            expected_prob = round(sample / pop, 6)
            expected_weight = round(pop / sample, 2)
            assert s_info["inclusion_probability"] == expected_prob
            assert s_info["sampling_weight"] == expected_weight
            assert s_info["is_mutually_exclusive"] is True
            running_sum += pop

        assert running_sum == 605428, "Strata populations must sum to exactly 605,428"


class TestRepresentativeQueueIntegrityM14:
    """Tests for Phase 2: Representative queue preservation, provenance isolation, and remaining counts."""

    def test_representative_queue_preservation_and_dedup(self):
        queue_csv = Path("data/processed/benchmark/annotation_queue.csv")
        assert queue_csv.exists(), "Annotation queue CSV must exist"

        with open(queue_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 500
        pids = [r["pair_id"] for r in rows]
        assert len(set(pids)) == 500, "500-pair queue must contain zero duplicate pair IDs"

        # Check stratum allocation: exactly 50 per stratum
        stratum_counts = {}
        for r in rows:
            st = r["sampling_stratum"]
            stratum_counts[st] = stratum_counts.get(st, 0) + 1

        for s_name in MUTUALLY_EXCLUSIVE_STRATA_ORDER:
            assert stratum_counts.get(s_name) == 50

    def test_provenance_isolation_and_remaining_reviews(self):
        status_file = Path("reports/representative_annotation_status_m14.json")
        assert status_file.exists(), "Annotation status report must exist"

        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        inv = data["inventory_summary"]
        assert inv["total_sampled_pairs"] == 500
        assert inv["human_verified_pairs_count"] == 1
        assert inv["ai_adopted_diagnostic_pairs_count"] == 49
        assert inv["unannotated_pending_pairs_count"] == 450
        assert inv["remaining_genuine_human_reviews_required"] == 499


class TestSecondReviewQCM14:
    """Tests for Phase 3: Independent second review queue and agreement limitations."""

    def test_qc_queue_zero_unsubmitted_agreement_blocked(self):
        qc_file = Path("reports/second_review_qc_audit_m14.json")
        assert qc_file.exists(), "QC audit report must exist"

        with open(qc_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        qc_a = data["dataset_a_representative_qc_queue_status"]
        assert qc_a["target_qc_sample_size"] == 100
        assert qc_a["completed_submissions_count"] == 0
        assert qc_a["agreement_status"] == "BLOCKED_PENDING_SECOND_REVIEW_SUBMISSIONS"

        # Dataset C agreement and CI
        qc_c = data["dataset_c_empirical_qc_analysis"]
        assert qc_c["sample_size_n"] == 20
        assert qc_c["observed_agreement_po"] == 85.0
        assert qc_c["cohens_kappa"] == 0.7000
        assert qc_c["standard_error_se_kappa"] > 0.0
        assert len(qc_c["confidence_interval_95pct"]) == 2


class TestBaselineEvaluationIntegrityM14:
    """Tests for Phase 4: Baseline evaluation integrity and in-sample leakage reclassification."""

    def test_v2_reclassification_as_development_diagnostics(self):
        eval_file = Path("reports/baseline_evaluation_integrity_m14.json")
        assert eval_file.exists(), "Evaluation integrity report must exist"

        with open(eval_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        leak = data["development_set_leakage_investigation"]
        assert leak["in_sample_leakage_confirmed"] is True
        assert len(leak["diagnostic_pairs_used_in_v2_design"]) == 4
        assert len(leak["diagnostic_pairs_present_in_evaluation_benchmark"]) == 4

        # V1 must be frozen; V2 must be experimental
        models = data["baseline_models_lifecycle_status"]
        assert models["explainable_rule_baseline_v1"]["status"] == "PERMANENTLY_FROZEN"
        assert models["explainable_rule_baseline_v2"]["status"] == "EXPERIMENTAL_CANDIDATE"
        assert models["explainable_rule_baseline_v2"]["evaluation_status"] == "DEVELOPMENT_SET_DIAGNOSTIC_ONLY"


class TestLeakageSafeSplitDesignM14:
    """Tests for Phase 5: Leakage-safe split and category trade-offs."""

    def test_component_blocked_partitions_zero_leakage(self):
        split_file = Path("reports/leakage_safe_split_design_m14.json")
        assert split_file.exists(), "Leakage safe split design report must exist"

        with open(split_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        leak = data["leakage_audit_and_isolation_guarantee"]
        assert leak["shared_osm_nodes"]["leakage_free"] is True
        assert leak["shared_overture_nodes"]["leakage_free"] is True

        parts = data["partition_sizes_and_shares"]
        assert parts["test_partition"]["pair_count"] == 68
        assert parts["test_partition"]["status"] == "STRICTLY_FROZEN_UNTOUCHED"


class TestBenchmarkReadinessGateM14:
    """Tests for Phase 6: Benchmark readiness gate verdict."""

    def test_formal_readiness_verdict_blocked(self):
        readiness_file = Path("reports/benchmark_readiness_assessment_m14.json")
        assert readiness_file.exists(), "Readiness assessment report must exist"

        with open(readiness_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        decision = data["formal_decision"]
        assert decision["verdict"] == "NOT_READY_FOR_SUPERVISED_TRAINING"
        assert decision["secondary_status"] == "CONDITIONALLY_READY_FOR_RULE_BASELINES_ONLY"
        assert decision["criteria_unmet_or_pending"] > 0
