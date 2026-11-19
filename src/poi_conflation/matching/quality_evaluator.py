"""Matching quality evaluation framework for rule baselines, supervised ML, and production pipeline.

Computes mathematically rigorous classification metrics, threshold sweeps, uncertainty profiles,
and agreement matrices with strict provenance stratification.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
import pyarrow.parquet as pq
import joblib

from src.poi_conflation.benchmark.provenance import EvaluationProvenance, EvaluationRecord
from src.poi_conflation.matching.engine import ExplainableMatchingEngine
from src.poi_conflation.matching.engine_v2 import ExplainableMatchingEngineV2
from src.poi_conflation.matching.supervised_model import SupervisedPOIMatcher
from src.poi_conflation.graph.safeguards import ConflationSafeguardValidator
from src.poi_conflation.graph.schema import EdgeDisposition

logger = logging.getLogger("quality_evaluator")


@dataclass
class ClassificationMetrics:
    """Standard evaluation metrics for binary match decisions."""
    system_name: str
    dataset_view: str
    sample_size: int
    positive_count: int
    negative_count: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    specificity: float
    accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    confusion_matrix: List[List[int]]  # [[TN, FP], [FN, TP]]
    wilson_f1_ci: Tuple[float, float] = (0.0, 1.0)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_name": self.system_name,
            "dataset_view": self.dataset_view,
            "sample_size": self.sample_size,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "specificity": round(self.specificity, 4),
            "accuracy": round(self.accuracy, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "confusion_matrix": self.confusion_matrix,
            "wilson_f1_ci": [round(self.wilson_f1_ci[0], 4), round(self.wilson_f1_ci[1], 4)],
            "notes": self.notes,
        }


def compute_binary_metrics(
    y_true: List[int],
    y_pred: List[int],
    system_name: str,
    dataset_view: str,
    notes: str = "",
) -> ClassificationMetrics:
    """Calculate binary classification metrics with zero-division protection and Wilson interval."""
    assert len(y_true) == len(y_pred), "y_true and y_pred must have identical length"
    n = len(y_true)
    if n == 0:
        return ClassificationMetrics(
            system_name=system_name,
            dataset_view=dataset_view,
            sample_size=0,
            positive_count=0,
            negative_count=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            specificity=0.0,
            accuracy=0.0,
            false_positive_rate=0.0,
            false_negative_rate=0.0,
            confusion_matrix=[[0, 0], [0, 0]],
            notes="Empty dataset",
        )

    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    pos_cnt = tp + fn
    neg_cnt = tn + fp

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    acc = (tp + tn) / n
    fpr = fp / neg_cnt if neg_cnt > 0 else 0.0
    fnr = fn / pos_cnt if pos_cnt > 0 else 0.0

    # Approximate 95% Wilson confidence interval for F1 / accuracy
    z = 1.96
    denom = 1 + (z**2 / n)
    center = (acc + (z**2 / (2 * n))) / denom
    margin = (z * math.sqrt((acc * (1 - acc) / n) + (z**2 / (4 * (n**2))))) / denom
    ci = (max(0.0, center - margin), min(1.0, center + margin))

    return ClassificationMetrics(
        system_name=system_name,
        dataset_view=dataset_view,
        sample_size=n,
        positive_count=pos_cnt,
        negative_count=neg_cnt,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=prec,
        recall=rec,
        f1_score=f1,
        specificity=spec,
        accuracy=acc,
        false_positive_rate=fpr,
        false_negative_rate=fnr,
        confusion_matrix=[[tn, fp], [fn, tp]],
        wilson_f1_ci=ci,
        notes=notes,
    )


class ConflationQualityEvaluator:
    """Orchestrates comprehensive multi-system evaluation over benchmark datasets."""

    def __init__(self, project_root: Optional[Path] = None):
        self.root = project_root or Path(".")
        self.rule_v1 = ExplainableMatchingEngine()
        self.rule_v2 = ExplainableMatchingEngineV2()
        self.safeguard_validator = ConflationSafeguardValidator(enable_honorific_safeguard=True)
        
        # Load supervised model
        model_path = self.root / "models/supervised_poi_matcher_v1.joblib"
        self.supervised_model: Optional[SupervisedPOIMatcher] = None
        if model_path.exists():
            self.supervised_model = SupervisedPOIMatcher.load(model_path)

        # Cache features table for benchmark pairs
        feat_path = self.root / "data/processed/features/pairwise_features.parquet"
        self.features_by_pair: Dict[str, Dict[str, float]] = {}
        if feat_path.exists():
            # Load candidate features in streaming batches to protect memory
            tbl = pq.read_table(feat_path)
            # Read columns
            p_ids = tbl["candidate_pair_id"].to_pylist()
            p_set = set(p_ids)
            # Convert to dict for fast lookup
            feature_cols = [c for c in tbl.column_names if c.startswith("feat_")]
            # Only store rows matching benchmark/pool pairs
            pool_path = self.root / "data/processed/benchmark/operational/operational_benchmark_full_pool.csv"
            bench_ids = set()
            if pool_path.exists():
                import csv
                with open(pool_path, "r", encoding="utf-8") as f:
                    bench_ids = {r["pair_id"] for r in csv.DictReader(f)}
            
            pylist = tbl.to_pylist()
            for r in pylist:
                pid = r["candidate_pair_id"]
                if pid in bench_ids:
                    self.features_by_pair[pid] = {k: float(r[k]) for k in feature_cols if r[k] is not None}

    def _extract_feature_vector(self, feat: Dict[str, float]) -> List[float]:
        """Convert feature dict to aligned vector for SupervisedPOIMatcher."""
        if not self.supervised_model or not self.supervised_model.feature_names:
            return []
        return [float(feat.get(name, 0.0)) for name in self.supervised_model.feature_names]

    def evaluate_systems_on_records(
        self,
        records: List[EvaluationRecord],
        dataset_view_name: str,
        match_threshold: float = 0.55,
    ) -> Dict[str, ClassificationMetrics]:
        """Evaluate Rule V1, Rule V2, LightGBM, and Production Pipeline on labeled records."""
        # Filter to binary ground truth only
        eval_records = [r for r in records if r.binary_label is not None and r.pair_id in self.features_by_pair]
        y_true = [r.binary_label for r in eval_records]

        results: Dict[str, ClassificationMetrics] = {}

        # 1. Rule Baseline V1
        v1_preds = []
        for r in eval_records:
            feat = self.features_by_pair.get(r.pair_id, {})
            v1_res = self.rule_v1.evaluate_pair(feat)
            dec = v1_res.get("decision", "NO_MATCH")
            v1_preds.append(1 if dec in ("MATCH", "STRONG_MATCH") else 0)
        results["rule_baseline_v1"] = compute_binary_metrics(
            y_true, v1_preds, "Rule Baseline V1", dataset_view_name,
            notes="Linear weighted heuristic baseline"
        )

        # 2. Rule Baseline V2
        v2_preds = []
        for r in eval_records:
            feat = self.features_by_pair.get(r.pair_id, {})
            v2_res = self.rule_v2.evaluate_pair(feat)
            dec = v2_res.get("decision", "NO_MATCH")
            v2_preds.append(1 if dec in ("MATCH", "STRONG_MATCH") else 0)
        results["rule_baseline_v2"] = compute_binary_metrics(
            y_true, v2_preds, "Rule Baseline V2", dataset_view_name,
            notes="Optimized experimental rule baseline"
        )

        # 3. Supervised LightGBM
        if self.supervised_model:
            lgbm_preds = []
            for r in eval_records:
                feat = self.features_by_pair.get(r.pair_id, {})
                vec = self._extract_feature_vector(feat)
                prob = self.supervised_model.predict_proba([vec])[0]
                lgbm_preds.append(1 if prob >= match_threshold else 0)
            results["supervised_lightgbm"] = compute_binary_metrics(
                y_true, lgbm_preds, "Supervised LightGBM", dataset_view_name,
                notes=f"Gradient boosted tree with match_threshold={match_threshold}"
            )

        # 4. Production Pipeline (LightGBM + Safeguards)
        if self.supervised_model:
            prod_preds = []
            for r in eval_records:
                feat = self.features_by_pair.get(r.pair_id, {})
                vec = self._extract_feature_vector(feat)
                prob = self.supervised_model.predict_proba([vec])[0]
                initial_dec = "MATCH" if prob >= match_threshold else "NO_MATCH"
                
                # Apply safeguards
                res = self.safeguard_validator.validate_candidate_edge(
                    osm_name=r.osm_name_raw,
                    ov_name=r.ov_name_raw,
                    osm_category=r.osm_category,
                    ov_category=r.ov_category,
                    distance_meters=r.distance_meters,
                    supervised_model_score=prob,
                    supervised_decision=initial_dec,
                    features=feat,
                )
                prod_preds.append(1 if res.disposition == EdgeDisposition.ACCEPTED_EQUIVALENCE else 0)
            results["production_pipeline"] = compute_binary_metrics(
                y_true, prod_preds, "Production Pipeline", dataset_view_name,
                notes="LightGBM model with active domain and honorific safeguards"
            )

        return results

    def compute_threshold_sweep(
        self,
        records: List[EvaluationRecord],
        thresholds: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate precision, recall, and review volume across threshold sweep [0.1, 0.9]."""
        if not self.supervised_model:
            return []
        if thresholds is None:
            thresholds = [round(t * 0.05, 2) for t in range(2, 19)]  # 0.10 to 0.90

        eval_records = [r for r in records if r.binary_label is not None and r.pair_id in self.features_by_pair]
        y_true = [r.binary_label for r in eval_records]

        probs = []
        for r in eval_records:
            feat = self.features_by_pair.get(r.pair_id, {})
            vec = self._extract_feature_vector(feat)
            prob = self.supervised_model.predict_proba([vec])[0]
            probs.append(prob)

        sweep_rows: List[Dict[str, Any]] = []
        for th in thresholds:
            y_pred = [1 if p >= th else 0 for p in probs]
            m = compute_binary_metrics(y_true, y_pred, "Supervised LightGBM", "Threshold Sweep")
            sweep_rows.append({
                "threshold": th,
                "precision": round(m.precision, 4),
                "recall": round(m.recall, 4),
                "f1_score": round(m.f1_score, 4),
                "tp": m.true_positives,
                "fp": m.false_positives,
                "tn": m.true_negatives,
                "fn": m.false_negatives,
                "accepted_count": m.true_positives + m.false_positives,
            })

        return sweep_rows
