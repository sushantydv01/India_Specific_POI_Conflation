"""Category compatibility feature extraction.

Computes exact category match flags, compatibility levels from the domain matrix,
and missing category indicators for both OSM and Overture.
"""

from typing import Dict, Any, Optional
from src.poi_conflation.blocking.category import (
    CategoryCompatibilityClassifier,
    CategoryCompatibility,
)


def extract_category_features(
    osm_cat: Optional[str],
    ov_cat: Optional[str],
    precomputed_compat: Optional[str] = None,
) -> Dict[str, float]:
    """Extract all 7 category compatibility features."""
    c1 = (osm_cat or "").strip().lower()
    c2 = (ov_cat or "").strip().lower()

    osm_missing = 1.0 if (not c1 or c1 == "other") else 0.0
    ov_missing = 1.0 if (not c2 or c2 == "other") else 0.0

    exact_cat_match = 1.0 if (c1 == c2 and c1 != "other" and c1 != "") else 0.0

    if precomputed_compat:
        compat_val = precomputed_compat
    else:
        compat_enum, _ = CategoryCompatibilityClassifier.evaluate(c1, c2)
        compat_val = compat_enum.value

    return {
        "feat_exact_category_match": exact_cat_match,
        "feat_category_strongly_compat": 1.0 if compat_val == CategoryCompatibility.STRONGLY_COMPATIBLE.value else 0.0,
        "feat_category_potentially_compat": 1.0 if compat_val == CategoryCompatibility.POTENTIALLY_COMPATIBLE.value else 0.0,
        "feat_category_unknown_compat": 1.0 if compat_val == CategoryCompatibility.COMPATIBLE_UNKNOWN.value else 0.0,
        "feat_category_incompatible": 1.0 if compat_val == CategoryCompatibility.INCOMPATIBLE.value else 0.0,
        "feat_osm_category_missing": osm_missing,
        "feat_ov_category_missing": ov_missing,
    }
