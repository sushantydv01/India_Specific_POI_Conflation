#!/usr/bin/env python3
"""Script to acquire and parse OpenStreetMap POIs for Bengaluru (BBMP)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.ingestion.osm import OSMIngestor


def main():
    print("Starting OpenStreetMap POI ingestion...")
    ingestor = OSMIngestor()
    metadata = ingestor.run()
    print("OSM POI ingestion finished:")
    print(f"  Contained Records: {metadata['record_count']:,}")
    print(f"  Output Parquet: {metadata['output_file']}")


if __name__ == "__main__":
    main()
