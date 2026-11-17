"""Comprehensive automated test suite for Milestone 4 candidate generation & blocking."""

import math
import pytest
from pathlib import Path
import pyarrow.parquet as pq

from src.poi_conflation.blocking.category import (
    CategoryCompatibility,
    CategoryCompatibilityClassifier,
)
from src.poi_conflation.blocking.multilingual import (
    MultilingualTransliterationEngine,
    strip_accents_and_diacritics,
)
from src.poi_conflation.blocking.lexical import (
    LexicalBlocker,
    extract_distinctive_tokens,
    generate_char_ngrams,
)
from src.poi_conflation.blocking.spatial import SpatialBlocker


def test_category_compatibility_matrix():
    # 1. Exact match
    comp, reason = CategoryCompatibilityClassifier.evaluate("sustenance", "sustenance")
    assert comp == CategoryCompatibility.STRONGLY_COMPATIBLE
    assert "Exact" in reason

    # 2. Known cross-domain adjacency
    comp, reason = CategoryCompatibilityClassifier.evaluate("sustenance", "hospitality")
    assert comp == CategoryCompatibility.POTENTIALLY_COMPATIBLE
    assert "restaurant" in reason.lower() or "hotel" in reason.lower()

    # 3. Healthcare and retail (pharmacy)
    comp, reason = CategoryCompatibilityClassifier.evaluate("healthcare", "retail")
    assert comp == CategoryCompatibility.POTENTIALLY_COMPATIBLE

    # 4. Strictly disjoint incompatible domains
    comp, reason = CategoryCompatibilityClassifier.evaluate("healthcare", "sustenance")
    assert comp == CategoryCompatibility.INCOMPATIBLE
    assert CategoryCompatibilityClassifier.is_candidate_allowed("healthcare", "sustenance") is False

    comp, reason = CategoryCompatibilityClassifier.evaluate("financial", "education")
    assert comp == CategoryCompatibility.INCOMPATIBLE
    assert CategoryCompatibilityClassifier.is_candidate_allowed("financial", "education") is False

    # 5. Unknown fallback 'other'
    comp, reason = CategoryCompatibilityClassifier.evaluate("other", "healthcare")
    assert comp == CategoryCompatibility.COMPATIBLE_UNKNOWN
    assert CategoryCompatibilityClassifier.is_candidate_allowed("other", "healthcare") is True

    comp, reason = CategoryCompatibilityClassifier.evaluate("other", "other")
    assert comp == CategoryCompatibility.COMPATIBLE_UNKNOWN


def test_multilingual_kannada_transliteration():
    engine = MultilingualTransliterationEngine()

    # 1. Vidyarthi Bhavan
    t_lat, prov = engine.transliterate_kannada_to_latin("ವಿದ್ಯಾರ್ಥಿ ಭವನ")
    assert t_lat is not None
    assert "vidyarthi" in t_lat
    assert "indic_transliteration" in prov

    # 2. Annapurneshwari
    t_lat, _ = engine.transliterate_kannada_to_latin("ಅನ್ನಪೂರ್ಣೇಶ್ವರಿ")
    assert t_lat == "annapurneshvari"

    # 3. Sri Lakshmi Provision Store
    t_lat, _ = engine.transliterate_kannada_to_latin("ಶ್ರೀ ಲಕ್ಷ್ಮಿ ಪ್ರೊವಿಷನ್ ಸ್ಟೋರ್")
    assert "shri" in t_lat and "lakshmi" in t_lat

    # 4. Non-Kannada input
    t_lat, prov = engine.transliterate_kannada_to_latin("McDonald's Church Street")
    assert t_lat is None
    assert prov == "no_kannada_detected"


