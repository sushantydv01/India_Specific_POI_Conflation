"""Unit tests for the canonical POI schema and Arrow table conversion."""

import pyarrow as pa
from src.poi_conflation.models.canonical import CanonicalPOI, get_canonical_arrow_schema
from src.poi_conflation.transformation.canonical_transformer import normalize_name_string


def test_canonical_poi_creation():
    poi = CanonicalPOI(
        poi_source="OVERTURE",
        source_record_id="test-uuid-1234",
        source_release="2026-10-21.0",
        name_original="Empire Restaurant",
        name_normalized="empire restaurant",
        alternate_names=["Hotel Empire"],
        name_en="Empire Restaurant",
        name_kn="ಎಂಪೈರ್ ರೆಸ್ಟೋರೆಂಟ್",
        latitude=12.9750,
        longitude=77.6000,
        geometry_wkt="POINT (77.6000 12.9750)",
        category_original="restaurant",
        category_normalized="sustenance",
        address_original="Church Street, Bengaluru",
        address_locality="Bengaluru Central",
        address_postcode="560001",
        phone="+91 80 4041 4041",
        website="https://hotelempire.in",
        confidence=0.92,
    )
    d = poi.to_dict()
    assert d["poi_source"] == "OVERTURE"
    assert d["name_normalized"] == "empire restaurant"
    assert d["name_kn"] == "ಎಂಪೈರ್ ರೆಸ್ಟೋರೆಂಟ್"
    assert d["address_postcode"] == "560001"
    assert isinstance(d["provenance_metadata"], str)


def test_arrow_schema_conformance():
    schema = get_canonical_arrow_schema()
    poi = CanonicalPOI(
        poi_source="OSM",
        source_record_id="node/99999",
        source_release="2026-11-17",
        name_original="Vidyarthi Bhavan",
        name_normalized="vidyarthi bhavan",
        latitude=12.9400,
        longitude=77.5700,
        geometry_wkt="POINT (77.5700 12.9400)",
        category_original="amenity=restaurant",
        category_normalized="sustenance",
    )
    table = pa.Table.from_pylist([poi.to_dict()], schema=schema)
    assert table.num_rows == 1
    assert table.num_columns == len(schema)
    assert table.column("poi_source")[0].as_py() == "OSM"


def test_name_normalization():
    assert normalize_name_string("  A2B - Veg Restaurant! ") == "a2b veg restaurant"
    assert normalize_name_string("M/s Sri Krishna & Sons") == "m s sri krishna sons"
    assert normalize_name_string(None) == ""
    assert normalize_name_string("") == ""
