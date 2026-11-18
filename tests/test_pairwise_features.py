"""Automated test suite for pairwise POI feature engineering.

Tests:
1. Feature schema integrity, column definitions, and PyArrow schema.
2. Name similarity calculations (exact, Jaro-Winkler, Levenshtein, token sort, char 3-gram, length ratio).
3. Generic and empty name detection.
4. Indic transliteration, Kannada script detection, and Indian English phonetic equivalence.
5. Projected spatial metric calculations (EPSG:32643, distance bands, Delta X/Y, bearing, missing coords).
6. Category compatibility flags and missing category indicators.
7. Candidate blocking strategy feature extraction.
8. End-to-end extractor pipeline execution and Parquet validation.
"""

import math
from pathlib import Path
import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from src.poi_conflation.features.schema import (
    FEATURE_SCHEMA_VERSION,
    ALL_COLUMNS,
    ID_COLUMNS,
    ALL_FEATURE_COLUMNS,
    NAME_FEATURE_COLUMNS,
    TRANSLIT_FEATURE_COLUMNS,
    SPATIAL_FEATURE_COLUMNS,
    CATEGORY_FEATURE_COLUMNS,
    STRATEGY_FEATURE_COLUMNS,
    get_pyarrow_feature_schema,
)
from src.poi_conflation.features.name_features import (
    extract_name_features,
    compute_char_3gram_jaccard,
    is_generic_name,
    is_empty_name,
)
from src.poi_conflation.features.translit_features import (
    extract_translit_features,
    has_kannada,
    has_latin,
)
from src.poi_conflation.features.spatial_features import extract_spatial_features
from src.poi_conflation.features.category_features import extract_category_features
from src.poi_conflation.features.strategy_features import extract_strategy_features
from src.poi_conflation.features.extractor import (
    PairwiseFeatureExtractor,
    extract_pair_features_dict,
)


def test_schema_column_definitions():
    """Verify feature schema column counts and uniqueness."""
    assert len(ID_COLUMNS) == 3
    assert len(NAME_FEATURE_COLUMNS) == 10
    assert len(TRANSLIT_FEATURE_COLUMNS) == 8
    assert len(SPATIAL_FEATURE_COLUMNS) == 12
    assert len(CATEGORY_FEATURE_COLUMNS) == 7
    assert len(STRATEGY_FEATURE_COLUMNS) == 7

    assert len(ALL_FEATURE_COLUMNS) == 44
    assert len(ALL_COLUMNS) == 47
    assert len(set(ALL_COLUMNS)) == 47, "All column names must be unique"

    schema = get_pyarrow_feature_schema()
    assert len(schema) == 47
    for col in ALL_FEATURE_COLUMNS:
        assert schema.field(col).type == pa.float64()


def test_name_features_exact_and_similarity():
    """Verify name similarity metrics on exact and partial matches."""
    feats = extract_name_features("Apollo Pharmacy", "Apollo Pharmacy")
    assert feats["feat_exact_name_match"] == 1.0
    assert feats["feat_jaro_winkler"] == 1.0
    assert feats["feat_levenshtein_sim"] == 1.0
    assert feats["feat_token_sort_ratio"] == 1.0
    assert feats["feat_char_3gram_jaccard"] == 1.0
    assert feats["feat_name_length_ratio"] == 1.0
    assert feats["feat_token_count_diff"] == 0.0
    assert feats["feat_is_empty_name"] == 0.0

    feats_partial = extract_name_features("Cafe Coffee Day Indiranagar", "Cafe Coffee Day")
    assert feats_partial["feat_exact_name_match"] == 0.0
    assert feats_partial["feat_token_set_ratio"] == 1.0
    assert feats_partial["feat_token_count_diff"] == 1.0
    assert feats_partial["feat_name_length_ratio"] < 1.0


def test_generic_and_empty_names():
    """Verify detection of generic business names and empty string handling."""
    assert is_generic_name("Restaurant") is True
    assert is_generic_name("Medical Store") is True
    assert is_generic_name("Darshini Hotel") is True
    assert is_generic_name("Sri Krishna Bhavan") is False  # 'Krishna' is not generic

    feats_empty = extract_name_features("", "Cafe Coffee Day")
    assert feats_empty["feat_is_empty_name"] == 1.0
    assert feats_empty["feat_exact_name_match"] == 0.0
    assert feats_empty["feat_jaro_winkler"] == 0.0


def test_char_3gram_jaccard():
    """Verify character 3-gram calculation and edge cases."""
    assert compute_char_3gram_jaccard("", "") == 0.0
    assert compute_char_3gram_jaccard("ab", "ab") == 1.0
    assert compute_char_3gram_jaccard("ab", "cd") == 0.0
    sim = compute_char_3gram_jaccard("bengaluru", "bangalore")
    assert 0.0 < sim < 1.0


