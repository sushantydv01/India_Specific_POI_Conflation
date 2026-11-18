#!/usr/bin/env python3
"""CLI script for extracting pairwise POI conflation features.

Processes the candidate universe in streaming batches and persists output to Parquet
along with a detailed JSON execution summary.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.features.extractor import PairwiseFeatureExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("extract_pairwise_features")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract pairwise POI conflation features across the candidate universe."
    )
    parser.add_argument(
        "--canonical-pois",
        default="data/processed/canonical_pois_h3.parquet",
        help="Path to spatially indexed canonical POIs Parquet file.",
    )
    parser.add_argument(
        "--candidates",
        default="data/processed/candidate_pairs/candidate_pairs_union.parquet",
        help="Path to candidate pairs Parquet file.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/features/pairwise_features.parquet",
        help="Path for output pairwise features Parquet file.",
    )
    parser.add_argument(
        "--summary",
        default="reports/feature_extraction_summary.json",
        help="Path for execution summary report JSON file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Batch size for memory-bounded streaming processing.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("Starting pairwise POI feature extraction...")
    logger.info(f"Canonical POIs: {args.canonical_pois}")
    logger.info(f"Candidate pairs: {args.candidates}")
    logger.info(f"Output features: {args.output}")
    logger.info(f"Batch size: {args.batch_size}")

    extractor = PairwiseFeatureExtractor(
        canonical_pois_path=args.canonical_pois,
        candidate_pairs_path=args.candidates,
        output_parquet_path=args.output,
        batch_size=args.batch_size,
    )

    summary = extractor.run_pipeline()

    # Save summary report
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info("Feature extraction completed successfully:")
    logger.info(f"  Total candidate pairs: {summary['total_candidate_pairs_processed']:,}")
    logger.info(f"  Total features extracted: {summary['total_features_count']}")
    logger.info(f"  Execution time: {summary['execution_time_seconds']} seconds")
    logger.info(f"  Throughput: {summary['processing_throughput_pairs_per_sec']:,} pairs/sec")
    logger.info(f"  Output size: {summary['output_size_mb']} MB")
    logger.info(f"  Peak memory: {summary['peak_memory_mb']} MB")
    logger.info(f"  Report written to: {args.summary}")


if __name__ == "__main__":
    main()
