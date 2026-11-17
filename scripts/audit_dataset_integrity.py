#!/usr/bin/env python3
"""Independent dataset integrity audit for Bengaluru raw and canonical POI datasets.

Validates schema consistency, coordinate bounds, null distributions,
source ID uniqueness, duplicate records, and independent polygon containment.
Outputs a machine-readable audit summary to reports/dataset_integrity_audit.json.
"""

import json
import time
from pathlib import Path
import pyarrow.parquet as pq
import shapely.geometry
from shapely.prepared import prep


def run_integrity_audit():
    t0 = time.time()
    repo_root = Path(__file__).resolve().parent.parent
    boundary_path = repo_root / "configs" / "bbmp_boundary.geojson"
    ov_path = repo_root / "data" / "raw" / "overture" / "bengaluru_overture_places.parquet"
    osm_path = repo_root / "data" / "raw" / "osm" / "bengaluru_osm_pois.parquet"
    canonical_path = repo_root / "data" / "processed" / "canonical_pois.parquet"
    report_dir = repo_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "dataset_integrity_audit.json"

    print("=" * 70)
    print("INDEPENDENT DATASET INTEGRITY AUDIT")
    print("=" * 70)

    # 1. Independent Polygon Containment Setup
    print(f"Loading independent boundary from {boundary_path}...")
    with open(boundary_path, "r", encoding="utf-8") as f:
        boundary_geojson = json.load(f)

    features = boundary_geojson.get("features", [])
    if not features:
        raise ValueError("No features found in boundary GeoJSON")
    raw_poly = shapely.geometry.shape(features[0]["geometry"])
    bbmp_poly = raw_poly.buffer(0) if not raw_poly.is_valid else raw_poly
    prepared_poly = prep(bbmp_poly)
    minx, miny, maxx, maxy = bbmp_poly.bounds
    print(f"Boundary polygon loaded. Bounds: [{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}]")

    audit_results = {
        "audit_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "boundary": {
            "source_file": str(boundary_path),
            "relation_id": features[0]["properties"].get("osm_id", 7902476),
            "bounds": [minx, miny, maxx, maxy],
            "polygon_valid": bbmp_poly.is_valid,
        },
        "datasets": {}
    }

    # Helper function to audit a dataset
    def audit_table(name: str, path: Path, id_col: str, lat_col: str, lon_col: str, name_col: str, cat_col: str):
        print(f"\nAuditing {name} from {path}...")
        t_start = time.time()
        table = pq.read_table(path)
        num_rows = table.num_rows
        pydict = table.to_pydict()

        # Schema & Columns
        cols = table.column_names
        null_counts = {col: pydict[col].count(None) for col in cols}

        # ID Uniqueness
        ids = pydict[id_col]
        unique_ids = set(ids)
        duplicate_id_count = len(ids) - len(unique_ids)

        # Coordinate ranges & Geometry Validity & Point Containment
        lats = pydict[lat_col]
        lons = pydict[lon_col]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        outside_bbox_count = 0
        outside_poly_count = 0

        for lon, lat in zip(lons, lats):
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                outside_bbox_count += 1
                outside_poly_count += 1
            else:
                pt = shapely.geometry.Point(lon, lat)
                if not prepared_poly.contains(pt):
                    outside_poly_count += 1

        # Name metrics
        names = pydict[name_col]
        empty_names = sum(1 for n in names if n is None or str(n).strip() == "")
        distinct_names = len(set(n for n in names if n is not None and str(n).strip() != ""))

        # Category distribution
        categories = pydict[cat_col]
        cat_counts = {}
        for c in categories:
            cat_str = str(c) if c is not None else "NULL"
            cat_counts[cat_str] = cat_counts.get(cat_str, 0) + 1

        top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        dataset_audit = {
            "record_count": num_rows,
            "file_size_bytes": path.stat().st_size,
            "columns": cols,
            "null_counts": null_counts,
            "id_uniqueness": {
                "id_column": id_col,
                "unique_ids": len(unique_ids),
                "duplicate_ids": duplicate_id_count,
                "is_unique": duplicate_id_count == 0
            },
            "coordinates": {
                "latitude_range": [min_lat, max_lat],
                "longitude_range": [min_lon, max_lon],
                "within_bbmp_bbox": (minx <= min_lon and max_lon <= maxx and miny <= min_lat and max_lat <= maxy)
            },
            "independent_containment": {
                "outside_bbox_count": outside_bbox_count,
                "outside_poly_count": outside_poly_count,
                "containment_rate_pct": round(100.0 * (num_rows - outside_poly_count) / num_rows, 4) if num_rows > 0 else 0.0,
                "all_strictly_contained": outside_poly_count == 0
            },
            "name_distribution": {
                "empty_or_null_names": empty_names,
                "populated_names": num_rows - empty_names,
                "distinct_names": distinct_names
            },
            "top_categories": dict(top_cats),
            "audit_duration_seconds": round(time.time() - t_start, 2)
        }

        print(f"  Rows: {num_rows:,} | Duplicates: {duplicate_id_count} | Null names: {empty_names:,}")
        print(f"  Coordinates: Lon [{min_lon:.5f}, {max_lon:.5f}], Lat [{min_lat:.5f}, {max_lat:.5f}]")
        print(f"  Independent Containment: {num_rows - outside_poly_count:,}/{num_rows:,} ({dataset_audit['independent_containment']['containment_rate_pct']}%)")
        return dataset_audit

    # Audit Overture
    audit_results["datasets"]["raw_overture"] = audit_table(
        name="Raw Overture Places",
        path=ov_path,
        id_col="id",
        lat_col="latitude",
        lon_col="longitude",
        name_col="name_primary",
        cat_col="basic_category"
    )

    # Audit OSM
    audit_results["datasets"]["raw_osm"] = audit_table(
        name="Raw OSM POIs",
        path=osm_path,
        id_col="osm_id",
        lat_col="latitude",
        lon_col="longitude",
        name_col="name",
        cat_col="category_original"
    )

    # Audit Canonical
    print(f"\nAuditing Canonical POIs from {canonical_path}...")
    t_start = time.time()
    can_table = pq.read_table(canonical_path)
    can_rows = can_table.num_rows
    can_pydict = can_table.to_pydict()

    # Composite source id check
    composite_ids = [f"{s}:{sid}" for s, sid in zip(can_pydict["poi_source"], can_pydict["source_record_id"])]
    unique_comp_ids = set(composite_ids)
    comp_dups = len(composite_ids) - len(unique_comp_ids)

    can_lats = can_pydict["latitude"]
    can_lons = can_pydict["longitude"]
    can_outside_poly = 0
    for lon, lat in zip(can_lons, can_lats):
        if not (minx <= lon <= maxx and miny <= lat <= maxy):
            can_outside_poly += 1
        else:
            pt = shapely.geometry.Point(lon, lat)
            if not prepared_poly.contains(pt):
                can_outside_poly += 1

    can_cat_counts = {}
    for c in can_pydict["category_normalized"]:
        can_cat_counts[c] = can_cat_counts.get(c, 0) + 1

    audit_results["datasets"]["canonical_pois"] = {
        "record_count": can_rows,
        "file_size_bytes": canonical_path.stat().st_size,
        "overture_records": can_pydict["poi_source"].count("OVERTURE"),
        "osm_records": can_pydict["poi_source"].count("OSM"),
        "composite_id_uniqueness": {
            "unique_ids": len(unique_comp_ids),
            "duplicate_ids": comp_dups,
            "is_unique": comp_dups == 0
        },
        "independent_containment": {
            "outside_poly_count": can_outside_poly,
            "containment_rate_pct": round(100.0 * (can_rows - can_outside_poly) / can_rows, 4),
            "all_strictly_contained": can_outside_poly == 0
        },
        "canonical_categories": can_cat_counts,
        "null_counts": {col: can_pydict[col].count(None) for col in can_table.column_names},
        "audit_duration_seconds": round(time.time() - t_start, 2)
    }

    audit_results["total_audit_duration_seconds"] = round(time.time() - t0, 2)

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Audit completed in {audit_results['total_audit_duration_seconds']}s")
    print(f"Report saved to: {report_file}")
    print("=" * 70)


if __name__ == "__main__":
    run_integrity_audit()
