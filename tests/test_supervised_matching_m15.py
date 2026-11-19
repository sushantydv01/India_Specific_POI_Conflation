"""Comprehensive unit and integration tests for Milestone 15 supervised POI matching pipeline."""

import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
import pytest

from src.poi_conflation.matching.supervised_model import SupervisedPOIMatcher
from src.poi_conflation.matching.explainability import POIModelExplainer
from src.poi_conflation.matching.batch_inference import BatchInferencePipeline
from src.poi_conflation.matching.engine import MatchingDecision


def test_operational_benchmark_consolidation():
    """Verify operational benchmark artifact counts, precedence, and filtering."""
    audit_path = Path("reports/operational_benchmark_audit.json")
    assert audit_path.exists(), "Operational benchmark audit report missing"
    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    inv = data["inventory"]
    assert inv["total_labeled_pairs"] == 100
    assert inv["total_unannotated_pairs"] == 450
    assert inv["total_combined_sample"] == 550

    # Binary vs non-binary targets
    assert inv["binary_classification_targets"]["total_binary_pairs"] == 92
    assert inv["binary_classification_targets"]["MATCH"] == 53
    assert inv["binary_classification_targets"]["NON_MATCH"] == 39
    assert inv["excluded_non_binary_pairs"]["total_excluded"] == 8

    # Provenance
    prov = inv["provenance_breakdown"]
    assert prov["HUMAN_ADJUDICATED"] == 3
    assert prov["HUMAN_VERIFIED"] == 48
    assert prov["AUTO_ADOPTED_AI"] == 49
    assert prov["human_verified_total"] == 51


