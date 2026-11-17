"""Unit tests for geographic, schema, and integrity validation rules."""

import pytest
from src.poi_conflation.validation.validators import POIValidator
from src.poi_conflation.ingestion.boundary import BBMPBoundary


@pytest.fixture
def validator():
    return POIValidator()


def test_coordinate_validation(validator):
    assert validator.validate_coordinates(12.97, 77.59)[0] is True
    assert validator.validate_coordinates(None, 77.59)[0] is False
    assert validator.validate_coordinates(12.97, None)[0] is False
    assert validator.validate_coordinates(95.0, 77.59)[0] is False
    assert validator.validate_coordinates(12.97, 190.0)[0] is False
    assert validator.validate_coordinates(0.0, 0.0)[0] is False


def test_boundary_containment_validation(validator):
    # Inside BBMP (Indiranagar)
    assert validator.validate_boundary_containment(12.9780, 77.6400)[0] is True
    # Outside BBMP (Chennai)
    assert validator.validate_boundary_containment(13.0827, 80.2707)[0] is False


def test_canonical_record_validation(validator):
    valid_record = {
        "poi_source": "OVERTURE",
        "source_record_id": "test-id-1",
        "source_release": "2026-10-21.0",
        "name_original": "Test Cafe",
        "name_normalized": "test cafe",
        "geometry_wkt": "POINT (77.60 12.97)",
        "latitude": 12.97,
        "longitude": 77.60,
        "category_normalized": "sustenance"
    }
    assert len(validator.validate_canonical_record(valid_record)) == 0

    # Missing required field
    invalid_record = valid_record.copy()
    invalid_record["name_original"] = ""
    errors = validator.validate_canonical_record(invalid_record)
    assert any("name_original" in e for e in errors)

    # Invalid source
    invalid_record = valid_record.copy()
    invalid_record["poi_source"] = "GOOGLE_MAPS"
    errors = validator.validate_canonical_record(invalid_record)
    assert any("poi_source" in e for e in errors)

    # Invalid category
    invalid_record = valid_record.copy()
    invalid_record["category_normalized"] = "invalid_category_xyz"
    errors = validator.validate_canonical_record(invalid_record)
    assert any("category_normalized" in e for e in errors)
