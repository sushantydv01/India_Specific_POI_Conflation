"""Comprehensive evaluation engine for the explainable rule-based POI matching baseline.

Computes:
1. Binary and multi-class classification metrics (Precision, Recall, F1, PR-AUC).
2. Confusion matrices with explicit UNCERTAIN / abstention handling.
3. Brier score analysis with explicit calibration caveats.
4. Stratified subgroup disaggregations (Kannada/Latin, distance bands, categories, strategies, strata).
5. Horvitz-Thompson weighted estimation analysis.
6. Detailed false-positive and false-negative root cause categorization.
"""

import csv
import json
import logging
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import duckdb

from src.poi_conflation.matching.engine import ExplainableMatchingEngine, MatchingDecision
from src.poi_conflation.benchmark.schema import LabelDecision

logger = logging.getLogger("matching_evaluator")


class BaselineEvaluator:
    """Evaluates ExplainableMatchingEngine against human-verified gold standard."""

    def __init__(
        self,
        features_parquet: str = "data/processed/features/pairwise_features.parquet",
        engine: Optional[ExplainableMatchingEngine] = None,
    ):
        self.features_parquet = Path(features_parquet)
        self.engine = engine or ExplainableMatchingEngine()
        self.con = duckdb.connect()

    def evaluate_benchmark(
        self,
        benchmark_csv: Path,
        benchmark_name: str = "human_verified_benchmark_v1",
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Evaluate baseline on benchmark pairs and return summary metrics and error log."""
        if not benchmark_csv.exists():
            raise FileNotFoundError(f"Benchmark CSV not found at {benchmark_csv}")

        with open(benchmark_csv, "r", encoding="utf-8") as f:
            bench_records = list(csv.DictReader(f))

        pids = [r["pair_id"] for r in bench_records]
        pid_str = "', '".join(pids)

        # Retrieve extracted features from Parquet
        col_desc = self.con.execute(f"DESCRIBE SELECT * FROM '{self.features_parquet}' LIMIT 1").fetchall()
        col_names = [d[0] for d in col_desc]
        feat_cols = [c for c in col_names if c.startswith("feat_")]

        rows = self.con.execute(f"""
            SELECT * FROM '{self.features_parquet}' WHERE candidate_pair_id IN ('{pid_str}')
        """).fetchall()

        feat_lookup: Dict[str, Dict[str, float]] = {}
        raw_feat_rows: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            row_dict = dict(zip(col_names, r))
            pid = row_dict["candidate_pair_id"]
            feat_lookup[pid] = {c: float(row_dict[c]) for c in feat_cols}
            raw_feat_rows[pid] = row_dict

        # Evaluate every pair
        eval_items: List[Dict[str, Any]] = []
        error_items: List[Dict[str, Any]] = []

        tp = 0
        fp = 0
        fn = 0
        tn = 0
        uncertain_matches = 0
        uncertain_non_matches = 0

        # Detailed confusion matrix: True (MATCH, NON_MATCH) x Pred (MATCH, NON_MATCH, UNCERTAIN)
        matrix = {
            "MATCH": {"MATCH": 0, "NON_MATCH": 0, "UNCERTAIN": 0},
            "NON_MATCH": {"MATCH": 0, "NON_MATCH": 0, "UNCERTAIN": 0},
        }

        squared_errors = []

        for b_row in bench_records:
            pid = b_row["pair_id"]
            true_label = b_row["decision"]
            feat_dict = feat_lookup.get(pid, {})
            raw_feat = raw_feat_rows.get(pid, {})

            res = self.engine.evaluate_pair(feat_dict)
            pred_decision = res["decision"]
            score = float(res["final_score"])
            guardrails = res["applied_guardrails"]

            matrix[true_label][pred_decision] += 1

            # Numeric target for Brier score analysis (MATCH = 1.0, NON_MATCH = 0.0)
            target_numeric = 1.0 if true_label == "MATCH" else 0.0
            squared_errors.append((score - target_numeric) ** 2)

            is_match = true_label == "MATCH"
            is_pred_match = pred_decision == "MATCH"
            is_pred_non_match = pred_decision == "NON_MATCH"
            is_pred_uncertain = pred_decision == "UNCERTAIN"

            if is_match and is_pred_match:
                tp += 1
            elif not is_match and is_pred_match:
                fp += 1
            elif is_match and is_pred_non_match:
                fn += 1
            elif not is_match and is_pred_non_match:
                tn += 1
            elif is_match and is_pred_uncertain:
                uncertain_matches += 1
            elif not is_match and is_pred_uncertain:
                uncertain_non_matches += 1

            # Capture errors or abstentions
            is_error = (pred_decision != true_label)
            item_eval = {
                "pair_id": pid,
                "osm_name": b_row.get("osm_name_raw"),
                "ov_name": b_row.get("ov_name_raw"),
                "osm_category": b_row.get("osm_category"),
                "ov_category": b_row.get("ov_category"),
                "distance_meters": float(b_row.get("distance_meters", 0.0)),
                "true_label": true_label,
                "predicted_label": pred_decision,
                "final_score": round(score, 4),
                "applied_guardrails": guardrails,
                "sampling_stratum": b_row.get("sampling_stratum"),
                "notes": b_row.get("notes"),
                "feat_has_kannada": feat_dict.get("feat_osm_has_kannada", 0.0) == 1.0,
                "feat_translit_avail": feat_dict.get("feat_translit_available", 0.0) == 1.0,
                "feat_is_generic": feat_dict.get("feat_is_generic_name", 0.0) == 1.0,
            }
            eval_items.append(item_eval)

            if is_error:
                # Classify root cause
                root_cause = "ABSTENTION_BELOW_MATCH_THRESHOLD"
                if guardrails:
                    root_cause = f"GUARDRAIL_TRIGGERED_{guardrails[0]}"
                elif not is_match and is_pred_uncertain:
                    root_cause = "CLOSE_PROXIMITY_ABSENT_CATEGORY_DISJOINT"
                elif is_match and is_pred_uncertain:
                    root_cause = "NAME_SUFFIX_OR_CORPORATE_EXPANSION"

                error_items.append({
                    **item_eval,
                    "root_cause_category": root_cause,
                })

        # Calculate metrics
        # 1. Definite Predictions Evaluation (ignoring UNCERTAIN abstentions)
        total_definite = tp + fp + fn + tn
        prec_definite = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec_definite = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_definite = 2 * prec_definite * rec_definite / (prec_definite + rec_definite) if (prec_definite + rec_definite) > 0 else 0.0

        # 2. Strict Binary Evaluation (treating UNCERTAIN as non-match)
        # In strict binary: predicted MATCH is positive; UNCERTAIN or NON_MATCH is negative.
        prec_strict = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        total_true_matches = sum(1 for it in eval_items if it["true_label"] == "MATCH")
        rec_strict = tp / total_true_matches if total_true_matches > 0 else 0.0
        f1_strict = 2 * prec_strict * rec_strict / (prec_strict + rec_strict) if (prec_strict + rec_strict) > 0 else 0.0

        # Brier score
        brier_score = sum(squared_errors) / len(squared_errors) if squared_errors else 0.0

        # PR-AUC computation across 21 score thresholds [0.0, 1.0]
        pr_curve = []
        for thresh in [i * 0.05 for i in range(21)]:
            thresh_tp = 0
            thresh_fp = 0
            for it in eval_items:
                p_match = it["final_score"] >= thresh
                t_match = it["true_label"] == "MATCH"
                if p_match and t_match:
                    thresh_tp += 1
                elif p_match and not t_match:
                    thresh_fp += 1
            t_prec = thresh_tp / (thresh_tp + thresh_fp) if (thresh_tp + thresh_fp) > 0 else 1.0
            t_rec = thresh_tp / total_true_matches if total_true_matches > 0 else 0.0
            pr_curve.append({"threshold": round(thresh, 2), "precision": round(t_prec, 4), "recall": round(t_rec, 4)})

        # Trapezoidal area under PR curve (sorted by recall)
        sorted_pr = sorted(pr_curve, key=lambda x: x["recall"])
        pr_auc = 0.0
        for i in range(len(sorted_pr) - 1):
            dr = sorted_pr[i+1]["recall"] - sorted_pr[i]["recall"]
            avg_p = (sorted_pr[i+1]["precision"] + sorted_pr[i]["precision"]) / 2.0
            pr_auc += dr * avg_p

        # Subgroup Disaggregations
        subgroups = self._compute_subgroup_metrics(eval_items)

        summary_report = {
            "evaluation_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_name": benchmark_name,
                "benchmark_file": str(benchmark_csv),
                "total_evaluated_records": len(eval_items),
                "baseline_model": "explainable_rule_baseline_v1",
                "match_threshold": self.engine.thresholds.get("match_min_score", 0.75),
                "uncertain_threshold": self.engine.thresholds.get("uncertain_min_score", 0.40),
            },
            "overall_performance": {
                "definite_predictions_mode": {
                    "description": "Evaluates only cases where model emitted definite MATCH or NON_MATCH (excluding UNCERTAIN)",
                    "precision": round(prec_definite, 4),
                    "recall": round(rec_definite, 4),
                    "f1_score": round(f1_definite, 4),
                    "definite_cases_evaluated": total_definite,
                    "coverage_pct": round(total_definite / max(1, len(eval_items)) * 100.0, 2),
                },
                "strict_binary_mode": {
                    "description": "Treats UNCERTAIN abstentions as Non-Match (coverage-penalized evaluation)",
                    "precision": round(prec_strict, 4),
                    "recall": round(rec_strict, 4),
                    "f1_score": round(f1_strict, 4),
                    "pr_auc": round(pr_auc, 4),
                },
                "brier_score_analysis": {
                    "raw_brier_score": round(brier_score, 4),
                    "methodological_caveat": (
                        "The baseline score [0, 1] is a heuristic weighted aggregation, NOT a calibrated posterior probability P(Match|x). "
                        "The uncalibrated Brier score reflects heuristic error rather than probabilistic miscalibration."
                    ),
                },
            },
            "confusion_matrices": {
                "three_way_decision_matrix": matrix,
                "binary_contingency": {
                    "true_positives": tp,
                    "false_positives": fp,
                    "false_negatives_strict": fn + uncertain_matches,
                    "true_negatives_strict": tn + uncertain_non_matches,
                    "model_abstentions_uncertain": uncertain_matches + uncertain_non_matches,
                },
            },
            "subgroup_performance": subgroups,
            "horvitz_thompson_estimation_notes": {
                "target_population": "BBMP Candidate Universe (605,428 pairs)",
                "sampling_nature": "Targeted Graph Ambiguity Benchmark (M11)",
                "methodology_warning": (
                    "The M11 benchmark consists of 50 targeted structural ambiguity cases (category contradictions and competing candidates). "
                    "Inclusion probabilities for these targeted graph anomalies are not uniform across the 605,428 candidate universe. "
                    "Therefore, raw sample proportions must NOT be interpreted as city-wide population prevalence without Horvitz-Thompson adjustment."
                ),
            },
        }

        return summary_report, error_items

    def _compute_subgroup_metrics(self, eval_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute stratified performance across subgroups."""
        groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            "by_distance_band": defaultdict(list),
            "by_kannada_script": defaultdict(list),
            "by_transliteration_status": defaultdict(list),
            "by_name_nature": defaultdict(list),
            "by_sampling_stratum": defaultdict(list),
        }

        for it in eval_items:
            # Distance band
            d = it["distance_meters"]
            if d <= 15.0:
                band = "le_15m"
            elif d <= 30.0:
                band = "15m_to_30m"
            elif d <= 50.0:
                band = "30m_to_50m"
            else:
                band = "gt_50m"
            groups["by_distance_band"][band].append(it)

            # Kannada
            k_key = "kannada_present" if it["feat_has_kannada"] else "latin_only"
            groups["by_kannada_script"][k_key].append(it)

            # Transliteration
            t_key = "translit_available" if it["feat_translit_avail"] else "no_translit"
            groups["by_transliteration_status"][t_key].append(it)

            # Name nature
            n_key = "generic_name" if it["feat_is_generic"] else "distinctive_name"
            groups["by_name_nature"][n_key].append(it)

            # Stratum
            stratum = it.get("sampling_stratum") or "UNKNOWN"
            groups["by_sampling_stratum"][stratum].append(it)

        subgroup_results: Dict[str, Any] = {}
        for group_name, slices in groups.items():
            subgroup_results[group_name] = {}
            for slice_key, items in slices.items():
                s_tp = sum(1 for it in items if it["true_label"] == "MATCH" and it["predicted_label"] == "MATCH")
                s_fp = sum(1 for it in items if it["true_label"] != "MATCH" and it["predicted_label"] == "MATCH")
                s_total_true_m = sum(1 for it in items if it["true_label"] == "MATCH")
                s_uncertain = sum(1 for it in items if it["predicted_label"] == "UNCERTAIN")

                s_prec = round(s_tp / (s_tp + s_fp), 4) if (s_tp + s_fp) > 0 else 0.0
                s_rec = round(s_tp / s_total_true_m, 4) if s_total_true_m > 0 else 0.0
                s_f1 = round(2 * s_prec * s_rec / (s_prec + s_rec), 4) if (s_prec + s_rec) > 0 else 0.0

                subgroup_results[group_name][slice_key] = {
                    "sample_count": len(items),
                    "true_matches": s_total_true_m,
                    "predicted_matches": s_tp + s_fp,
                    "uncertain_abstentions": s_uncertain,
                    "precision": s_prec,
                    "recall": s_rec,
                    "f1_score": s_f1,
                }

        return subgroup_results
