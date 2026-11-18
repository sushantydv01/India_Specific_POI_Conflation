"""Feature schema definition for pairwise POI entity resolution.

Defines the canonical schema, types, and groupings for the 44 pairwise conflation features
extracted across candidate pairs in the Bengaluru (BBMP) dataset.
"""

from typing import List, Dict, Any
import pyarrow as pa

FEATURE_SCHEMA_VERSION = "1.0.0"

ID_COLUMNS: List[str] = [
    "candidate_pair_id",
    "osm_source_id",
    "ov_source_id",
]

NAME_FEATURE_COLUMNS: List[str] = [
    "feat_exact_name_match",
    "feat_jaro_winkler",
    "feat_levenshtein_sim",
    "feat_token_sort_ratio",
    "feat_token_set_ratio",
    "feat_char_3gram_jaccard",
    "feat_name_length_ratio",
    "feat_token_count_diff",
    "feat_is_generic_name",
    "feat_is_empty_name",
]

TRANSLIT_FEATURE_COLUMNS: List[str] = [
    "feat_osm_has_kannada",
    "feat_ov_has_kannada",
    "feat_osm_has_latin",
    "feat_ov_has_latin",
    "feat_translit_available",
    "feat_translit_sim",
    "feat_translit_exact_match",
    "feat_indic_phonetic_sim",
]

SPATIAL_FEATURE_COLUMNS: List[str] = [
    "feat_distance_meters",
    "feat_dist_band_le15m",
    "feat_dist_band_le30m",
    "feat_dist_band_le50m",
    "feat_dist_band_le100m",
    "feat_log_distance",
    "feat_delta_x",
    "feat_delta_y",
    "feat_abs_delta_x",
    "feat_abs_delta_y",
    "feat_bearing_deg",
    "feat_missing_coords",
]

CATEGORY_FEATURE_COLUMNS: List[str] = [
    "feat_exact_category_match",
    "feat_category_strongly_compat",
    "feat_category_potentially_compat",
    "feat_category_unknown_compat",
    "feat_category_incompatible",
    "feat_osm_category_missing",
    "feat_ov_category_missing",
]

STRATEGY_FEATURE_COLUMNS: List[str] = [
    "feat_strat_spatial_50m",
    "feat_strat_token_containment",
    "feat_strat_exact_name",
    "feat_strat_translit",
    "feat_strat_phonetic",
    "feat_multi_strategy_overlap",
    "feat_strategy_count",
]

ALL_FEATURE_COLUMNS: List[str] = (
    NAME_FEATURE_COLUMNS
    + TRANSLIT_FEATURE_COLUMNS
    + SPATIAL_FEATURE_COLUMNS
    + CATEGORY_FEATURE_COLUMNS
    + STRATEGY_FEATURE_COLUMNS
)

ALL_COLUMNS: List[str] = ID_COLUMNS + ALL_FEATURE_COLUMNS


def get_pyarrow_feature_schema() -> pa.Schema:
    """Return PyArrow schema for persisting pairwise features to Parquet."""
    fields = [
        pa.field("candidate_pair_id", pa.string(), nullable=False),
        pa.field("osm_source_id", pa.string(), nullable=False),
        pa.field("ov_source_id", pa.string(), nullable=False),
    ]
    for col in ALL_FEATURE_COLUMNS:
        fields.append(pa.field(col, pa.float64(), nullable=False))
    return pa.schema(fields)
