"""Projected spatial metric and directional feature extraction.

Computes EPSG:32643 UTM 43N Euclidean distances, distance bands, log distance,
coordinate offsets (Delta X, Delta Y), and clockwise bearing from North.
"""

import math
from typing import Dict, Any, Optional


def extract_spatial_features(
    utm_x_osm: Optional[float],
    utm_y_osm: Optional[float],
    utm_x_ov: Optional[float],
    utm_y_ov: Optional[float],
) -> Dict[str, float]:
    """Extract all 12 spatial metric features from projected UTM 43N coordinates."""
    if (
        utm_x_osm is None
        or utm_y_osm is None
        or utm_x_ov is None
        or utm_y_ov is None
        or math.isnan(utm_x_osm)
        or math.isnan(utm_y_osm)
        or math.isnan(utm_x_ov)
        or math.isnan(utm_y_ov)
    ):
        return {
            "feat_distance_meters": 999999.0,
            "feat_dist_band_le15m": 0.0,
            "feat_dist_band_le30m": 0.0,
            "feat_dist_band_le50m": 0.0,
            "feat_dist_band_le100m": 0.0,
            "feat_log_distance": math.log1p(999999.0),
            "feat_delta_x": 0.0,
            "feat_delta_y": 0.0,
            "feat_abs_delta_x": 0.0,
            "feat_abs_delta_y": 0.0,
            "feat_bearing_deg": -1.0,
            "feat_missing_coords": 1.0,
        }

    dx = float(utm_x_ov - utm_x_osm)
    dy = float(utm_y_ov - utm_y_osm)
    dist = math.sqrt(dx * dx + dy * dy)
    log_dist = math.log1p(dist)

    band_15 = 1.0 if dist <= 15.0 else 0.0
    band_30 = 1.0 if dist <= 30.0 else 0.0
    band_50 = 1.0 if dist <= 50.0 else 0.0
    band_100 = 1.0 if dist <= 100.0 else 0.0

    # Clockwise bearing from North: dx = sin(theta), dy = cos(theta)
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        bearing = 0.0
    else:
        deg = math.degrees(math.atan2(dx, dy))
        bearing = (deg + 360.0) % 360.0

    return {
        "feat_distance_meters": dist,
        "feat_dist_band_le15m": band_15,
        "feat_dist_band_le30m": band_30,
        "feat_dist_band_le50m": band_50,
        "feat_dist_band_le100m": band_100,
        "feat_log_distance": log_dist,
        "feat_delta_x": dx,
        "feat_delta_y": dy,
        "feat_abs_delta_x": abs(dx),
        "feat_abs_delta_y": abs(dy),
        "feat_bearing_deg": bearing,
        "feat_missing_coords": 0.0,
    }
