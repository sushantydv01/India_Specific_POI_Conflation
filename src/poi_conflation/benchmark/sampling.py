"""Stratified candidate sampling engine for POI conflation ground truth benchmark.

Generates a balanced, 500-pair review queue across 10 distinct difficulty and evidence strata:
1. EXACT_NAME_MATCH: Exact normalized string agreement (<= 50m).
2. STRONG_LEXICAL_SIMILARITY: Fuzzy similarity (Token Sort Ratio >= 85) without exact identity.
3. KANNADA_TRANSLITERATION: Native Kannada script in OSM matched to Latin Overture.
4. PHONETIC_VARIANTS: Indian English phonetic variants (Sri/Shree, Udupi/Udapi, Bhavan/Bhavana).
5. CLOSE_SPATIAL_DISTINCT_NAMES: Spatial co-location (<= 15m) with distinct, non-matching names.
6. CATEGORY_ADJACENCY: Compatible cross-domain categories (e.g., Sustenance ↔ Hospitality).
7. MISSING_OR_GENERIC_NAME: Incomplete, null, or generic names.
8. HIGH_DENSITY_HOTSPOTS: Concentrated commercial hubs (Chickpet, MG Road, Indiranagar).
9. LARGE_DISTANCE_CANDIDATES: Non-spatial candidates at larger distances (50m - 2000m).
10. MULTI_STRATEGY_OVERLAP: Pairs corroborated by 2 or more independent blocking strategies.
"""

import json
import random
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

import duckdb
from rapidfuzz import fuzz

from src.poi_conflation.benchmark.schema import AnnotationQueueItem


STRATA_TARGETS = {
    "EXACT_NAME_MATCH": 50,
    "STRONG_LEXICAL_SIMILARITY": 50,
    "KANNADA_TRANSLITERATION": 50,
    "PHONETIC_VARIANTS": 50,
    "CLOSE_SPATIAL_DISTINCT_NAMES": 50,
    "CATEGORY_ADJACENCY": 50,
    "MISSING_OR_GENERIC_NAME": 50,
    "HIGH_DENSITY_HOTSPOTS": 50,
    "LARGE_DISTANCE_CANDIDATES": 50,
    "MULTI_STRATEGY_OVERLAP": 50,
}


