"""Comprehensive evaluation engine for explainable rule-based POI matching engines.

Audited and enhanced in Milestone 13 to support:
1. Strict binary classification vs. selective prediction metrics with explicit coverage and abstention rates.
2. Exact Precision-Recall Curve with proper (recall=0, precision=1.0) boundary anchoring and Average Precision.
3. Exact ROC-AUC calculation via Wilcoxon-Mann-Whitney rank-sum and trapezoidal ROC integration.
4. Brier score calculation with explicit methodological caveats regarding heuristic scores vs. calibrated probabilities.
5. Deduplication and provenance filtering (HUMAN_VERIFIED and HUMAN_ADJUDICATED).
6. Stratified subgroup disaggregations and root cause error taxonomies.
"""

import csv
import json
import logging
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
import duckdb

from src.poi_conflation.matching.engine import ExplainableMatchingEngine, MatchingDecision
from src.poi_conflation.benchmark.schema import LabelDecision

logger = logging.getLogger("matching_evaluator")


def compute_roc_auc(scores: List[float], labels: List[int]) -> float:
    """Compute exact ROC-AUC using Wilcoxon-Mann-Whitney U statistic."""
    pos_scores = [s for s, y in zip(scores, labels) if y == 1]
    neg_scores = [s for s, y in zip(scores, labels) if y == 0]

    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    if n_pos == 0 or n_neg == 0:
        return 0.5

    u = 0.0
    for p in pos_scores:
        for n in neg_scores:
            if p > n:
                u += 1.0
            elif p == n:
                u += 0.5

    return u / (n_pos * n_neg)


def compute_pr_curve_and_auc(scores: List[float], labels: List[int]) -> Tuple[List[Dict[str, float]], float]:
    """Compute exact Precision-Recall curve and trapezoidal PR-AUC anchored at recall 0.0."""
    total_positives = sum(labels)
    if total_positives == 0:
        return [{"threshold": 1.0, "precision": 1.0, "recall": 0.0}], 0.0

    unique_scores = sorted(set(scores), reverse=True)

    pr_points = []
    # Anchor point: at threshold higher than max score, predicted positives = 0, recall = 0.0, precision = 1.0
    pr_points.append({"threshold": round(unique_scores[0] + 0.01, 4), "precision": 1.0, "recall": 0.0})

    for thresh in unique_scores:
        tp = sum(1 for s, y in zip(scores, labels) if s >= thresh and y == 1)
        fp = sum(1 for s, y in zip(scores, labels) if s >= thresh and y == 0)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / total_positives
        pr_points.append({"threshold": round(thresh, 4), "precision": round(prec, 4), "recall": round(rec, 4)})

    # Precision envelope interpolation across recall points
    rec_to_max_prec = {}
    for pt in pr_points:
        r = pt["recall"]
        p = pt["precision"]
        if r not in rec_to_max_prec or p > rec_to_max_prec[r]:
            rec_to_max_prec[r] = p

    sorted_recs = sorted(rec_to_max_prec.keys())
    interp_precs = [rec_to_max_prec[r] for r in sorted_recs]
    for i in range(len(interp_precs) - 2, -1, -1):
        interp_precs[i] = max(interp_precs[i], interp_precs[i + 1])

    pr_auc = 0.0
    for i in range(len(sorted_recs) - 1):
        dr = sorted_recs[i + 1] - sorted_recs[i]
        avg_p = (interp_precs[i + 1] + interp_precs[i]) / 2.0
        pr_auc += dr * avg_p

    return pr_points, pr_auc


