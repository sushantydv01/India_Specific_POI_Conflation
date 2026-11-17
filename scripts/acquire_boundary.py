#!/usr/bin/env python3
"""Script to verify and reload the BBMP boundary GeoJSON."""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.ingestion.boundary import BBMPBoundary


def main():
    print("Verifying official BBMP Boundary...")
    boundary = BBMPBoundary()
    area_km2 = boundary.calculate_projected_area_km2()
    minx, miny, maxx, maxy = boundary.bounds
    print(f"BBMP Boundary Verified Successfully:")
    print(f"  OSM Relation: {boundary.metadata.get('osm_id')}")
    print(f"  Admin Level:  {boundary.metadata.get('admin_level')}")
    print(f"  Projected Area (EPSG:32643): {area_km2:.2f} km²")
    print(f"  Bounding Box: [{minx:.5f}, {miny:.5f}, {maxx:.5f}, {maxy:.5f}]")


if __name__ == "__main__":
    main()