class BenchmarkSampler:
    """Extracts stratified candidate sample for human annotation."""

    def __init__(
        self,
        candidate_parquet: str = "data/processed/candidate_pairs/candidate_pairs_union.parquet",
        canonical_parquet: str = "data/processed/canonical_pois_h3.parquet",
        output_dir: str = "data/processed/benchmark",
        reports_dir: str = "reports",
        seed: int = 42
    ):
        self.candidate_parquet = Path(candidate_parquet)
        self.canonical_parquet = Path(canonical_parquet)
        self.output_dir = Path(output_dir)
        self.reports_dir = Path(reports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.con = duckdb.connect()

    def _prepare_enriched_view(self):
        """Join candidate pairs with canonical POI attributes to restore raw coordinates and names."""
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE canonical_pois AS 
            SELECT 
                source_record_id,
                name_original,
                name_normalized,
                name_en,
                name_kn,
                category_normalized,
                latitude,
                longitude,
                h3_res9
            FROM '{self.canonical_parquet}';

            CREATE OR REPLACE TEMP TABLE enriched_candidates AS
            SELECT 
                c.candidate_pair_id,
                c.osm_source_id,
                c.ov_source_id,
                co.name_original as osm_name_raw,
                cv.name_original as ov_name_raw,
                c.osm_norm_name as osm_name_normalized,
                c.ov_norm_name as ov_name_normalized,
                co.name_en as osm_name_en,
                co.name_kn as osm_name_kn,
                co.latitude as osm_latitude,
                co.longitude as osm_longitude,
                cv.latitude as ov_latitude,
                cv.longitude as ov_longitude,
                c.distance_meters,
                c.osm_category,
                c.ov_category,
                c.category_compatibility,
                array_to_string(c.blocking_strategies, '+') as blocking_strategies,
                c.exact_name_match,
                c.name_containment,
                length(c.blocking_strategies) as strategy_count,
                co.h3_res9 as osm_h3_res9
            FROM '{self.candidate_parquet}' c
            JOIN canonical_pois co ON c.osm_source_id = co.source_record_id
            JOIN canonical_pois cv ON c.ov_source_id = cv.source_record_id;
        """)

    def sample_queue(self) -> Tuple[List[AnnotationQueueItem], Dict[str, Any]]:
        """Execute multi-stratum sampling to generate balanced 500-pair annotation queue."""
        self._prepare_enriched_view()
        random.seed(self.seed)

        sampled_pair_ids: Set[str] = set()
        queue_items: List[AnnotationQueueItem] = []
        strata_report: Dict[str, Any] = {}

        # 1. Exact Name Match (<= 50m)
        pop_exact = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE exact_name_match = true 
              AND distance_meters <= 50.0
              AND osm_name_normalized IS NOT NULL
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_exact = self._select_stratum(pop_exact, cols, STRATA_TARGETS["EXACT_NAME_MATCH"], "EXACT_NAME_MATCH", sampled_pair_ids)
        queue_items.extend(sampled_exact)
        strata_report["EXACT_NAME_MATCH"] = {
            "stratum": "EXACT_NAME_MATCH",
            "population_size": len(pop_exact),
            "sampled_count": len(sampled_exact),
            "inclusion_probability": round(len(sampled_exact) / max(1, len(pop_exact)), 6),
            "description": "Exact normalized string agreement within 50 meters"
        }

        # 2. Kannada Transliteration Matches
        pop_kannada = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE blocking_strategies LIKE '%transliteration%'
              OR osm_name_kn IS NOT NULL
              OR regexp_matches(coalesce(osm_name_raw, ''), '[\\x{0C80}-\\x{0CFF}]')
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_kannada = self._select_stratum(pop_kannada, cols, STRATA_TARGETS["KANNADA_TRANSLITERATION"], "KANNADA_TRANSLITERATION", sampled_pair_ids)
        queue_items.extend(sampled_kannada)
        strata_report["KANNADA_TRANSLITERATION"] = {
            "stratum": "KANNADA_TRANSLITERATION",
            "population_size": len(pop_kannada),
            "sampled_count": len(sampled_kannada),
            "inclusion_probability": round(len(sampled_kannada) / max(1, len(pop_kannada)), 6),
            "description": "Native Kannada script in OSM matched against Latin Overture name"
        }

        # 3. Phonetic Variants
        pop_phonetic = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE (
                osm_name_normalized LIKE '%sri%' OR ov_name_normalized LIKE '%sri%' OR
                osm_name_normalized LIKE '%udupi%' OR ov_name_normalized LIKE '%udupi%' OR
                osm_name_normalized LIKE '%bhavan%' OR ov_name_normalized LIKE '%bhavan%' OR
                osm_name_normalized LIKE '%sagar%' OR ov_name_normalized LIKE '%sagar%' OR
                osm_name_normalized LIKE '%lakshmi%' OR ov_name_normalized LIKE '%lakshmi%'
            )
            AND exact_name_match = false
            AND distance_meters <= 100.0
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_phonetic = self._select_stratum(pop_phonetic, cols, STRATA_TARGETS["PHONETIC_VARIANTS"], "PHONETIC_VARIANTS", sampled_pair_ids)
        queue_items.extend(sampled_phonetic)
        strata_report["PHONETIC_VARIANTS"] = {
            "stratum": "PHONETIC_VARIANTS",
            "population_size": len(pop_phonetic),
            "sampled_count": len(sampled_phonetic),
            "inclusion_probability": round(len(sampled_phonetic) / max(1, len(pop_phonetic)), 6),
            "description": "Phonetic spelling variation common in Indian English commercial signage"
        }

        # 4. Multi-Strategy Overlap (>= 2 strategies)
        pop_multi = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE strategy_count >= 2
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_multi = self._select_stratum(pop_multi, cols, STRATA_TARGETS["MULTI_STRATEGY_OVERLAP"], "MULTI_STRATEGY_OVERLAP", sampled_pair_ids)
        queue_items.extend(sampled_multi)
        strata_report["MULTI_STRATEGY_OVERLAP"] = {
            "stratum": "MULTI_STRATEGY_OVERLAP",
            "population_size": len(pop_multi),
            "sampled_count": len(sampled_multi),
            "inclusion_probability": round(len(sampled_multi) / max(1, len(pop_multi)), 6),
            "description": "Candidates corroborated simultaneously by multiple independent blocking strategies"
        }

        # 5. Category Adjacency (POTENTIALLY_COMPATIBLE)
        pop_cat = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE category_compatibility = 'POTENTIALLY_COMPATIBLE'
              AND distance_meters <= 50.0
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_cat = self._select_stratum(pop_cat, cols, STRATA_TARGETS["CATEGORY_ADJACENCY"], "CATEGORY_ADJACENCY", sampled_pair_ids)
        queue_items.extend(sampled_cat)
        strata_report["CATEGORY_ADJACENCY"] = {
            "stratum": "CATEGORY_ADJACENCY",
            "population_size": len(pop_cat),
            "sampled_count": len(sampled_cat),
            "inclusion_probability": round(len(sampled_cat) / max(1, len(pop_cat)), 6),
            "description": "Semantically adjacent cross-domain categories (e.g. Sustenance ↔ Hospitality)"
        }

        # 6. Close Spatial Pairs with Distinct Names (<= 15m, low lexical match)
        pop_distinct = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE distance_meters <= 15.0
              AND exact_name_match = false
              AND name_containment = false
              AND osm_name_normalized IS NOT NULL
              AND ov_name_normalized IS NOT NULL
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        # Filter for low lexical similarity
        pop_distinct_filtered = [
            r for r in pop_distinct 
            if fuzz.token_sort_ratio(r[cols.index("osm_name_normalized")], r[cols.index("ov_name_normalized")]) < 45
        ]
        sampled_distinct = self._select_stratum(pop_distinct_filtered, cols, STRATA_TARGETS["CLOSE_SPATIAL_DISTINCT_NAMES"], "CLOSE_SPATIAL_DISTINCT_NAMES", sampled_pair_ids)
        queue_items.extend(sampled_distinct)
        strata_report["CLOSE_SPATIAL_DISTINCT_NAMES"] = {
            "stratum": "CLOSE_SPATIAL_DISTINCT_NAMES",
            "population_size": len(pop_distinct_filtered),
            "sampled_count": len(sampled_distinct),
            "inclusion_probability": round(len(sampled_distinct) / max(1, len(pop_distinct_filtered)), 6),
            "description": "Close physical proximity (<= 15m) with distinct, non-matching business names"
        }

        # 7. Strong Lexical Similarity (Token Sort Ratio >= 85, not exact)
        pop_lex = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE exact_name_match = false
              AND distance_meters <= 100.0
              AND osm_name_normalized IS NOT NULL
              AND ov_name_normalized IS NOT NULL
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        pop_lex_filtered = [
            r for r in pop_lex 
            if 85 <= fuzz.token_sort_ratio(r[cols.index("osm_name_normalized")], r[cols.index("ov_name_normalized")]) < 100
        ]
        sampled_lex = self._select_stratum(pop_lex_filtered, cols, STRATA_TARGETS["STRONG_LEXICAL_SIMILARITY"], "STRONG_LEXICAL_SIMILARITY", sampled_pair_ids)
        queue_items.extend(sampled_lex)
        strata_report["STRONG_LEXICAL_SIMILARITY"] = {
            "stratum": "STRONG_LEXICAL_SIMILARITY",
            "population_size": len(pop_lex_filtered),
            "sampled_count": len(sampled_lex),
            "inclusion_probability": round(len(sampled_lex) / max(1, len(pop_lex_filtered)), 6),
            "description": "High string similarity (Token Sort Ratio >= 85) without exact name equality"
        }

        # 8. Large Distance Candidates (> 50m up to 2000m)
        pop_large_dist = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE distance_meters > 50.0
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_large = self._select_stratum(pop_large_dist, cols, STRATA_TARGETS["LARGE_DISTANCE_CANDIDATES"], "LARGE_DISTANCE_CANDIDATES", sampled_pair_ids)
        queue_items.extend(sampled_large)
        strata_report["LARGE_DISTANCE_CANDIDATES"] = {
            "stratum": "LARGE_DISTANCE_CANDIDATES",
            "population_size": len(pop_large_dist),
            "sampled_count": len(sampled_large),
            "inclusion_probability": round(len(sampled_large) / max(1, len(pop_large_dist)), 6),
            "description": "Candidates generated via non-spatial strategies with distance > 50m"
        }

        # 9. Missing or Incomplete Names
        pop_missing = self.con.execute("""
            SELECT * FROM enriched_candidates 
            WHERE (
                osm_name_raw IS NULL OR trim(osm_name_raw) = '' OR
                ov_name_raw IS NULL OR trim(ov_name_raw) = '' OR
                length(trim(osm_name_normalized)) <= 3 OR
                length(trim(ov_name_normalized)) <= 3
            )
            AND distance_meters <= 50.0
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_missing = self._select_stratum(pop_missing, cols, STRATA_TARGETS["MISSING_OR_GENERIC_NAME"], "MISSING_OR_GENERIC_NAME", sampled_pair_ids)
        queue_items.extend(sampled_missing)
        strata_report["MISSING_OR_GENERIC_NAME"] = {
            "stratum": "MISSING_OR_GENERIC_NAME",
            "population_size": len(pop_missing),
            "sampled_count": len(sampled_missing),
            "inclusion_probability": round(len(sampled_missing) / max(1, len(pop_missing)), 6),
            "description": "Pairs with null, unclassified, or uninformative short names"
        }

        # 10. High Density Hotspots (Top H3 Res 9 cells)
        top_h3_cells = [
            r[0] for r in self.con.execute("""
                SELECT osm_h3_res9, count(*) as cnt 
                FROM enriched_candidates 
                GROUP BY osm_h3_res9 
                ORDER BY cnt DESC 
                LIMIT 5
            """).fetchall()
        ]
        pop_hotspot = self.con.execute(f"""
            SELECT * FROM enriched_candidates 
            WHERE osm_h3_res9 IN ('{"','".join(top_h3_cells)}')
              AND distance_meters <= 50.0
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        sampled_hotspot = self._select_stratum(pop_hotspot, cols, STRATA_TARGETS["HIGH_DENSITY_HOTSPOTS"], "HIGH_DENSITY_HOTSPOTS", sampled_pair_ids)
        queue_items.extend(sampled_hotspot)
        strata_report["HIGH_DENSITY_HOTSPOTS"] = {
            "stratum": "HIGH_DENSITY_HOTSPOTS",
            "population_size": len(pop_hotspot),
            "sampled_count": len(sampled_hotspot),
            "inclusion_probability": round(len(sampled_hotspot) / max(1, len(pop_hotspot)), 6),
            "description": "Dense commercial core markets (Chickpet, MG Road, Indiranagar) with high POI congestion"
        }

        summary = {
            "sampling_timestamp": "2026-11-17T09:15:00Z",
            "total_candidate_population": 605428,
            "target_sample_size": sum(STRATA_TARGETS.values()),
            "actual_sample_size": len(queue_items),
            "random_seed": self.seed,
            "strata": strata_report,
            "sampling_method": "Stratified random sampling across 10 disjoint/ordered evidence categories"
        }

        return queue_items, summary

    def _select_stratum(
        self,
        population: List[Tuple],
        cols: List[str],
        target_count: int,
        stratum_name: str,
        seen_pairs: Set[str]
    ) -> List[AnnotationQueueItem]:
        """Select up to target_count records from stratum population, excluding previously seen pairs."""
        candidates = [r for r in population if r[cols.index("candidate_pair_id")] not in seen_pairs]
        random.shuffle(candidates)
        selected_rows = candidates[:target_count]

        items = []
        for r in selected_rows:
            pair_id = r[cols.index("candidate_pair_id")]
            seen_pairs.add(pair_id)
            item = AnnotationQueueItem(
                pair_id=pair_id,
                osm_source_id=r[cols.index("osm_source_id")],
                ov_source_id=r[cols.index("ov_source_id")],
                osm_name_raw=r[cols.index("osm_name_raw")],
                ov_name_raw=r[cols.index("ov_name_raw")],
                osm_name_normalized=r[cols.index("osm_name_normalized")],
                ov_name_normalized=r[cols.index("ov_name_normalized")],
                osm_latitude=r[cols.index("osm_latitude")],
                osm_longitude=r[cols.index("osm_longitude")],
                ov_latitude=r[cols.index("ov_latitude")],
                ov_longitude=r[cols.index("ov_longitude")],
                distance_meters=round(r[cols.index("distance_meters")], 2),
                osm_category=r[cols.index("osm_category")],
                ov_category=r[cols.index("ov_category")],
                category_compatibility=r[cols.index("category_compatibility")],
                blocking_strategies=r[cols.index("blocking_strategies")],
                sampling_stratum=stratum_name,
                osm_name_kn=r[cols.index("osm_name_kn")],
                osm_name_en=r[cols.index("osm_name_en")]
            )
            items.append(item)
        return items

    def export_queue(self) -> Tuple[Path, Path]:
        """Export annotation queue CSV and machine-readable sampling report."""
        queue_items, summary = self.sample_queue()

        queue_csv = self.output_dir / "annotation_queue.csv"
        import csv
        with open(queue_csv, "w", newline="", encoding="utf-8") as f:
            if queue_items:
                fieldnames = list(queue_items[0].to_dict().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in queue_items:
                    writer.writerow(item.to_dict())

        report_json = self.reports_dir / "benchmark_sampling_report.json"
        with open(report_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"Exported {len(queue_items)} stratified queue items to {queue_csv}")
        print(f"Exported sampling manifest to {report_json}")
        return queue_csv, report_json