def test_indic_transliteration_features():
    """Verify Kannada script detection, transliteration similarity, and phonetic equivalence."""
    # Native Kannada string: 'ಶ್ರೀ ಸಾಗರ್' (Shree Sagar)
    kn_name = "ಶ್ರೀ ಸಾಗರ್"
    assert has_kannada(kn_name) is True
    assert has_latin(kn_name) is False

    feats = extract_translit_features(
        osm_raw_name=kn_name,
        ov_raw_name="Shree Sagar",
        osm_norm_name="sri sagar",
        ov_norm_name="shree sagar",
    )
    assert feats["feat_osm_has_kannada"] == 1.0
    assert feats["feat_ov_has_kannada"] == 0.0
    assert feats["feat_translit_available"] == 1.0
    assert feats["feat_translit_sim"] > 0.70
    assert feats["feat_indic_phonetic_sim"] == 1.0  # 'shree' -> 'sri'


def test_spatial_features_projection_and_bearing():
    """Verify EPSG:32643 metric spatial features, bands, and bearing."""
    # Point A: (100.0, 100.0), Point B: (100.0, 110.0) -> exactly 10m North
    feats = extract_spatial_features(
        utm_x_osm=100.0,
        utm_y_osm=100.0,
        utm_x_ov=100.0,
        utm_y_ov=110.0,
    )
    assert math.isclose(feats["feat_distance_meters"], 10.0, abs_tol=1e-4)
    assert feats["feat_dist_band_le15m"] == 1.0
    assert feats["feat_dist_band_le30m"] == 1.0
    assert feats["feat_dist_band_le50m"] == 1.0
    assert feats["feat_dist_band_le100m"] == 1.0
    assert math.isclose(feats["feat_delta_x"], 0.0, abs_tol=1e-4)
    assert math.isclose(feats["feat_delta_y"], 10.0, abs_tol=1e-4)
    assert math.isclose(feats["feat_bearing_deg"], 0.0, abs_tol=1e-4)  # Due North
    assert feats["feat_missing_coords"] == 0.0

    # Point B: (110.0, 100.0) -> exactly 10m East (bearing 90 deg)
    feats_east = extract_spatial_features(100.0, 100.0, 110.0, 100.0)
    assert math.isclose(feats_east["feat_bearing_deg"], 90.0, abs_tol=1e-4)

    # Missing coordinates handling
    feats_missing = extract_spatial_features(None, None, 100.0, 100.0)
    assert feats_missing["feat_missing_coords"] == 1.0
    assert feats_missing["feat_bearing_deg"] == -1.0


def test_category_compatibility_features():
    """Verify category one-hot flags and missingness indicators."""
    feats_exact = extract_category_features("healthcare", "healthcare")
    assert feats_exact["feat_exact_category_match"] == 1.0
    assert feats_exact["feat_category_strongly_compat"] == 1.0
    assert feats_exact["feat_category_incompatible"] == 0.0
    assert feats_exact["feat_osm_category_missing"] == 0.0

    feats_incompat = extract_category_features("healthcare", "sustenance")
    assert feats_incompat["feat_category_incompatible"] == 1.0
    assert feats_incompat["feat_exact_category_match"] == 0.0

    feats_other = extract_category_features("other", "retail")
    assert feats_other["feat_category_unknown_compat"] == 1.0
    assert feats_other["feat_osm_category_missing"] == 1.0


def test_strategy_features():
    """Verify blocking strategy indicators."""
    strats = ["spatial_50m", "exact_name"]
    feats = extract_strategy_features(strats)
    assert feats["feat_strat_spatial_50m"] == 1.0
    assert feats["feat_strat_exact_name"] == 1.0
    assert feats["feat_strat_token_containment"] == 0.0
    assert feats["feat_strategy_count"] == 2.0
    assert feats["feat_multi_strategy_overlap"] == 1.0


def test_extracted_features_parquet_exists_and_valid():
    """Verify that generated Parquet dataset matches exact candidate pair count and schema."""
    parquet_path = Path("data/processed/features/pairwise_features.parquet")
    assert parquet_path.exists(), "Pairwise features parquet file must exist"

    table = pq.read_table(str(parquet_path))
    assert table.num_rows == 605428, "Features parquet must contain exactly 605,428 candidate pairs"
    assert table.num_columns == 47, "Features parquet must contain 47 columns (3 IDs + 44 features)"

    # Check for zero nulls across all feature columns
    for col in ALL_FEATURE_COLUMNS:
        assert table[col].null_count == 0, f"Feature {col} must have 0 null values"
