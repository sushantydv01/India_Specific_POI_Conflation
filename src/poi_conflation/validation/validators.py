"""Data validation rules for POI ingestion and canonical records."""

from typing import List, Dict, Any, Tuple
from src.poi_conflation.ingestion.boundary import BBMPBoundary
from src.poi_conflation.models.categories import CANONICAL_CATEGORIES


class POIValidator:
    """Validates raw and canonical POI records against geographic and schema rules."""

    def __init__(self, boundary: BBMPBoundary = None):
        self.boundary = boundary or BBMPBoundary()

    def validate_coordinates(self, lat: float, lon: float) -> Tuple[bool, str]:
        """Validate that coordinates are realistic geographic coordinates."""
        if lat is None or lon is None:
            return False, "Null coordinates"
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return False, f"Coordinate range out of bounds: ({lat}, {lon})"
        if lat == 0.0 and lon == 0.0:
            return False, "Null island (0, 0) coordinates"
        return True, "OK"

    def validate_boundary_containment(self, lat: float, lon: float) -> Tuple[bool, str]:
        """Validate that the coordinates fall strictly within the BBMP polygon."""
        valid, msg = self.validate_coordinates(lat, lon)
        if not valid:
            return False, msg
        if not self.boundary.contains_point(lon, lat):
            return False, f"Coordinates ({lat}, {lon}) fall outside BBMP municipal boundary"
        return True, "OK"

    def validate_canonical_record(self, record: Dict[str, Any]) -> List[str]:
        """Validate a single canonical POI record dictionary against schema rules."""
        errors = []

        # Required non-empty string fields
        for field in ("poi_source", "source_record_id", "source_release", "name_original", "geometry_wkt"):
            val = record.get(field)
            if not val or not str(val).strip():
                errors.append(f"Missing required field: {field}")

        # Source check
        source = record.get("poi_source")
        if source not in ("OSM", "OVERTURE"):
            errors.append(f"Invalid poi_source: {source}")

        # Coordinates
        lat = record.get("latitude")
        lon = record.get("longitude")
        is_coord_valid, coord_msg = self.validate_coordinates(lat, lon)
        if not is_coord_valid:
            errors.append(coord_msg)

        # Category
        cat_norm = record.get("category_normalized")
        if cat_norm not in CANONICAL_CATEGORIES:
            errors.append(f"category_normalized '{cat_norm}' not in allowed set")

        return errors

    def validate_canonical_table(self, table) -> Dict[str, Any]:
        """Run complete dataset validation across an Arrow table."""
        num_rows = table.num_rows
        pydict = table.to_pydict()
        
        sources = set(pydict["poi_source"])
        null_names = sum(1 for n in pydict["name_original"] if not n or not str(n).strip())
        
        # Check source id uniqueness per source
        osm_ids = set()
        overture_ids = set()
        dup_osm = 0
        dup_ov = 0

        for i in range(num_rows):
            src = pydict["poi_source"][i]
            sid = pydict["source_record_id"][i]
            if src == "OSM":
                if sid in osm_ids:
                    dup_osm += 1
                osm_ids.add(sid)
            elif src == "OVERTURE":
                if sid in overture_ids:
                    dup_ov += 1
                overture_ids.add(sid)

        return {
            "total_rows": num_rows,
            "sources": list(sources),
            "osm_record_count": len(osm_ids),
            "overture_record_count": len(overture_ids),
            "duplicate_osm_ids": dup_osm,
            "duplicate_overture_ids": dup_ov,
            "null_or_empty_names": null_names,
            "is_valid": (dup_osm == 0 and dup_ov == 0 and null_names == 0)
        }