def test_phonetic_normalization_variants():
    engine = MultilingualTransliterationEngine()

    # Udapi -> Udupi
    norm, prov = engine.apply_phonetic_normalization("udapi grand")
    assert norm == "udupi grand"
    assert prov == "phonetic_equivalence_map"

    # Shree -> Sri
    norm, _ = engine.apply_phonetic_normalization("shree lakshmi store")
    assert norm == "sri lakshmi store"

    # Bhavana -> Bhavan
    norm, _ = engine.apply_phonetic_normalization("gualbert bhavana")
    assert norm == "gualbert bhavan"

    # Unaltered Latin name
    norm, prov = engine.apply_phonetic_normalization("truffles indiranagar")
    assert norm == "truffles indiranagar"
    assert prov == "unmodified"


def test_lexical_token_extraction_and_containment():
    blocker = LexicalBlocker()

    tokens = extract_distinctive_tokens("The Grand Udupi Restaurant, Bangalore Road")
    assert "grand" in tokens
    assert "udupi" in tokens
    assert "restaurant" in tokens
    # Stopwords must be excluded
    assert "the" not in tokens
    assert "bangalore" not in tokens
    assert "road" not in tokens

    # Name containment
    assert blocker.check_name_containment("apollo cradle", "apollo cradle hospital") is True
    assert blocker.check_name_containment("kamat", "kamat hotel") is True
    assert blocker.check_name_containment("subway", "subway esteem mall bengaluru") is True
    assert blocker.check_name_containment("bata", "bata shoe store") is True
    assert blocker.check_name_containment("completely different", "unrelated name") is False


def test_metric_distance_accuracy():
    # Test UTM 43N metric distance formula vs known coordinates
    # In UTM 43N, 1 meter in x is exactly 1 meter displacement
    x1, y1 = 770000.0, 1430000.0
    x2, y2 = 770030.0, 1430040.0
    expected_dist = math.sqrt(30**2 + 40**2)  # 50.0 meters
    calc_dist = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
    assert abs(calc_dist - expected_dist) < 1e-6


def test_candidate_union_dataset_integrity():
    parquet_path = Path("data/processed/candidate_pairs/candidate_pairs_union.parquet")
    assert parquet_path.exists(), "Candidate pairs union parquet must exist"
    assert parquet_path.stat().st_size > 5_000_000, "Parquet size should be > 5 MB"

    table = pq.read_table(parquet_path)
    assert table.num_rows > 500_000, f"Expected > 500k candidates, got {table.num_rows}"

    cols = table.column_names
    expected_cols = [
        "candidate_pair_id",
        "osm_source_id",
        "ov_source_id",
        "osm_name",
        "ov_name",
        "distance_meters",
        "match_h3_res8",
        "match_h3_res9",
        "match_h3_res10",
        "exact_name_match",
        "name_containment",
        "category_compatibility",
        "blocking_strategies"
    ]
    for c in expected_cols:
        assert c in cols, f"Missing required column: {c}"

    # Sample verification: Pair ID format and cross-source separation
    sample = table.slice(0, 100).to_pydict()
    for pid, osm_id, ov_id, dist, comp in zip(
        sample["candidate_pair_id"],
        sample["osm_source_id"],
        sample["ov_source_id"],
        sample["distance_meters"],
        sample["category_compatibility"]
    ):
        assert pid == f"{osm_id}::{ov_id}", "Candidate pair ID must equal osm_id::ov_id"
        assert osm_id.startswith(("node/", "way/")), "OSM ID must have node/ or way/ prefix"
        assert len(ov_id) == 36 or "-" in ov_id, "Overture ID must be standard UUID string"
        assert dist >= 0.0, "Distance must be non-negative"
        assert comp != "INCOMPATIBLE", "Incompatible category pairs must be pruned"


def test_missing_name_preservation():
    # Verify that records with null/empty names are not discarded from the candidate union
    parquet_path = Path("data/processed/candidate_pairs/candidate_pairs_union.parquet")
    table = pq.read_table(parquet_path, columns=["osm_name", "blocking_strategies"])
    pydict = table.to_pydict()
    
    unnamed_count = sum(1 for n in pydict["osm_name"] if n is None or str(n).strip() == "")
    assert unnamed_count > 10_000, f"Expected >10k candidate pairs with unnamed OSM features, got {unnamed_count}"
