"""Unit tests for category normalization logic."""

from src.poi_conflation.models.categories import (
    normalize_osm_category,
    normalize_overture_category,
    CANONICAL_CATEGORIES,
)


def test_osm_category_normalization():
    assert normalize_osm_category({"amenity": "restaurant"}) == "sustenance"
    assert normalize_osm_category({"amenity": "cafe"}) == "sustenance"
    assert normalize_osm_category({"shop": "supermarket"}) == "retail"
    assert normalize_osm_category({"shop": "clothes"}) == "retail"
    assert normalize_osm_category({"healthcare": "hospital"}) == "healthcare"
    assert normalize_osm_category({"amenity": "pharmacy"}) == "healthcare"
    assert normalize_osm_category({"tourism": "hotel"}) == "hospitality"
    assert normalize_osm_category({"amenity": "bank"}) == "financial"
    assert normalize_osm_category({"amenity": "school"}) == "education"
    assert normalize_osm_category({"office": "it"}) == "commercial_services"
    assert normalize_osm_category({"amenity": "place_of_worship"}) == "civic_religious"
    assert normalize_osm_category({"leisure": "park"}) == "leisure_tourism"
    assert normalize_osm_category({"non_standard": "unknown"}) == "other"


def test_overture_category_normalization():
    assert normalize_overture_category("restaurant", None) == "sustenance"
    assert normalize_overture_category("indian_restaurant", None) == "sustenance"
    assert normalize_overture_category("shopping", None) == "retail"
    assert normalize_overture_category("hospital", None) == "healthcare"
    assert normalize_overture_category("hotel", None) == "hospitality"
    assert normalize_overture_category("bank", None) == "financial"
    assert normalize_overture_category("school", None) == "education"
    assert normalize_overture_category("real_estate_service", None) == "commercial_services"
    assert normalize_overture_category("hindu_place_of_worship", None) == "civic_religious"
    assert normalize_overture_category(None, "shopping") == "retail"
    assert normalize_overture_category("unknown_xyz", None) == "other"


def test_all_normalized_categories_in_canonical_set():
    sample_osm_tags = [
        {"amenity": "bar"},
        {"shop": "shoes"},
        {"tourism": "museum"},
        {"historic": "monument"},
        {"amenity": "police"},
    ]
    for tags in sample_osm_tags:
        cat = normalize_osm_category(tags)
        assert cat in CANONICAL_CATEGORIES
