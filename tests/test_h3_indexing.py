"""Unit tests for H3 spatial indexing and deterministic ID generation."""

import h3
import pyarrow.parquet as pq
import pytest

from src.poi_conflation.indexing.h3_indexer import (
    generate_canonical_poi_id,
    compute_h3_cells,
)


def test_deterministic_id_generation():
    # Same inputs must produce exact same UUID
    id1 = generate_canonical_poi_id("OSM", "node/12345678")
    id2 = generate_canonical_poi_id("OSM", "node/12345678")
    assert id1 == id2, "Canonical ID must be deterministic"
    assert len(id1) == 36, "Canonical ID must be standard UUID string length"

    # Cross-source separation: same numeric ID from different sources must yield different UUIDs
    id_osm = generate_canonical_poi_id("OSM", "12345")
    id_overture = generate_canonical_poi_id("OVERTURE", "12345")
    assert id_osm != id_overture, "Cross-source IDs must not collide"

    # Different record IDs from same source must yield different UUIDs
    id3 = generate_canonical_poi_id("OSM", "node/87654321")
    assert id1 != id3, "Different record IDs must have different UUIDs"


def test_h3_cell_computation():
    lat, lon = 12.9716, 77.5946  # Central Bengaluru (Cubbon Park)
    c8, c9, c10 = compute_h3_cells(lat, lon)

    assert c8 is not None and c9 is not None and c10 is not None
    assert h3.is_valid_cell(c8), f"Cell {c8} must be valid"
    assert h3.is_valid_cell(c9), f"Cell {c9} must be valid"
    assert h3.is_valid_cell(c10), f"Cell {c10} must be valid"

    assert h3.get_resolution(c8) == 8, "Resolution 8 mismatch"
    assert h3.get_resolution(c9) == 9, "Resolution 9 mismatch"
    assert h3.get_resolution(c10) == 10, "Resolution 10 mismatch"

    # Parent relationship: res 9 parent is res 8; res 10 parent is res 9
    assert h3.cell_to_parent(c9, 8) == c8
    assert h3.cell_to_parent(c10, 9) == c9


def test_h3_null_and_invalid_coordinates():
    assert compute_h3_cells(None, 77.59) == (None, None, None)
    assert compute_h3_cells(12.97, None) == (None, None, None)
    assert compute_h3_cells(None, None) == (None, None, None)
    assert compute_h3_cells(95.0, 77.59) == (None, None, None)  # Lat out of range
    assert compute_h3_cells(12.97, 200.0) == (None, None, None)  # Lon out of range


def test_indexed_dataset_schema():
    indexed_path = "data/processed/canonical_pois_h3.parquet"
    table = pq.read_table(indexed_path)
    
    expected_cols = [
        "canonical_poi_id",
        "poi_source",
        "source_record_id",
        "latitude",
        "longitude",
        "h3_res8",
        "h3_res9",
        "h3_res10"
    ]
    for col in expected_cols:
        assert col in table.column_names, f"Expected {col} in indexed table"

    assert table.num_rows == 246_856, f"Expected 246,856 rows, got {table.num_rows}"

    # Sample check cell validity
    sample = table.slice(0, 100)
    for c8, c9, c10 in zip(sample.column("h3_res8"), sample.column("h3_res9"), sample.column("h3_res10")):
        s8, s9, s10 = c8.as_py(), c9.as_py(), c10.as_py()
        assert h3.is_valid_cell(s8) and h3.get_resolution(s8) == 8
        assert h3.is_valid_cell(s9) and h3.get_resolution(s9) == 9
        assert h3.is_valid_cell(s10) and h3.get_resolution(s10) == 10
