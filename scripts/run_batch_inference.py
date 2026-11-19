#!/usr/bin/env python3
"""Run scalable streaming batch inference across the entire 605,428 candidate universe.

Outputs:
- data/processed/predictions/supervised_predictions_universe.parquet
- reports/inference_performance_report.json
"""

import json
import logging
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.poi_conflation.matching.batch_inference import BatchInferencePipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_batch_inference")


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "features" / "pairwise_features.parquet"
    predictions_path = root / "data" / "processed" / "predictions" / "supervised_predictions_universe.parquet"
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    pipeline = BatchInferencePipeline(
        model_path=str(root / "models" / "supervised_poi_matcher_v1.joblib"),
        batch_size=50000,
    )

    metrics = pipeline.run(
        input_parquet=str(features_path),
        output_parquet=str(predictions_path),
    )

    report_path = reports_dir / "inference_performance_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Saved inference report to {report_path}")

    print("=== Supervised Universe Batch Inference Summary ===")
    print(f"Total Pairs Scored: {metrics['performance']['total_candidate_pairs']}")
    print(f"Execution Time: {metrics['performance']['execution_time_seconds']}s")
    print(f"Throughput: {metrics['performance']['throughput_pairs_per_sec']} pairs/sec")
    print(f"Peak Memory: {metrics['performance']['peak_memory_mb']} MB")
    print("\nDecision Distribution:")
    for dec, d_info in metrics["decision_distribution"].items():
        print(f"  - {dec}: {d_info['count']} ({d_info['percentage']}%)")
    print(f"\nPredictions written to: {predictions_path}")


if __name__ == "__main__":
    main()
