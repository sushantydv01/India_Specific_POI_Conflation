"""Unit tests for BBMP boundary management and spatial validation."""

import pytest
from src.poi_conflation.ingestion.boundary import BBMPBoundary


@pytest.fixture
def bbmp():
    return BBMPBoundary("configs/bbmp_boundary.geojson")


def test_boundary_loading_and_validity(bbmp):
    assert bbmp.polygon is not None
    assert bbmp.polygon.is_valid
    assert not bbmp.polygon.is_empty
    assert bbmp.polygon.geom_type in ("Polygon", "MultiPolygon")


def test_boundary_metadata(bbmp):
    assert bbmp.metadata.get("osm_id") == 7902476
    assert bbmp.metadata.get("admin_level") == 7
    assert bbmp.metadata.get("name") == "Bengaluru"


def test_boundary_projected_area(bbmp):
    area_km2 = bbmp.calculate_projected_area_km2()
    # BBMP municipal polygon area is verified at 717.21 km² (tolerance +/- 5 km²)
    assert 710.0 <= area_km2 <= 725.0


def test_boundary_bounds(bbmp):
    minx, miny, maxx, maxy = bbmp.bounds
    # Check that bounds match Bengaluru BBMP envelope
    assert 77.45 <= minx <= 77.47
    assert 12.82 <= miny <= 12.84
    assert 77.77 <= maxx <= 77.79
    assert 13.13 <= maxy <= 13.15


def test_point_containment(bbmp):
    # MG Road / Brigade Road downtown core (should be inside BBMP)
    assert bbmp.contains_point(77.6000, 12.9750) is True
    # Vidhana Soudha (should be inside BBMP)
    assert bbmp.contains_point(77.5906, 12.9797) is True
    # Whitefield ITPL (should be inside BBMP)
    assert bbmp.contains_point(77.7470, 12.9860) is True

    # Mysore Palace (~140 km away, definitely outside)
    assert bbmp.contains_point(76.6552, 12.3051) is False
    # Hosur, Tamil Nadu (outside BBMP)
    assert bbmp.contains_point(77.8281, 12.7409) is False
    # Point outside bounds
    assert bbmp.contains_point(0.0, 0.0) is False
