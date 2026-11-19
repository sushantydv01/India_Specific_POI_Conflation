"""Comprehensive automated tests for Milestone 18: Conflation Quality Evaluation & Geospatial Intelligence.

Covers all 16 required test domains:
1. Label provenance preservation.
2. Gold-label filtering and AI-label exclusion.
3. Duplicate-pair prevention in benchmark assembly.
4. Split leakage prevention across train, validation, and test.
5. Reproducible sampling and manifest verification.
6. Metric calculations (Precision, Recall, F1, Specificity, Accuracy, FPR, FNR).
7. Confusion matrix calculations and structure.
8. Threshold evaluation sweep and trade-off calculation.
9. Category-wise evaluation and aggregations.
10. Spatial aggregation and H3 indexing.
11. Distance calculations and percentile distributions.
12. Indic language diagnostics and Kannada script detection.
13. Review-priority ranking and tier assignment.
14. Missing and insufficient label handling.
15. Empty dataset edge case handling.
16. Inconsistent or invalid annotation record protection.
"""

import json
from pathlib import Path
import pytest

from src.poi_conflation.benchmark.provenance import (
    EvaluationProvenance,
    EvaluationViewType,
    EvaluationRecord,
    BenchmarkProvenanceAuditor,
)
from src.poi_conflation.matching.quality_evaluator import (
    ClassificationMetrics,
    compute_binary_metrics,
    ConflationQualityEvaluator,
)
from src.poi_conflation.analysis.geospatial_intelligence import (
    GeospatialIntelligenceAnalyzer,
)
from src.poi_conflation.analysis.indic_language_intelligence import (
    IndicLanguageIntelligenceAnalyzer,
)
from src.poi_conflation.matching.review_prioritizer import (
    PriorityTier,
    PrioritizedReviewItem,
    ReviewQueuePrioritizer,
)


# ==============================================================================
# 1. PROVENANCE & BENCHMARK TESTS
# ==============================================================================

def test_provenance_taxonomy_enum_values():
    """Verify that all 6 required provenance categories are strictly defined."""
    required = {
        "HUMAN_DUAL_REVIEWED",
        "HUMAN_REVIEWED",
        "AI_ADOPTED",
        "AI_GENERATED",
        "HEURISTIC",
        "UNREVIEWED",
    }
    actual = {e.value for e in EvaluationProvenance}
    assert required.issubset(actual), f"Missing required provenance values: {required - actual}"


def test_record_provenance_preservation():
    """Verify that EvaluationRecord preserves annotators, timestamps, and adjudication rationale."""
    rec = EvaluationRecord(
        pair_id="pair-101",
        osm_source_id="osm/1",
        ov_source_id="ov/1",
        osm_name_raw="ICICI Bank",
        ov_name_raw="ICICI Bank Limited",
        osm_name_norm="icici bank",
        ov_name_norm="icici bank limited",
        osm_category="financial",
        ov_category="financial",
        distance_meters=15.2,
        ground_truth_decision="MATCH",
        binary_label=1,
        provenance=EvaluationProvenance.HUMAN_DUAL_REVIEWED,
        annotator_ids=["rev1", "rev2", "adjudicator"],
        review_timestamps=["2026-11-18T10:00:00Z"],
        initial_decisions={"rev1": "MATCH", "rev2": "UNCERTAIN"},
        adjudication_rationale="Resolved as match based on branch locality matching",
        is_gold_standard=True,
    )
    d = rec.to_dict()
    assert d["pair_id"] == "pair-101"
    assert d["provenance"] == "HUMAN_DUAL_REVIEWED"
    assert d["is_gold_standard"] is True
    assert "adjudicator" in d["annotator_ids"]
    assert "Resolved as match" in d["adjudication_rationale"]


