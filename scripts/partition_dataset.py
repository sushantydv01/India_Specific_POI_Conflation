#!/usr/bin/env python3
"""Script to execute component-blocked, spatially isolated dataset partitioning.

Partitions candidate pairs into Train (60%), Validation (20%), and Test (20%) sets.
Ensures:
1. Connected-component precedence (no component appears in > 1 partition).
2. Spatial H3 Resolution 7 grouping (~1.2 km radius).
3. Zero cross-partition node or graph leakage.
4. Produces frozen partition manifests and reports/leakage_audit_report.json.
"""

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.benchmark.partitioner import ComponentBlockedPartitioner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("partition_dataset")


def main():
    root = Path(__file__).resolve().parent.parent
    queue_csv = root / "data/processed/benchmark/annotation_queue.csv"
    partitions_dir = root / "data/processed/benchmark/partitions"
    reports_dir = root / "reports"
    partitions_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading representative 500-pair queue from {queue_csv}...")
    with open(queue_csv, "r", encoding="utf-8") as f:
        pairs = list(csv.DictReader(f))

    logger.info(f"Loaded {len(pairs)} candidate pairs.")

    partitioner = ComponentBlockedPartitioner(
        h3_resolution=7,
        train_ratio=0.60,
        val_ratio=0.20,
        test_ratio=0.20,
        seed=42,
    )

    split_pairs, audit_report = partitioner.partition(pairs)

    # Export partition manifests
    for split_name, s_items in split_pairs.items():
        fname = f"{split_name.lower()}_partition.csv"
        out_csv = partitions_dir / fname
        fieldnames = list(s_items[0].keys())

        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in s_items:
                writer.writerow(row)

        logger.info(f"Saved {len(s_items)} pairs to {out_csv} ({split_name}).")

    leakage_report_file = reports_dir / "leakage_audit_report.json"
    with open(leakage_report_file, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)

    logger.info(f"Leakage audit report written to {leakage_report_file}.")
    logger.info(f"Is strictly leakage free: {audit_report['leakage_verification']['is_strictly_leakage_free']}")


if __name__ == "__main__":
    main()