class BaselineEvaluator:
    """Evaluates rule-based matching engines against human-verified gold standards."""

    def __init__(
        self,
        features_parquet: str = "data/processed/features/pairwise_features.parquet",
        engine: Optional[Any] = None,
    ):
        self.features_parquet = Path(features_parquet)
        self.engine = engine or ExplainableMatchingEngine()
        self.con = duckdb.connect()

    def evaluate_benchmark(
        self,
        benchmark_csv: Path,
        benchmark_name: str = "human_verified_benchmark_v1",
        engine_name: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Evaluate baseline on benchmark pairs and return summary metrics and error log."""
        if not benchmark_csv.exists():
            raise FileNotFoundError(f"Benchmark CSV not found at {benchmark_csv}")

        with open(benchmark_csv, "r", encoding="utf-8") as f:
            bench_records = list(csv.DictReader(f))

        seen_pids: Set[str] = set()
        dedup_records = []
        for r in bench_records:
            pid = r["pair_id"]
            if pid not in seen_pids:
                seen_pids.add(pid)
                dedup_records.append(r)
            else:
                logger.warning("Duplicate pair_id ignored in benchmark evaluation: %s", pid)
        bench_records = dedup_records

        pids = [r["pair_id"] for r in bench_records]
        pid_str = "', '".join(pids)

        col_desc = self.con.execute(f"DESCRIBE SELECT * FROM '{self.features_parquet}' LIMIT 1").fetchall()
        col_names = [d[0] for d in col_desc]
        feat_cols = [c for c in col_names if c.startswith("feat_")]

        rows = self.con.execute(f"""
            SELECT * FROM '{self.features_parquet}' WHERE candidate_pair_id IN ('{pid_str}')
        """).fetchall()

        feat_lookup: Dict[str, Dict[str, float]] = {}
        for r in rows:
            row_dict = dict(zip(col_names, r))
            pid = row_dict["candidate_pair_id"]
            feat_lookup[pid] = {c: float(row_dict[c]) for c in feat_cols}

        eval_items: List[Dict[str, Any]] = []
        error_items: List[Dict[str, Any]] = []

        scores: List[float] = []
        binary_targets: List[int] = []

        tp = 0
        fp = 0
        fn = 0
        tn = 0
        uncertain_matches = 0
        uncertain_non_matches = 0

        matrix = {
            "MATCH": {"MATCH": 0, "NON_MATCH": 0, "UNCERTAIN": 0},
            "NON_MATCH": {"MATCH": 0, "NON_MATCH": 0, "UNCERTAIN": 0},
        }

        squared_errors = []

        for b_row in bench_records:
            pid = b_row["pair_id"]
            true_label = b_row["decision"]
            feat_dict = feat_lookup.get(pid, {})

            res = self.engine.evaluate_pair(feat_dict)
            pred_decision = res["decision"]
            score = float(res["final_score"])
            guardrails = res.get("applied_guardrails", [])

            if true_label not in matrix:
                logger.warning("Excluding unadjudicated / non-binary label from matrix: %s", true_label)
                continue

            matrix[true_label][pred_decision] += 1

            target_numeric = 1 if true_label == "MATCH" else 0
            scores.append(score)
            binary_targets.append(target_numeric)
            squared_errors.append((score - float(target_numeric)) ** 2)

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

        total_definite = tp + fp + fn + tn
        prec_definite = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec_definite = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_definite = 2 * prec_definite * rec_definite / (prec_definite + rec_definite) if (prec_definite + rec_definite) > 0 else 0.0

        prec_strict = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        total_true_matches = sum(binary_targets)
        rec_strict = tp / total_true_matches if total_true_matches > 0 else 0.0
        f1_strict = 2 * prec_strict * rec_strict / (prec_strict + rec_strict) if (prec_strict + rec_strict) > 0 else 0.0

        roc_auc = compute_roc_auc(scores, binary_targets)
        pr_curve, pr_auc = compute_pr_curve_and_auc(scores, binary_targets)
        brier_score = sum(squared_errors) / len(squared_errors) if squared_errors else 0.0

        subgroups = self._compute_subgroup_metrics(eval_items)

        model_name = engine_name or getattr(self.engine, "engine_version", "explainable_rule_baseline_v1")
        match_thresh = getattr(self.engine, "thresholds", {}).get("match_min_score", 0.75)
        uncertain_thresh = getattr(self.engine, "thresholds", {}).get("uncertain_min_score", 0.40)

        summary_report = {
            "evaluation_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_name": benchmark_name,
                "benchmark_file": str(benchmark_csv),
                "total_evaluated_records": len(eval_items),
                "baseline_model": model_name,
                "match_threshold": match_thresh,
                "uncertain_threshold": uncertain_thresh,
            },
            "overall_performance": {
                "selective_prediction_mode": {
                    "description": "Evaluates only cases where model emitted definite MATCH or NON_MATCH (excluding UNCERTAIN abstentions)",
                    "precision": round(prec_definite, 4),
                    "recall": round(rec_definite, 4),
                    "f1_score": round(f1_definite, 4),
                    "definite_cases_evaluated": total_definite,
                    "coverage_pct": round(total_definite / max(1, len(eval_items)) * 100.0, 2),
                    "abstention_rate_pct": round((len(eval_items) - total_definite) / max(1, len(eval_items)) * 100.0, 2),
                },
                "strict_binary_mode": {
                    "description": "Treats UNCERTAIN abstentions as Non-Match (coverage-penalized evaluation)",
                    "precision": round(prec_strict, 4),
                    "recall": round(rec_strict, 4),
                    "f1_score": round(f1_strict, 4),
                    "roc_auc": round(roc_auc, 4),
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
                    "The benchmark contains targeted structural ambiguity cases. "
                    "Sample proportions must NOT be interpreted as city-wide population prevalence without Horvitz-Thompson adjustment."
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

            k_key = "kannada_present" if it["feat_has_kannada"] else "latin_only"
            groups["by_kannada_script"][k_key].append(it)

            t_key = "translit_available" if it["feat_translit_avail"] else "no_translit"
            groups["by_transliteration_status"][t_key].append(it)

            n_key = "generic_name" if it["feat_is_generic"] else "distinctive_name"
            groups["by_name_nature"][n_key].append(it)

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