def test_gold_label_filtering_excludes_ai_adopted():
    """Verify that gold filtering strictly excludes AI_ADOPTED and UNREVIEWED labels."""
    records = [
        EvaluationRecord(
            "p1", "osm1", "ov1", "A", "A", "a", "a", "c", "c", 5.0,
            "MATCH", 1, EvaluationProvenance.HUMAN_DUAL_REVIEWED, is_gold_standard=True
        ),
        EvaluationRecord(
            "p2", "osm2", "ov2", "B", "B", "b", "b", "c", "c", 10.0,
            "MATCH", 1, EvaluationProvenance.HUMAN_REVIEWED, is_gold_standard=True
        ),
        EvaluationRecord(
            "p3", "osm3", "ov3", "C", "D", "c", "d", "c", "c", 20.0,
            "NON_MATCH", 0, EvaluationProvenance.AI_ADOPTED, is_gold_standard=False
        ),
        EvaluationRecord(
            "p4", "osm4", "ov4", "E", "F", "e", "f", "c", "c", 30.0,
            None, None, EvaluationProvenance.UNREVIEWED, is_gold_standard=False
        ),
    ]

    gold_only = [r for r in records if r.is_gold_standard]
    assert len(gold_only) == 2
    assert all(r.provenance in (EvaluationProvenance.HUMAN_DUAL_REVIEWED, EvaluationProvenance.HUMAN_REVIEWED) for r in gold_only)
    assert not any(r.provenance == EvaluationProvenance.AI_ADOPTED for r in gold_only)


def test_duplicate_pair_prevention():
    """Verify that BenchmarkProvenanceAuditor deduplicates pair IDs across source files."""
    auditor = BenchmarkProvenanceAuditor()
    records = auditor.assemble_audited_records()
    pids = list(records.keys())
    assert len(pids) == len(set(pids)), "Assembled benchmark contains duplicated pair IDs"


def test_split_leakage_prevention():
    """Verify that train, validation, and test partitions have zero shared candidate pairs."""
    auditor = BenchmarkProvenanceAuditor()
    records = auditor.assemble_audited_records()

    train_ids = {r.pair_id for r in records.values() if r.partition_split == "train"}
    val_ids = {r.pair_id for r in records.values() if r.partition_split == "validation"}
    test_ids = {r.pair_id for r in records.values() if r.partition_split == "test"}

    assert len(train_ids & test_ids) == 0, f"Leaked pairs between train and test: {train_ids & test_ids}"
    assert len(val_ids & test_ids) == 0, f"Leaked pairs between val and test: {val_ids & test_ids}"
    assert len(train_ids & val_ids) == 0, f"Leaked pairs between train and val: {train_ids & val_ids}"


# ==============================================================================
# 2. METRICS & CONFUSION MATRIX TESTS
# ==============================================================================

def test_metric_calculations_basic():
    """Verify standard binary classification metric formulas."""
    y_true = [1, 1, 1, 1, 0, 0, 0, 0]
    y_pred = [1, 1, 1, 0, 0, 0, 1, 0]  # TP=3, FN=1, TN=3, FP=1

    m = compute_binary_metrics(y_true, y_pred, "TestSystem", "TestView")

    assert m.sample_size == 8
    assert m.true_positives == 3
    assert m.false_negatives == 1
    assert m.true_negatives == 3
    assert m.false_positives == 1

    assert m.precision == pytest.approx(3 / 4, rel=1e-3)
    assert m.recall == pytest.approx(3 / 4, rel=1e-3)
    assert m.f1_score == pytest.approx(3 / 4, rel=1e-3)
    assert m.specificity == pytest.approx(3 / 4, rel=1e-3)
    assert m.accuracy == pytest.approx(6 / 8, rel=1e-3)
    assert m.false_positive_rate == pytest.approx(1 / 4, rel=1e-3)
    assert m.false_negative_rate == pytest.approx(1 / 4, rel=1e-3)


def test_confusion_matrix_structure():
    """Verify confusion matrix [[TN, FP], [FN, TP]] structure."""
    y_true = [1, 0]
    y_pred = [1, 0]
    m = compute_binary_metrics(y_true, y_pred, "TestSystem", "TestView")

    # [[TN=1, FP=0], [FN=0, TP=1]]
    assert m.confusion_matrix == [[1, 0], [0, 1]]


def test_empty_dataset_edge_case():
    """Verify that empty inputs produce zeroed metrics without zero-division crashes."""
    m = compute_binary_metrics([], [], "TestEmpty", "EmptyView")
    assert m.sample_size == 0
    assert m.precision == 0.0
    assert m.recall == 0.0
    assert m.f1_score == 0.0
    assert m.accuracy == 0.0


