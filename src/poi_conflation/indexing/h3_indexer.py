"""Uber H3 spatial indexing module for canonical POI records.

Computes discrete global grid cell identifiers at multiple spatial resolutions
(Resolution 8, 9, 10) and assigns deterministic UUIDv5 canonical identifiers.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import h3
import pyarrow as pa
import pyarrow.parquet as pq

# Persistent namespace for deterministic POI UUIDv5 generation
POI_NAMESPACE_URL = uuid.NAMESPACE_URL
POI_URL_PREFIX = "https://poi.conflation.in"


def generate_canonical_poi_id(poi_source: str, source_record_id: str) -> str:
    """Generate deterministic, collision-free UUIDv5 from source and source record ID."""
    name = f"{POI_URL_PREFIX}/{poi_source.lower()}/{source_record_id}"
    return str(uuid.uuid5(POI_NAMESPACE_URL, name))


def compute_h3_cells(
    lat: Optional[float],
    lon: Optional[float]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Compute H3 cell strings at resolutions 8, 9, and 10 for WGS84 coordinates.
    
    Returns (h3_res8, h3_res9, h3_res10). Returns (None, None, None) if coordinates are invalid.
    """
    if lat is None or lon is None:
        return (None, None, None)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return (None, None, None)

    try:
        c8 = h3.latlng_to_cell(lat, lon, 8)
        c9 = h3.latlng_to_cell(lat, lon, 9)
        c10 = h3.latlng_to_cell(lat, lon, 10)
        return (c8, c9, c10)
    except Exception:
        return (None, None, None)


class H3SpatialIndexer:
    """Coordinates spatial indexing of canonical POI tables with H3 resolutions 8, 9, 10."""

    def __init__(
        self,
        input_path: str = "data/processed/canonical_pois.parquet",
        output_path: str = "data/processed/canonical_pois_h3.parquet",
        metadata_path: str = "data/processed/canonical_pois_h3_metadata.json"
    ):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.metadata_path = Path(metadata_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def run(self) -> Dict[str, Any]:
        """Execute H3 spatial indexing and export indexed Parquet dataset."""
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input canonical dataset missing: {self.input_path}")

        print(f"Loading canonical dataset from {self.input_path}...")
        t0 = time.time()
        table = pq.read_table(self.input_path)
        num_rows = table.num_rows
        print(f"Loaded {num_rows:,} records in {time.time() - t0:.2f}s")

        t_index0 = time.time()
        pydict = table.to_pydict()
        sources = pydict["poi_source"]
        source_ids = pydict["source_record_id"]
        lats = pydict["latitude"]
        lons = pydict["longitude"]

        canonical_ids = []
        res8_cells = []
        res9_cells = []
        res10_cells = []

        print("Generating canonical IDs and computing H3 resolutions 8, 9, 10...")
        for src, sid, lat, lon in zip(sources, source_ids, lats, lons):
            cid = generate_canonical_poi_id(src, sid)
            c8, c9, c10 = compute_h3_cells(lat, lon)
            canonical_ids.append(cid)
            res8_cells.append(c8)
            res9_cells.append(c9)
            res10_cells.append(c10)

        indexing_duration = round(time.time() - t_index0, 2)
        print(f"Spatial indexing finished in {indexing_duration}s")

        # Assemble new PyArrow table
        # Prepend canonical_poi_id, and append h3 fields
        new_columns = [
            pa.array(canonical_ids, pa.string()),
        ] + [
            table.column(c) for c in table.column_names
        ] + [
            pa.array(res8_cells, pa.string()),
            pa.array(res9_cells, pa.string()),
            pa.array(res10_cells, pa.string()),
        ]

        new_names = ["canonical_poi_id"] + table.column_names + ["h3_res8", "h3_res9", "h3_res10"]
        indexed_table = pa.Table.from_arrays(new_columns, names=new_names)

        # Validation check on output
        print("Validating H3 cell integrity...")
        unique_cids = len(set(canonical_ids))
        if unique_cids != num_rows:
            raise ValueError(f"Canonical ID collision: expected {num_rows}, got {unique_cids}")

        unique_res8 = len(set(res8_cells))
        unique_res9 = len(set(res9_cells))
        unique_res10 = len(set(res10_cells))
        print(f"H3 Cells: Res 8: {unique_res8:,} unique | Res 9: {unique_res9:,} unique | Res 10: {unique_res10:,} unique")

        # Export table
        print(f"Exporting indexed dataset to {self.output_path}...")
        t_write0 = time.time()
        pq.write_table(indexed_table, self.output_path, compression="ZSTD")
        write_duration = round(time.time() - t_write0, 2)

        file_size_mb = self.output_path.stat().st_size / 1e6
        total_duration = round(time.time() - t0, 2)
        print(f"Wrote {self.output_path} ({file_size_mb:.2f} MB) in {write_duration}s (Total: {total_duration}s)")

        metadata = {
            "dataset": "Bengaluru Canonical POIs with H3 Spatial Indexing",
            "creation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input_file": str(self.input_path),
            "output_file": str(self.output_path),
            "total_records": num_rows,
            "overture_records": sources.count("OVERTURE"),
            "osm_records": sources.count("OSM"),
            "file_size_bytes": self.output_path.stat().st_size,
            "indexing_duration_seconds": indexing_duration,
            "total_duration_seconds": total_duration,
            "h3_metrics": {
                "unique_res8_cells": unique_res8,
                "unique_res9_cells": unique_res9,
                "unique_res10_cells": unique_res10,
                "null_res8_count": res8_cells.count(None),
                "null_res9_count": res9_cells.count(None),
                "null_res10_count": res10_cells.count(None),
            }
        }

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata
