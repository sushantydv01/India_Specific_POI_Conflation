"""Pairwise feature engineering package for India-specific POI conflation.

Exposes schema definitions, feature extraction routines, and the batch pipeline.
"""

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
from src.poi_conflation.features.name_features import extract_name_features
from src.poi_conflation.features.translit_features import extract_translit_features
from src.poi_conflation.features.spatial_features import extract_spatial_features
from src.poi_conflation.features.category_features import extract_category_features
from src.poi_conflation.features.strategy_features import extract_strategy_features
from src.poi_conflation.features.extractor import (
    PairwiseFeatureExtractor,
    extract_pair_features_dict,
)

__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "ALL_COLUMNS",
    "ID_COLUMNS",
    "ALL_FEATURE_COLUMNS",
    "NAME_FEATURE_COLUMNS",
    "TRANSLIT_FEATURE_COLUMNS",
    "SPATIAL_FEATURE_COLUMNS",
    "CATEGORY_FEATURE_COLUMNS",
    "STRATEGY_FEATURE_COLUMNS",
    "get_pyarrow_feature_schema",
    "extract_name_features",
    "extract_translit_features",
    "extract_spatial_features",
    "extract_category_features",
    "extract_strategy_features",
    "PairwiseFeatureExtractor",
    "extract_pair_features_dict",
]
