#!/usr/bin/env python3
"""Master pipeline runner for Bengaluru POI ingestion and canonical transformation."""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.ingestion.boundary import BBMPBoundary
from src.poi_conflation.ingestion.overture import OvertureIngestor
from src.poi_conflation.ingestion.osm import OSMIngestor
from src.poi_conflation.transformation.canonical_transformer import CanonicalTransformer
import pyarrow.parquet as pq
from src.poi_conflation.validation.validators import POIValidator


def main():
    t_start = time.time()
    print("=" * 70)
    print("BENGALURU POI INGESTION & CANONICAL PIPELINE")
    print("=" * 70)

    # 1. Boundary verification
    boundary = BBMPBoundary()
    area = boundary.calculate_projected_area_km2()
    print(f"[Stage 1/4] Boundary Verified: {boundary.metadata.get('name')} ({area} km²)")

    # 2. Overture Ingestion
    print("\n[Stage 2/4] Ingesting Overture Places...")
    ov_ingestor = OvertureIngestor(boundary=boundary)
    ov_meta = ov_ingestor.run()

    # 3. OSM Ingestion
    print("\n[Stage 3/4] Ingesting OpenStreetMap POIs...")
    osm_ingestor = OSMIngestor(boundary=boundary)
    osm_meta = osm_ingestor.run()

    # 4. Canonical Transformation
    print("\n[Stage 4/4] Transforming to Canonical POI Schema...")
    transformer = CanonicalTransformer()
    canon_meta = transformer.run()

    # 5. Validation Check
    print("\n[Validation] Validating Canonical Output...")
    canon_table = pq.read_table(canon_meta["output_file"])
    validator = POIValidator(boundary=boundary)
    val_report = validator.validate_canonical_table(canon_table)

    print("=" * 70)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Total Runtime: {time.time() - t_start:.2f}s")
    print(f"Overture Contained Records: {ov_meta['record_count']:,}")
    print(f"OSM Contained Records:      {osm_meta['record_count']:,}")
    print(f"Total Canonical Records:    {canon_meta['total_canonical_records']:,}")
    print(f"Validation Status:          {'PASS' if val_report['is_valid'] else 'FAIL'}")
    print(f"Validation Details:         {val_report}")
    print("=" * 70)


if __name__ == "__main__":
    main()
