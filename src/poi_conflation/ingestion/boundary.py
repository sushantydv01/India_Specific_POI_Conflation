"""Boundary management and spatial validation for Bengaluru (BBMP)."""

import json
from pathlib import Path
from typing import Tuple, Dict, Any, List
from shapely.geometry import shape, Polygon
import shapely.ops as ops
import pyproj


class BBMPBoundary:
    """Manages the official Bruhat Bengaluru Mahanagara Palike (BBMP) administrative boundary."""

    def __init__(self, boundary_path: str = "configs/bbmp_boundary.geojson"):
        self.boundary_path = Path(boundary_path)
        if not self.boundary_path.exists():
            raise FileNotFoundError(f"Boundary file not found at: {self.boundary_path}")
        
        with open(self.boundary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.metadata = data.get("metadata", {})
        features = data.get("features", [])
        if not features:
            raise ValueError(f"No features found in boundary file: {self.boundary_path}")
            
        self.polygon: Polygon = shape(features[0]["geometry"])
        if not self.polygon.is_valid:
            raise ValueError("BBMP Boundary geometry is topologically invalid!")

        self.min_lon, self.min_lat, self.max_lon, self.max_lat = self.polygon.bounds
        self._transformer = pyproj.Transformer.from_crs(
            "EPSG:4326", "EPSG:32643", always_xy=True
        )

    @property
    def wkt(self) -> str:
        """Return WKT string of the boundary polygon."""
        return self.polygon.wkt

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Return bounding box (min_lon, min_lat, max_lon, max_lat)."""
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)

    def calculate_projected_area_km2(self) -> float:
        """Calculate polygon area in square kilometers projected to UTM Zone 43N (EPSG:32643)."""
        import shapely
        projected_poly = shapely.transform(
            self.polygon, self._transformer.transform, interleaved=False
        )
        return round(projected_poly.area / 1e6, 2)

    def contains_point(self, lon: float, lat: float) -> bool:
        """Check if a coordinate point (lon, lat) lies strictly within the BBMP polygon."""
        from shapely.geometry import Point
        # Quick bounding box pre-filter
        if not (self.min_lon <= lon <= self.max_lon and self.min_lat <= lat <= self.max_lat):
            return False
        return self.polygon.contains(Point(lon, lat))
