#!/usr/bin/env python3
"""Script to evaluate the explainable matching baseline against human-verified benchmark.

Generates:
1. reports/baseline_evaluation.json (overall metrics, confusion matrices, subgroups, PR-AUC).
2. reports/baseline_error_analysis.json (detailed pair-level false positive and false negative analysis).
"""

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.matching.evaluator import BaselineEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_matching_baseline")


def main():
    root = Path(__file__).resolve().parent.parent
    benchmark_csv = root / "data/processed/benchmark/human_verified/benchmark_human_verified_v1.csv"
    features_parquet = root / "data/processed/features/pairwise_features.parquet"
    eval_report_file = root / "reports/baseline_evaluation.json"
    error_report_file = root / "reports/baseline_error_analysis.json"

    logger.info(f"Loading features from {features_parquet} and benchmark from {benchmark_csv}...")
    evaluator = BaselineEvaluator(features_parquet=str(features_parquet))

    summary_report, error_items = evaluator.evaluate_benchmark(
        benchmark_csv=benchmark_csv,
        benchmark_name="human_verified_benchmark_v1",
    )

    logger.info("Evaluation complete:")
    logger.info(f"  Definite Precision: {summary_report['overall_performance']['definite_predictions_mode']['precision']}")
    logger.info(f"  Strict Recall:      {summary_report['overall_performance']['strict_binary_mode']['recall']}")
    logger.info(f"  Strict F1:          {summary_report['overall_performance']['strict_binary_mode']['f1_score']}")
    logger.info(f"  PR-AUC:             {summary_report['overall_performance']['strict_binary_mode']['pr_auc']}")
    logger.info(f"  Error / Abstentions:{len(error_items)}")

    eval_report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_report_file, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)
    logger.info(f"Baseline evaluation report written to {eval_report_file}.")

    # Format error analysis report
    error_report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "benchmark_file": str(benchmark_csv.relative_to(root)),
            "total_errors_or_abstentions": len(error_items),
            "false_positives_count": sum(1 for e in error_items if e["true_label"] != "MATCH" and e["predicted_label"] == "MATCH"),
            "false_negatives_strict_count": sum(1 for e in error_items if e["true_label"] == "MATCH" and e["predicted_label"] != "MATCH"),
        },
        "root_cause_distribution": dict(Counter(e["root_cause_category"] for e in error_items)),
        "error_details": error_items,
    }

    with open(error_report_file, "w", encoding="utf-8") as f:
        json.dump(error_report, f, indent=2)
    logger.info(f"Baseline error analysis report written to {error_report_file}.")


if __name__ == "__main__":
    main()