def test_supervised_dataset_leakage_and_isolation():
    """Verify zero cross-split connected components, zero node sharing, and test preservation."""
    leak_path = Path("reports/supervised_dataset_leakage_audit.json")
    assert leak_path.exists(), "Leakage audit report missing"
    with open(leak_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Zero leakage guarantees
    assert data["leakage_verification"]["is_strictly_leakage_free"] is True
    assert data["leakage_verification"]["cross_split_connected_components_leakage_count"] == 0
    assert data["leakage_verification"]["cross_split_osm_nodes_leakage_count"] == 0
    assert data["leakage_verification"]["cross_split_ov_nodes_leakage_count"] == 0

    # Frozen test partition preservation
    assert data["frozen_test_partition_status"]["m14_test_pairs_preserved_intact"] is True
    assert data["frozen_test_partition_status"]["m14_test_pairs_count"] == 68


def test_feature_completeness_and_schema():
    """Verify 44 pairwise feature columns with zero nulls across all partitions."""
    for split in ["train", "validation", "test"]:
        p_path = Path(f"data/processed/supervised/{split}_features.parquet")
        assert p_path.exists(), f"Feature parquet missing for {split}"

        table = pq.read_table(p_path)
        feat_cols = [c for c in table.schema.names if c.startswith("feat_")]
        assert len(feat_cols) == 44, f"Expected 44 features in {split}, found {len(feat_cols)}"

        # Check for nulls in feature columns
        for c in feat_cols:
            col_data = table[c]
            assert col_data.null_count == 0, f"Found nulls in feature {c} of {split}"


def test_supervised_poi_matcher_lifecycle(tmp_path):
    """Test fitting, threshold tuning, decision prediction, and serialization."""
    np.random.seed(42)
    N = 40
    n_feats = 44
    X = np.random.randn(N, n_feats).astype(np.float32)
    # Target correlates with first feature
    y = (X[:, 0] > 0).astype(int)
    feat_names = [f"feat_{i}" for i in range(n_feats)]

    matcher = SupervisedPOIMatcher()
    matcher.fit(X, y, feature_names=feat_names)

    # Probabilities
    probas = matcher.predict_proba(X)
    assert len(probas) == N
    assert np.all(probas >= 0.0) and np.all(probas <= 1.0)

    # Decisions
    decisions = matcher.predict_decision(X)
    assert len(decisions) == N
    for d in decisions:
        assert isinstance(d, MatchingDecision) or d in ("MATCH", "UNCERTAIN", "NON_MATCH")

    # Feature importances
    importances = matcher.get_feature_importances()
    assert len(importances) == n_feats
    assert "feat_0" in importances

    # Serialization test
    save_file = tmp_path / "model_test.joblib"
    matcher.save(save_file)
    assert save_file.exists()

    loaded = SupervisedPOIMatcher.load(save_file)
    loaded_probas = loaded.predict_proba(X)
    np.testing.assert_allclose(probas, loaded_probas, rtol=1e-4)


def test_random_forest_matcher():
    """Verify that the Random Forest model type initializes and predicts properly."""
    config = {
        "model_type": "random_forest",
        "fallback_hyperparameters": {
            "n_estimators": 10,
            "max_depth": 3,
            "random_state": 42,
        },
    }
    matcher = SupervisedPOIMatcher(config=config)
    X = np.random.randn(20, 10).astype(np.float32)
    y = np.array([1]*10 + [0]*10, dtype=int)
    matcher.fit(X, y)

    probas = matcher.predict_proba(X)
    assert len(probas) == 20
    assert matcher.model_type == "random_forest"


def test_explainability_domain_synthesis():
    """Verify POIModelExplainer produces complete domain synthesis and feature drivers."""
    feat_names = ["feat_distance_meters", "feat_jaro_winkler", "feat_exact_name_match", "feat_category_strongly_compat"]
    explainer = POIModelExplainer(feature_names=feat_names)

    sample_features = {
        "feat_distance_meters": 12.5,
        "feat_jaro_winkler": 0.95,
        "feat_exact_name_match": 1.0,
        "feat_category_strongly_compat": 1.0,
    }
    meta = {
        "osm_name_raw": "CTR Shri Sagar",
        "ov_name_raw": "CTR Shri Sagar",
        "osm_category": "sustenance",
        "ov_category": "restaurant",
    }

    explanation = explainer.explain_prediction(
        features=sample_features,
        match_probability=0.98,
        decision="MATCH",
        pair_metadata=meta,
    )

    domain = explanation["domain_synthesis"]
    assert "Coincident location" in domain["spatial_proximity"]
    assert "Exact normalized name match" in domain["name_similarity"]
    assert "Compatible taxonomy alignment" in domain["category_compatibility"]

    assert len(explanation["top_positive_evidence"]) > 0
    assert "summary_rationale" in explanation


def test_batch_inference_execution(tmp_path):
    """Test streaming batch inference pipeline on sample features."""
    model_path = Path("models/supervised_poi_matcher_v1.joblib")
    assert model_path.exists(), "Trained model artifact missing"

    pipeline = BatchInferencePipeline(model_path=str(model_path), batch_size=200)
    out_pq = tmp_path / "test_predictions.parquet"

    # Run on validation partition features as test input
    val_features = "data/processed/supervised/validation_features.parquet"
    metrics = pipeline.run(input_parquet=val_features, output_parquet=str(out_pq))

    assert out_pq.exists()
    table = pq.read_table(out_pq)
    assert table.num_rows == 170
    assert set(table.schema.names) == {"candidate_pair_id", "match_probability", "pred_decision", "explanation_summary"}

    # Validate output decisions
    unique_decisions = set(table["pred_decision"].to_pylist())
    assert unique_decisions.issubset({"MATCH", "UNCERTAIN", "NON_MATCH"})


def test_model_evaluation_report():
    """Verify evaluation report metrics on validation and frozen test partitions."""
    eval_path = Path("reports/supervised_model_evaluation.json")
    assert eval_path.exists(), "Evaluation report missing"
    with open(eval_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Supervised LightGBM achieves superior or equal performance to baseline
    val_lgbm = data["validation_partition_evaluation"]["supervised_lgbm_poi_matcher_v1"]["overall_evaluation"]
    val_rule1 = data["validation_partition_evaluation"]["explainable_rule_baseline_v1"]["overall_evaluation"]
    assert val_lgbm["f1"] >= val_rule1["f1"]
    assert val_lgbm["brier_score"] <= val_rule1["brier_score"]

    test_lgbm = data["frozen_test_partition_evaluation"]["supervised_lgbm_poi_matcher_v1"]["overall_evaluation"]
    test_rule1 = data["frozen_test_partition_evaluation"]["explainable_rule_baseline_v1"]["overall_evaluation"]
    assert test_lgbm["f1"] >= test_rule1["f1"]


def test_model_readiness_assessment_verdict():
    """Verify model readiness formal verdict and criteria checklist."""
    readiness_path = Path("reports/model_readiness_assessment_m15.json")
    assert readiness_path.exists(), "Readiness report missing"
    with open(readiness_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["metadata"]["formal_verdict"] == "EXPERIMENTAL_MODEL_READY"
    checklist = data["criteria_checklist"]
    for c_key, c_data in checklist.items():
        assert c_data["passed"] is True, f"Readiness criterion failed: {c_key}"
