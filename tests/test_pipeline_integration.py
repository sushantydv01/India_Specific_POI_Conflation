"""Integration test for the Bengaluru POI acquisition and canonical pipeline outputs."""

from pathlib import Path
import pyarrow.parquet as pq
import pytest

from src.poi_conflation.ingestion.boundary import BBMPBoundary
from src.poi_conflation.models.canonical import get_canonical_arrow_schema
from src.poi_conflation.validation.validators import POIValidator


@pytest.fixture(scope="module")
def boundary():
    return BBMPBoundary()


def test_overture_extract_exists_and_valid():
    ov_path = Path("data/raw/overture/bengaluru_overture_places.parquet")
    meta_path = Path("data/raw/overture/extraction_metadata.json")
    assert ov_path.exists(), "Overture raw parquet must exist"
    assert meta_path.exists(), "Overture metadata must exist"
    
    table = pq.read_table(ov_path)
    assert table.num_rows > 150_000, f"Expected >150k Overture records, got {table.num_rows}"
    assert "id" in table.column_names
    assert "name_primary" in table.column_names
    assert "latitude" in table.column_names
    assert "longitude" in table.column_names


def test_osm_extract_exists_and_valid():
    osm_path = Path("data/raw/osm/bengaluru_osm_pois.parquet")
    meta_path = Path("data/raw/osm/extraction_metadata.json")
    assert osm_path.exists(), "OSM raw parquet must exist"
    assert meta_path.exists(), "OSM metadata must exist"

    table = pq.read_table(osm_path)
    assert table.num_rows > 30_000, f"Expected >30k OSM records, got {table.num_rows}"
    assert "osm_id" in table.column_names
    assert "name" in table.column_names
    assert "latitude" in table.column_names
    assert "longitude" in table.column_names


def test_canonical_dataset_conformance(boundary):
    canon_path = Path("data/processed/canonical_pois.parquet")
    assert canon_path.exists(), "Canonical parquet must exist"

    table = pq.read_table(canon_path)
    assert table.num_rows >= 200_000, f"Expected >=200k canonical records, got {table.num_rows}"

    expected_schema = get_canonical_arrow_schema()
    for field in expected_schema:
        assert field.name in table.column_names, f"Missing field {field.name} in canonical table"

    # Validate with POIValidator
    validator = POIValidator(boundary=boundary)
    # Check sample of records
    sample_table = table.slice(0, 1000)
    report = validator.validate_canonical_table(sample_table)
    assert report["is_valid"], f"Validation failure: {report}"
