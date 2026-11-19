"""Unit and integration test suite for Milestone 13:
Human Benchmark Completion, Evaluator Audit, and Rule-Based Matching Optimization.
"""

import csv
import json
import pytest
from pathlib import Path

from src.poi_conflation.matching.engine import ExplainableMatchingEngine, MatchingDecision
from src.poi_conflation.matching.engine_v2 import ExplainableMatchingEngineV2
from src.poi_conflation.matching.normalization import EnhancedNameNormalizer
from src.poi_conflation.matching.evaluator import (
    BaselineEvaluator,
    compute_pr_curve_and_auc,
    compute_roc_auc,
)


class TestProvenanceReconciliation:
    """Tests for Phase 1 benchmark accounting and provenance reconciliation."""

    def test_reconciliation_report_exists_and_verified(self):
        report_path = Path("reports/representative_benchmark_reconciliation.json")
        assert report_path.exists(), "Reconciliation report must exist"

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data["executive_summary"]
        assert summary["actual_composition"]["dataset_a_representative_sample_human_verified"] == 1
        assert summary["actual_composition"]["dataset_c_targeted_ambiguity_gold_standard_human_verified"] == 50
        assert summary["actual_composition"]["total_distinct_human_verified_pairs_in_repo"] == 51

        # Confirm zero overlap between Dataset A and Dataset C
        assert summary["zero_overlap_confirmation"]["overlap_pair_count"] == 0
        assert summary["zero_overlap_confirmation"]["overlap_percentage"] == 0.0

        # Confirm AI provenance isolation
        assert summary["ai_provenance_isolation"]["ai_pairs_in_human_gold_benchmark"] == 0

    def test_true_representative_completion_accounting(self):
        comp_path = Path("reports/representative_benchmark_completion.json")
        assert comp_path.exists(), "Representative completion report must exist"

        with open(comp_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        status = data["actual_completion_status"]
        assert status["total_representative_sample"] == 500
        assert status["human_verified_count"] == 1
        assert status["ai_adopted_diagnostic_count"] == 49
        assert status["pending_unannotated_count"] == 450
        assert status["remaining_human_reviews_required"] == 499
        assert status["readiness_verdict"] == "NOT_READY_FOR_SUPERVISED_TRAINING"


class TestDualReviewQCStatus:
    """Tests for Phase 3 blind dual-review QC queue and agreement status."""

    def test_qc_queue_assignment_and_pending_status(self):
        iaa_path = Path("reports/inter_annotator_agreement_final.json")
        assert iaa_path.exists(), "Final IAA report must exist"

        with open(iaa_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Dataset C agreement
        c_data = data["dataset_c_empirical_agreement"]
        assert c_data["dual_review_overlap_count"] == 20
        assert c_data["exact_percent_agreement"] == 85.0
        assert c_data["cohens_kappa"] == 0.7000
        assert c_data["krippendorffs_alpha_nominal"] == 0.6931

        # Dataset A QC queue status
        a_data = data["dataset_a_representative_qc_queue_status"]
        assert a_data["target_qc_overlap_pairs"] == 100
        assert a_data["second_review_submissions_completed"] == 0
        assert a_data["agreement_computation_status"] == "PENDING_HUMAN_SUBMISSIONS"


class TestEvaluatorAuditCalculations:
    """Tests for Phase 4 metric calculation audit and hand-calculated known cases."""

    def test_compute_roc_auc_known_cases(self):
        # Perfect separation
        assert compute_roc_auc([0.9, 0.8, 0.3, 0.1], [1, 1, 0, 0]) == 1.0

        # Total inversion
        assert compute_roc_auc([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0

        # Partial inversion: pos [0.8, 0.4], neg [0.6, 0.2] -> 3/4 = 0.75
        assert compute_roc_auc([0.8, 0.4, 0.6, 0.2], [1, 1, 0, 0]) == 0.75

        # Empty handling
        assert compute_roc_auc([], []) == 0.5

    def test_compute_pr_curve_and_auc_anchoring(self):
        # Perfect scores: PR-AUC must be 1.0
        _, pr_auc_perfect = compute_pr_curve_and_auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0])
        assert pr_auc_perfect == 1.0

        # Anchor check: boundary threshold higher than max score must have recall=0.0, precision=1.0
        points, _ = compute_pr_curve_and_auc([0.8, 0.4, 0.6, 0.2], [1, 1, 0, 0])
        assert points[0]["recall"] == 0.0
        assert points[0]["precision"] == 1.0

    def test_evaluator_audit_report(self):
        audit_path = Path("reports/baseline_evaluator_audit.json")
        assert audit_path.exists(), "Evaluator audit report must exist"

        with open(audit_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        checks = data["audit_checklist_a_through_j"]
        assert checks["check_a_positive_class_encoding"]["status"] == "VERIFIED_CORRECT"
        assert checks["check_b_continuous_score_direction_and_semantics"]["status"] == "VERIFIED_CORRECT"
        assert checks["check_c_abstention_handling"]["status"] == "VERIFIED_CORRECTED"
        assert checks["check_e_pr_curve_and_auc_calculation"]["status"] == "DEFECT_RESOLVED"
        assert checks["check_f_roc_auc_calculation"]["status"] == "DEFECT_RESOLVED"
        assert checks["check_g_brier_score_calibration_semantics"]["status"] == "VERIFIED_WITH_METHODOLOGICAL_CAVEAT"


class TestEnhancedNameNormalizer:
    """Tests for Phase 6 corporate, locality, and event normalizer."""

    def setup_method(self):
        self.norm = EnhancedNameNormalizer()

    def test_corporate_suffix_normalization(self):
        res1 = self.norm.normalize_and_extract("ICICI Bank Limited")
        assert res1["core_name"] == "icici bank"
        assert res1["corporate_suffix"] == "limited"

        res2 = self.norm.normalize_and_extract("Infosys Private Limited")
        assert res2["core_name"] == "infosys"
        assert res2["corporate_suffix"] == "private limited"

        res3 = self.norm.normalize_and_extract("Wipro Ltd.")
        assert res3["core_name"] == "wipro"
        assert res3["corporate_suffix"] == "ltd"

    def test_locality_qualifier_extraction(self):
        res1 = self.norm.normalize_and_extract("ICICI Bank, Bangalore-Rajarajeshwarinagar")
        assert res1["core_name"] == "icici bank"
        assert "rajarajeshwarinagar" in res1["locality_qualifier"]

        res2 = self.norm.normalize_and_extract("ICICI Bank Bangalore-Marathalli")
        assert res2["core_name"] == "icici bank"
        assert "marathalli" in res2["locality_qualifier"]

        res3 = self.norm.normalize_and_extract("Ujjivan Small Finance Bank, Bannergatta")
        assert res3["core_name"] == "ujjivan bank"
        assert "bannergatta" in res3["locality_qualifier"]

    def test_event_temporal_qualifier_extraction(self):
        res = self.norm.normalize_and_extract("Karnataka Chitrakala parishath Annual show 2017")
        assert res["core_name"] == "karnataka chitrakala parishath"
        assert res["event_qualifier"] == "annual show 2017"

    def test_atm_vs_bank_detection(self):
        res_atm = self.norm.normalize_and_extract("ICICI Bank ATM")
        assert res_atm["is_atm"] is True
        assert res_atm["is_bank"] is False

        res_bank = self.norm.normalize_and_extract("ICICI Bank")
        assert res_bank["is_atm"] is False
        assert res_bank["is_bank"] is True


class TestBaselineV2Optimization:
    """Tests for Phase 7 candidate baseline v2."""

    def setup_method(self):
        self.engine_v1 = ExplainableMatchingEngine()
        self.engine_v2 = ExplainableMatchingEngineV2()

    def test_baseline_v1_frozen_and_intact(self):
        assert self.engine_v1.weights["name"] == 0.35
        assert self.engine_v1.weights["spatial"] == 0.30
        assert self.engine_v1.thresholds["match_min_score"] == 0.75

    def test_v2_containment_boost_for_corporate_expansion(self):
        # Diagnostic pair: ICICI Bank vs ICICI Bank Limited, Bangalore-Rajarajeshwarinagar
        feat = {
            "feat_exact_name_match": 0.0,
            "feat_jaro_winkler": 0.8417,
            "feat_token_sort_ratio": 0.3448,
            "feat_token_set_ratio": 1.0,
            "feat_char_3gram_jaccard": 0.1538,
            "feat_distance_meters": 13.28,
            "feat_dist_band_le15m": 1.0,
            "feat_dist_band_le30m": 1.0,
            "feat_dist_band_le50m": 1.0,
            "feat_dist_band_le100m": 1.0,
            "feat_exact_category_match": 0.0,
            "feat_category_strongly_compat": 0.0,
            "feat_category_potentially_compat": 0.0,
            "feat_category_unknown_compat": 1.0,
            "feat_category_incompatible": 0.0,
        }
        res_v1 = self.engine_v1.evaluate_pair(feat)
        res_v2 = self.engine_v2.evaluate_pair(feat)

        assert res_v2["final_score"] > res_v1["final_score"]
        assert "NAME_SUBSET_CONTAINMENT_BOOST_LE50M" in res_v2["applied_rules"]

    def test_v2_atm_vs_bank_guardrail(self):
        feat = {
            "feat_exact_name_match": 0.0,
            "feat_jaro_winkler": 0.90,
            "feat_token_sort_ratio": 0.85,
            "feat_token_set_ratio": 1.0,
            "feat_distance_meters": 5.0,
            "feat_dist_band_le15m": 1.0,
            "feat_exact_category_match": 0.0,
            "feat_category_incompatible": 0.0,
        }
        res = self.engine_v2.evaluate_pair(
            feat,
            osm_name_raw="ICICI Bank",
            ov_name_raw="ICICI Bank ATM",
            osm_category="civic_religious",
            ov_category="atm",
        )
        assert "ATM_VS_BANK_FACILITY_DISTINCTION" in res["applied_guardrails"]
        assert res["decision"] != MatchingDecision.MATCH

    def test_v2_same_building_different_business_protection(self):
        # Collocated shop within 25m with distinct name: Pathi Market vs Prakash Colour Lab
        feat = {
            "feat_exact_name_match": 0.0,
            "feat_jaro_winkler": 0.40,
            "feat_token_sort_ratio": 0.15,
            "feat_token_set_ratio": 0.20,
            "feat_distance_meters": 22.5,
            "feat_dist_band_le15m": 0.0,
            "feat_dist_band_le30m": 1.0,
            "feat_exact_category_match": 1.0,
            "feat_category_incompatible": 0.0,
        }
        res = self.engine_v2.evaluate_pair(feat)
        assert res["decision"] == MatchingDecision.NON_MATCH
        assert "SAME_BUILDING_DIFFERENT_BUSINESS" in res["applied_guardrails"]

    def test_v2_same_brand_different_branch_protection(self):
        # Same brand at 250m: must remain NON_MATCH
        feat = {
            "feat_exact_name_match": 1.0,
            "feat_jaro_winkler": 1.0,
            "feat_token_sort_ratio": 1.0,
            "feat_token_set_ratio": 1.0,
            "feat_distance_meters": 250.0,
            "feat_dist_band_le15m": 0.0,
            "feat_dist_band_le30m": 0.0,
            "feat_dist_band_le50m": 0.0,
            "feat_dist_band_le100m": 0.0,
            "feat_exact_category_match": 1.0,
            "feat_category_incompatible": 0.0,
        }
        res = self.engine_v2.evaluate_pair(feat)
        assert res["decision"] == MatchingDecision.NON_MATCH
        assert "SAME_BRAND_DIFFERENT_BRANCH" in res["applied_guardrails"]


class TestBenchmarkQualityGateFinal:
    """Tests for Phase 8 final readiness assessment and test-set integrity."""

    def test_final_readiness_assessment(self):
        readiness_path = Path("reports/benchmark_readiness_assessment_final.json")
        assert readiness_path.exists(), "Final readiness assessment must exist"

        with open(readiness_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        formal = data["formal_decision"]
        assert formal["verdict"] == "NOT_READY_FOR_SUPERVISED_TRAINING"
        assert formal["secondary_operational_status"] == "CONDITIONALLY_READY_FOR_RULE_BASELINES_ONLY"

    def test_frozen_test_partition_integrity(self):
        test_csv = Path("data/processed/benchmark/partitions/test_partition.csv")
        assert test_csv.exists(), "Frozen test partition must exist"

        with open(test_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 68, "Test partition must have exactly 68 rows"