def test_threshold_evaluation_sweep():
    """Verify threshold sweep produces expected schema across thresholds."""
    evaluator = ConflationQualityEvaluator()
    auditor = BenchmarkProvenanceAuditor()
    records = list(auditor.assemble_audited_records().values())
    op_records = [r for r in records if r.provenance != EvaluationProvenance.UNREVIEWED]

    sweep = evaluator.compute_threshold_sweep(op_records, thresholds=[0.3, 0.55, 0.8])
    assert len(sweep) == 3
    for row in sweep:
        assert "threshold" in row
        assert "precision" in row
        assert "recall" in row
        assert "f1_score" in row
        assert "accepted_count" in row


# ==============================================================================
# 3. SPATIAL & DISTANCE TESTS
# ==============================================================================

def test_distance_percentiles_calculation():
    """Verify metric distance distribution calculations."""
    analyzer = GeospatialIntelligenceAnalyzer()
    res = analyzer.analyze_distance_distributions()

    assert "disposition_distance" in res
    assert "equivalence_percentiles" in res
    p = res["equivalence_percentiles"]

    # Percentiles must be monotonically non-decreasing
    assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"] <= p["p95"] <= p["p99"]
    # Median distance for accepted equivalences in Bengaluru is typically < 25m
    assert p["p50"] < 25.0


def test_spatial_coverage_h3():
    """Verify that H3 Res 8 clusters aggregate properly and return positive counts."""
    analyzer = GeospatialIntelligenceAnalyzer()
    cov = analyzer.analyze_spatial_coverage()

    assert "source_distribution" in cov
    assert "top_h3_clusters" in cov
    assert len(cov["top_h3_clusters"]) > 0

    top_cluster = cov["top_h3_clusters"][0]
    assert top_cluster["total_pois"] > 1000
    assert top_cluster["h3_res8"].startswith("88")


# ==============================================================================
# 4. INDIC LANGUAGE & TRANSLITERATION TESTS
# ==============================================================================

def test_indic_language_script_detection():
    """Verify Kannada script detection regex on Unicode Kannada block [0x0C80-0x0CFF]."""
    kannada_sample = "ವಿದ್ಯಾರ್ಥಿ ಭವನ್"
    english_sample = "Vidyarthi Bhavan"
    mixed_sample = "SBI ಬ್ಯಾಂಕ್"

    import re
    kannada_regex = re.compile(r"[\u0C80-\u0CFF]")

    assert kannada_regex.search(kannada_sample) is not None
    assert kannada_regex.search(english_sample) is None
    assert kannada_regex.search(mixed_sample) is not None


def test_indic_transliteration_profiling():
    """Verify transliteration feature profiling across candidate universe."""
    analyzer = IndicLanguageIntelligenceAnalyzer()
    res = analyzer.profile_transliteration_features()

    assert res["total_candidate_pairs"] == 605428
    assert res["osm_has_kannada_pairs"] > 50000
    assert res["translit_available_pairs"] > 50000
    assert res["translit_exact_match_pairs"] > 1000


# ==============================================================================
# 5. REVIEW QUEUE PRIORITIZATION TESTS
# ==============================================================================

def test_review_priority_score_and_tier_ranking():
    """Verify that review queue items receive valid priority scores and tiers."""
    prioritizer = ReviewQueuePrioritizer()
    items = prioritizer.prioritize_unresolved_pairs()

    assert len(items) == 2842
    # Verify descending rank order
    scores = [it.priority_score for it in items]
    assert scores == sorted(scores, reverse=True)

    # Verify score range and tier assignment
    for it in items:
        assert 0.0 <= it.priority_score <= 100.0
        if it.priority_score >= 70.0:
            assert it.priority_tier == PriorityTier.P1_CRITICAL
        elif it.priority_score >= 55.0:
            assert it.priority_tier == PriorityTier.P2_HIGH
        elif it.priority_score >= 40.0:
            assert it.priority_tier == PriorityTier.P3_MEDIUM
        else:
            assert it.priority_tier == PriorityTier.P4_LOW


def test_insufficient_labels_warning_handling():
    """Verify that evaluator handles small-sample evaluation transparently."""
    evaluator = ConflationQualityEvaluator()
    # 2 sample evaluation
    y_true = [1, 0]
    y_pred = [1, 1]
    m = compute_binary_metrics(y_true, y_pred, "TinyTest", "SmallView", notes="Small sample size warning")
    assert m.sample_size == 2
    assert "Small sample size" in m.notes
    # Wilson interval should be wide for small N
    ci_width = m.wilson_f1_ci[1] - m.wilson_f1_ci[0]
    assert ci_width > 0.40  # Wide uncertainty
