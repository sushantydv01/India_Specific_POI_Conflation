#!/usr/bin/env python3
"""Script to execute H3 spatial indexing on the canonical POI dataset."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.indexing.h3_indexer import H3SpatialIndexer


def main():
    indexer = H3SpatialIndexer()
    meta = indexer.run()
    print("\nH3 Spatial Indexing Summary:")
    print(f"  Records Indexed:    {meta['total_records']:,}")
    print(f"  Output Artifact:    {meta['output_file']} ({meta['file_size_bytes'] / 1e6:.2f} MB)")
    print(f"  Unique Res 8 Cells: {meta['h3_metrics']['unique_res8_cells']:,}")
    print(f"  Unique Res 9 Cells: {meta['h3_metrics']['unique_res9_cells']:,}")
    print(f"  Unique Res 10 Cells:{meta['h3_metrics']['unique_res10_cells']:,}")
    print(f"  Runtime:            {meta['total_duration_seconds']}s")


if __name__ == "__main__":
    main()
