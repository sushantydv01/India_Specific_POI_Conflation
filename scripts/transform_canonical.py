#!/usr/bin/env python3
"""Script to transform raw OSM and Overture extracts into Canonical POI dataset."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.transformation.canonical_transformer import CanonicalTransformer


def main():
    print("Executing Canonical POI Transformation...")
    transformer = CanonicalTransformer()
    metadata = transformer.run()
    print("Canonical transformation complete:")
    print(f"  Total Canonical POIs: {metadata['total_canonical_records']:,}")
    print(f"    - Overture: {metadata['overture_records']:,}")
    print(f"    - OSM:      {metadata['osm_records']:,}")
    print(f"  Output Parquet: {metadata['output_file']}")


if __name__ == "__main__":
    main()
