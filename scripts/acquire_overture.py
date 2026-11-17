#!/usr/bin/env python3
"""Script to acquire and extract Overture Places for Bengaluru (BBMP)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.ingestion.overture import OvertureIngestor


def main():
    print("Starting Overture Maps Places ingestion...")
    ingestor = OvertureIngestor()
    metadata = ingestor.run()
    print("Overture extraction finished:")
    print(f"  Release: {metadata['release']}")
    print(f"  Contained Records: {metadata['record_count']:,}")
    print(f"  Output Parquet: {metadata['output_file']}")


if __name__ == "__main__":
    main()
