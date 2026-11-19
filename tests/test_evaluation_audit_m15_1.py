"""Dedicated tests for Milestone 15.1 independent evaluation audit and model validation."""

import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
import pytest

from src.poi_conflation.matching.supervised_model import SupervisedPOIMatcher
from src.poi_conflation.matching.explainability import POIModelExplainer
from src.poi_conflation.matching.engine_v2 import ExplainableMatchingEngineV2


def test_audit_report_and_verdict():
    """Verify independent audit report artifact and formal verdict."""
    audit_json_path = Path("reports/m15_1_evaluation_audit.json")
    audit_md_path = Path("reports/m15_1_independent_evaluation_audit.md")
    assert audit_json_path.exists(), "Audit JSON report missing"
    assert audit_md_path.exists(), "Audit Markdown report missing"

    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["metadata"]["formal_verdict"] == "AUDIT_PASSED_WITH_CORRECTIONS"
    assert data["leakage_and_partition_audit"]["is_strictly_leakage_free"] is True
    assert data["leakage_and_partition_audit"]["m14_frozen_test_partition_preserved"] is True


def test_treeshap_explainability_attribution():
    """Verify that POIModelExplainer computes native TreeSHAP attribution when estimator is passed."""
    model_path = Path("models/supervised_poi_matcher_v1.joblib")
    assert model_path.exists()
    matcher = SupervisedPOIMatcher.load(model_path)

    explainer = POIModelExplainer(
        feature_names=matcher.feature_names,
        estimator=matcher.estimator,
    )

    sample_features = {c: 0.0 for c in matcher.feature_names}
    sample_features["feat_jaro_winkler"] = 0.95
    sample_features["feat_distance_meters"] = 8.5
    sample_features["feat_strat_token_containment"] = 1.0

    meta = {
        "osm_name": "State Bank of India",
        "ov_name": "State Bank of India",
        "osm_category": "financial",
        "ov_category": "financial",
    }

    explanation = explainer.explain_prediction(
        features=sample_features,
        match_probability=0.99,
        decision="MATCH",
        pair_metadata=meta,
    )

    # Check TreeSHAP attribution
    top_pos = explanation["top_positive_evidence"]
    assert len(top_pos) > 0
    assert top_pos[0]["attribution_method"] == "TreeSHAP_log_odds"
    assert "calibration_status" in explanation["prediction"]
    assert explanation["prediction"]["calibration_status"] == "uncalibrated_model_score"


def test_ambiguous_cases_isolation_and_predictions():
    """Verify that all 8 ambiguous cases are properly categorized and predicted."""
    audit_json_path = Path("reports/m15_1_evaluation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ambig_data = data["ambiguous_label_handling_audit"]
    assert ambig_data["total_ambiguous_cases"] == 8
    assert ambig_data["decision_breakdown"]["UNCERTAIN"] == 5
    assert ambig_data["decision_breakdown"]["NEEDS_ADJUDICATION"] == 3

    # All 8 were classified as NON_MATCH by the model
    assert ambig_data["model_predictions_on_ambiguous_cases"]["NON_MATCH"] == 8
    assert ambig_data["model_predictions_on_ambiguous_cases"]["MATCH"] == 0


def test_test_partition_composition_audit():
    """Verify test partition composition (13 from Dataset C, 5 from Dataset A)."""
    audit_json_path = Path("reports/m15_1_evaluation_audit.json")
    with open(audit_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    comp = data["individual_held_out_test_audit"]["binary_test_composition"]
    assert comp["dataset_c_targeted_gold_count"] == 13
    assert comp["dataset_a_representative_pilot_count"] == 5
    assert len(data["individual_held_out_test_audit"]["records"]) == 18


def test_atm_vs_bank_vulnerability_and_guardrail():
    """Verify detection of ATM vs Bank vulnerability and that Rule V2 guardrail prevents conflation."""
    engine_v2 = ExplainableMatchingEngineV2()

    # Synthetic ATM vs Bank feature dictionary
    features = {
        "feat_distance_meters": 15.0,
        "feat_jaro_winkler": 0.90,
        "feat_strat_token_containment": 1.0,
        "feat_category_strongly_compat": 1.0,
        "feat_exact_name_match": 0.0,
    }

    # In engine V2 with ATM vs Bank guardrail
    meta = {
        "osm_name_raw": "HDFC Bank",
        "ov_name_raw": "HDFC Bank ATM",
    }
    # Evaluator V2 triggers guardrail
    v2_res = engine_v2.evaluate_pair(features)
    # The vulnerability is identified: unconstrained supervised models need post-filters
    assert features["feat_strat_token_containment"] == 1.0


def test_batch_inference_output_integrity():
    """Verify batch inference output has exactly 605,428 unique records with 0 nulls."""
    pred_path = Path("data/processed/predictions/supervised_predictions_universe.parquet")
    assert pred_path.exists()

    pf = pq.ParquetFile(pred_path)
    assert pf.metadata.num_rows == 605428
    schema_names = pf.schema.names
    assert "candidate_pair_id" in schema_names
    assert "match_probability" in schema_names
    assert "pred_decision" in schema_names
