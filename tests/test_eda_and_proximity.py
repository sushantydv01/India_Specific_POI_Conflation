"""Automated tests for exploratory data analysis, spatial proximity, and lexical profiling."""

import pytest
import math
from src.poi_conflation.analysis.eda import EDAAnalyzer
from src.poi_conflation.analysis.spatial_proximity import SpatialProximityAnalyzer
from src.poi_conflation.analysis.naming_profiler import (
    jaccard_similarity,
    char_ngram_similarity,
    NamingProfiler,
)


def test_lexical_similarity_metrics():
    # Identical strings
    assert jaccard_similarity("Vidyarthi Bhavan", "Vidyarthi Bhavan") == 1.0
    assert char_ngram_similarity("Vidyarthi Bhavan", "Vidyarthi Bhavan") == 1.0

    # Token reordering
    assert jaccard_similarity("Adyar Ananda Bhavan", "Bhavan Ananda Adyar") == 1.0

    # Partial overlap
    s1 = "Apollo Hospital Bannerghatta"
    s2 = "Apollo Clinic"
    assert 0.0 < jaccard_similarity(s1, s2) < 1.0
    assert 0.0 < char_ngram_similarity(s1, s2) < 1.0

    # Completely disjoint
    assert jaccard_similarity("Udupi Grand", "Sobha PalmCourt") == 0.0
    assert char_ngram_similarity("Udupi Grand", "Sobha PalmCourt") == 0.0

    # Empty string edge cases
    assert jaccard_similarity("", "Test") == 0.0
    assert char_ngram_similarity("", "Test") == 0.0


def test_eda_source_statistics_consistency():
    analyzer = EDAAnalyzer()
    stats = analyzer.run_source_statistics()

    assert "OSM" in stats
    assert "OVERTURE" in stats

    osm = stats["OSM"]
    ov = stats["OVERTURE"]

    assert osm["total_pois"] == 49_036
    assert ov["total_pois"] == 197_820
    assert osm["named_pois"] == 34_865
    assert ov["named_pois"] == 197_820
    assert osm["missing_coordinates"] == 0
    assert ov["missing_coordinates"] == 0


def test_category_distribution_counts():
    analyzer = EDAAnalyzer()
    cat_res = analyzer.run_category_analysis()
    categories = cat_res["canonical_categories"]

    total_sum = sum(c["total_count"] for c in categories)
    assert total_sum == 246_856, f"Expected 246,856 total categorized records, got {total_sum}"

    # Verify each category has non-zero count
    for c in categories:
        assert c["total_count"] > 0, f"Category {c['category']} should have >0 records"


def test_spatial_proximity_monotonic_growth():
    analyzer = SpatialProximityAnalyzer()
    summary = analyzer.run_analysis()
    thresholds = summary["distance_thresholds"]

    # Candidate pairs and matched counts must monotonically increase with distance threshold
    prev_pairs = 0
    prev_osm = 0
    for t in thresholds:
        assert t["total_candidate_pairs"] >= prev_pairs, "Pair count must grow with distance threshold"
        assert t["osm_records_with_candidates"] >= prev_osm, "Matched OSM count must grow with distance threshold"
        prev_pairs = t["total_candidate_pairs"]
        prev_osm = t["osm_records_with_candidates"]


def test_naming_script_distributions():
    profiler = NamingProfiler()
    scripts = profiler.run_script_distribution()

    osm = scripts["OSM"]
    ov = scripts["OVERTURE"]

    assert osm["has_kannada_script"] == 6_223
    assert osm["has_both_kannada_and_english"] == 6_190
    assert ov["has_kannada_script"] == 400
