"""Automated test suite for the explainable deterministic POI matching engine.

Tests:
1. MatchingConfig loading and defaults.
2. High-confidence matching pair scoring and evidence generation.
3. Guardrail: Incompatible category forces NON_MATCH and caps score.
4. Guardrail: Empty name forces UNCERTAIN.
5. Guardrail: Same brand different branch forces NON_MATCH for large separation.
6. Guardrail: Same building different business forces NON_MATCH for close low-similarity pairs.
7. Guardrail: Excessive spatial separation (> 500m) forces NON_MATCH.
8. Full report and sample explanations generation validation.
"""

from pathlib import Path
import pytest

from src.poi_conflation.matching.config import MatchingConfig
from src.poi_conflation.matching.engine import (
    ExplainableMatchingEngine,
    MatchingDecision,
)


@pytest.fixture
def engine():
    return ExplainableMatchingEngine()


def test_matching_config_defaults():
    """Verify default config parameters and weights sum to 1.0."""
    config = MatchingConfig.load()
    assert config.version == "1.0.0"
    weights = config.feature_group_weights
    total_w = sum(weights.values())
    assert pytest.approx(total_w, abs=1e-4) == 1.0
    assert config.thresholds["match_min_score"] == 0.75
    assert config.thresholds["uncertain_min_score"] == 0.40


def test_high_confidence_match(engine):
    """Verify that an exact name, strongly compatible, co-located pair produces MATCH."""
    feat = {
        "feat_exact_name_match": 1.0,
        "feat_jaro_winkler": 1.0,
        "feat_token_sort_ratio": 1.0,
        "feat_token_set_ratio": 1.0,
        "feat_char_3gram_jaccard": 1.0,
        "feat_indic_phonetic_sim": 1.0,
        "feat_translit_available": 0.0,
        "feat_distance_meters": 5.0,
        "feat_dist_band_le15m": 1.0,
        "feat_dist_band_le30m": 1.0,
        "feat_dist_band_le50m": 1.0,
        "feat_dist_band_le100m": 1.0,
        "feat_exact_category_match": 1.0,
        "feat_category_strongly_compat": 1.0,
        "feat_strat_exact_name": 1.0,
        "feat_strat_spatial_50m": 1.0,
        "feat_multi_strategy_overlap": 1.0,
    }
    res = engine.evaluate_pair(feat)
    assert res["decision"] == MatchingDecision.MATCH
    assert res["final_score"] >= 0.75
    assert len(res["positive_evidence"]) >= 3
    assert len(res["negative_evidence"]) == 0
    assert "Exact normalized name match" in res["positive_evidence"]


def test_guardrail_incompatible_category(engine):
    """Verify that incompatible categories override high name similarity and force NON_MATCH."""
    feat = {
        "feat_exact_name_match": 1.0,
        "feat_jaro_winkler": 1.0,
        "feat_token_sort_ratio": 1.0,
        "feat_token_set_ratio": 1.0,
        "feat_char_3gram_jaccard": 1.0,
        "feat_indic_phonetic_sim": 1.0,
        "feat_distance_meters": 10.0,
        "feat_dist_band_le15m": 1.0,
        "feat_dist_band_le30m": 1.0,
        "feat_dist_band_le50m": 1.0,
        "feat_dist_band_le100m": 1.0,
        "feat_category_incompatible": 1.0,  # Hospital vs Restaurant
    }
    res = engine.evaluate_pair(feat)
    assert res["decision"] == MatchingDecision.NON_MATCH
    assert res["final_score"] <= 0.35
    assert "CATEGORY_DISJOINT" in res["applied_guardrails"]
    assert "Disjoint incompatible categories" in res["negative_evidence"]


def test_guardrail_same_brand_different_branch(engine):
    """Verify that exact name match at large urban separation forces NON_MATCH."""
    feat = {
        "feat_exact_name_match": 1.0,
        "feat_jaro_winkler": 1.0,
        "feat_token_sort_ratio": 1.0,
        "feat_token_set_ratio": 1.0,
        "feat_indic_phonetic_sim": 1.0,
        "feat_exact_category_match": 1.0,
        "feat_category_strongly_compat": 1.0,
        "feat_distance_meters": 1500.0,  # 1.5 km away (e.g. Apollo Pharmacy)
        "feat_dist_band_le100m": 0.0,
    }
    res = engine.evaluate_pair(feat)
    assert res["decision"] == MatchingDecision.NON_MATCH
    assert res["final_score"] <= 0.35
    assert "SAME_BRAND_DIFFERENT_BRANCH" in res["applied_guardrails"]


def test_guardrail_same_building_different_business(engine):
    """Verify that close distance (<25m) with distinct names forces NON_MATCH."""
    feat = {
        "feat_exact_name_match": 0.0,
        "feat_jaro_winkler": 0.30,
        "feat_token_sort_ratio": 0.15,
        "feat_token_set_ratio": 0.15,
        "feat_distance_meters": 8.0,  # 8m away in same complex
        "feat_dist_band_le15m": 1.0,
        "feat_dist_band_le30m": 1.0,
        "feat_dist_band_le50m": 1.0,
        "feat_dist_band_le100m": 1.0,
        "feat_category_strongly_compat": 1.0,
    }
    res = engine.evaluate_pair(feat)
    assert res["decision"] == MatchingDecision.NON_MATCH
    assert res["final_score"] <= 0.35
    assert "SAME_BUILDING_DIFFERENT_BUSINESS" in res["applied_guardrails"]


def test_guardrail_empty_name(engine):
    """Verify that empty name cannot produce MATCH and is capped at UNCERTAIN."""
    feat = {
        "feat_is_empty_name": 1.0,
        "feat_distance_meters": 5.0,
        "feat_dist_band_le15m": 1.0,
        "feat_dist_band_le30m": 1.0,
        "feat_dist_band_le50m": 1.0,
        "feat_dist_band_le100m": 1.0,
        "feat_exact_category_match": 1.0,
        "feat_category_strongly_compat": 1.0,
    }
    res = engine.evaluate_pair(feat)
    assert res["decision"] in (MatchingDecision.UNCERTAIN, MatchingDecision.NON_MATCH)
    assert "INSUFFICIENT_NAME_EVIDENCE" in res["applied_guardrails"]
    assert "Missing or empty name in one or both records" in res["missing_evidence"]


def test_guardrail_excessive_spatial_separation(engine):
    """Verify that pairs separated by > 500m are forced to NON_MATCH."""
    feat = {
        "feat_distance_meters": 650.0,
        "feat_exact_name_match": 0.0,
        "feat_jaro_winkler": 0.50,
        "feat_token_sort_ratio": 0.50,
    }
    res = engine.evaluate_pair(feat)
    assert res["decision"] == MatchingDecision.NON_MATCH
    assert res["final_score"] <= 0.20
    assert "EXCESSIVE_SPATIAL_SEPARATION" in res["applied_guardrails"]


def test_baseline_report_and_samples_exist():
    """Verify that matching report and sample explanations are present on disk."""
    rep_path = Path("reports/matching_baseline_report.json")
    samples_path = Path("reports/matching_sample_explanations.json")
    assert rep_path.exists(), "Matching report must exist"
    assert samples_path.exists(), "Sample explanations must exist"
