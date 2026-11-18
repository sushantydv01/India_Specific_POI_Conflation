"""Multi-strategy candidate generation and deduplication engine.

Orchestrates:
1. Spatial candidate generation (metric distance <= 50m / 100m via H3 / UTM 43N grid).
2. Exact normalized name matching.
3. Distinctive token overlap matching (within 200m).
4. Substring name containment matching (within 200m).
5. Kannada-to-Latin transliteration matching.
6. Indian English phonetic equivalence matching.
7. Category compatibility filtering (pruning strictly incompatible pairs).
8. Unified deduplicated candidate export with full strategy provenance to Parquet.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from src.poi_conflation.blocking.category import (
    CategoryCompatibility,
    CategoryCompatibilityClassifier,
    DISJOINT_INCOMPATIBLE_PAIRS,
)
from src.poi_conflation.blocking.multilingual import MultilingualTransliterationEngine
from src.poi_conflation.blocking.lexical import extract_distinctive_tokens, generate_char_ngrams


class CandidateEngine:
    """Orchestrates multi-strategy candidate pair generation and unified deduplication."""

    def __init__(
        self,
        dataset_path: str = "data/processed/canonical_pois_h3.parquet",
        output_dir: str = "data/processed/candidate_pairs",
        reports_dir: str = "reports"
    ):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir)
        self.reports_dir = Path(reports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.output_parquet = self.output_dir / "candidate_pairs_union.parquet"
        self.con = duckdb.connect()
        self.con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")
        self.trans_engine = MultilingualTransliterationEngine()

    def _setup_tables(self):
        """Prepare projected tables in DuckDB with UTM coordinates and transliterated names."""
        print("Initializing candidate engine tables and spatial projection...")
        t0 = time.time()
        
        # Load raw dataset into memory table
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE canonical_base AS 
            SELECT * FROM '{self.dataset_path}';

            CREATE OR REPLACE TEMP TABLE osm_tbl AS 
            SELECT 
                canonical_poi_id as osm_poi_id,
                source_record_id as osm_source_id,
                name_original as osm_name,
                name_normalized as osm_norm_name,
                name_en as osm_name_en,
                name_kn as osm_name_kn,
                category_normalized as osm_category,
                h3_res8 as osm_h3_8,
                h3_res9 as osm_h3_9,
                h3_res10 as osm_h3_10,
                latitude as osm_lat,
                longitude as osm_lon,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
            FROM canonical_base
            WHERE poi_source = 'OSM';

            CREATE OR REPLACE TEMP TABLE ov_tbl AS 
            SELECT 
                canonical_poi_id as ov_poi_id,
                source_record_id as ov_source_id,
                name_original as ov_name,
                name_normalized as ov_norm_name,
                category_normalized as ov_category,
                h3_res8 as ov_h3_8,
                h3_res9 as ov_h3_9,
                h3_res10 as ov_h3_10,
                latitude as ov_lat,
                longitude as ov_lon,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y,
                CAST(floor(ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) / 200.0) AS INT) as gx,
                CAST(floor(ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) / 200.0) AS INT) as gy
            FROM canonical_base
            WHERE poi_source = 'OVERTURE';

            -- 3x3 neighboring 200m bins for complete 200m distance coverage
            CREATE OR REPLACE TEMP TABLE grid_offsets (dx INT, dy INT);
            DELETE FROM grid_offsets;
            INSERT INTO grid_offsets VALUES 
                (-1,-1), (-1,0), (-1,1),
                ( 0,-1), ( 0,0), ( 0,1),
                ( 1,-1), ( 1,0), ( 1,1);

            CREATE OR REPLACE TEMP TABLE osm_expanded AS
            SELECT 
                o.*,
                CAST(floor(o.utm_x / 200.0) AS INT) + off.dx as gx,
                CAST(floor(o.utm_y / 200.0) AS INT) + off.dy as gy
            FROM osm_tbl o
            CROSS JOIN grid_offsets off;
        """)
        print(f"Base tables ready in {time.time() - t0:.2f}s")

    def run_multi_strategy_generation(self) -> Dict[str, Any]:
        """Execute all candidate generation strategies and merge into unified deduplicated table."""
        t_start = time.time()
        print("=" * 70)
        print("MULTI-STRATEGY CANDIDATE GENERATION & BLOCKING")
        print("=" * 70)

        self._setup_tables()

        # Build Incompatible Category Clause for DuckDB
        incompat_conditions = []
        for pair in DISJOINT_INCOMPATIBLE_PAIRS:
            c1, c2 = list(pair)
            incompat_conditions.append(f"(any_value(osm_category) = '{c1}' AND any_value(ov_category) = '{c2}')")
            incompat_conditions.append(f"(any_value(osm_category) = '{c2}' AND any_value(ov_category) = '{c1}')")
        incompat_sql = " OR ".join(incompat_conditions)

        # 1. Strategy A: Spatial Candidates (<= 50m)
        print("\n[Strategy 1/5] Evaluating Spatial Proximity (distance <= 50m)...")
        t0 = time.time()
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE cand_spatial_50m AS
            SELECT 
                o.osm_source_id,
                v.ov_source_id,
                o.osm_name,
                o.osm_norm_name,
                o.osm_category,
                v.ov_name,
                v.ov_norm_name,
                v.ov_category,
                (o.osm_h3_8 = v.ov_h3_8) as match_h3_res8,
                (o.osm_h3_9 = v.ov_h3_9) as match_h3_res9,
                (o.osm_h3_10 = v.ov_h3_10) as match_h3_res10,
                round(sqrt((o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y)), 2) as distance_meters,
                'spatial_50m' as strategy
            FROM osm_expanded o
            JOIN ov_tbl v ON o.gx = v.gx AND o.gy = v.gy
            WHERE (o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y) <= 2500.0;
        """)
        c_spatial = self.con.execute("SELECT count(*) FROM cand_spatial_50m").fetchone()[0]
        print(f"  Generated {c_spatial:,} spatial candidate pairs in {time.time() - t0:.2f}s")

        # 2. Strategy B: Exact Normalized Name Blocking
        print("\n[Strategy 2/5] Evaluating Exact Normalized Name Blocking...")
        t0 = time.time()
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE cand_exact_name AS
            SELECT 
                o.osm_source_id,
                v.ov_source_id,
                o.osm_name,
                o.osm_norm_name,
                o.osm_category,
                v.ov_name,
                v.ov_norm_name,
                v.ov_category,
                (o.osm_h3_8 = v.ov_h3_8) as match_h3_res8,
                (o.osm_h3_9 = v.ov_h3_9) as match_h3_res9,
                (o.osm_h3_10 = v.ov_h3_10) as match_h3_res10,
                round(sqrt((o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y)), 2) as distance_meters,
                'exact_name' as strategy
            FROM osm_tbl o
            JOIN ov_tbl v ON o.osm_norm_name = v.ov_norm_name
            WHERE length(trim(o.osm_norm_name)) >= 4
              AND o.osm_norm_name NOT IN ('bank of india', 'state bank of india', 'icici bank', 'hdfc bank', 'axis bank', 'atm', 'temple', 'church', 'mosque')
              AND (o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y) <= 4000000.0; -- within 2km
        """)
        c_exact = self.con.execute("SELECT count(*) FROM cand_exact_name").fetchone()[0]
        print(f"  Generated {c_exact:,} exact name candidate pairs in {time.time() - t0:.2f}s")

        # 3. Strategy C: Name Containment & Token Overlap (distance <= 100m)
        print("\n[Strategy 3/5] Evaluating Name Containment & Token Overlap (distance <= 100m)...")
        t0 = time.time()
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE cand_token_containment AS
            SELECT 
                o.osm_source_id,
                v.ov_source_id,
                o.osm_name,
                o.osm_norm_name,
                o.osm_category,
                v.ov_name,
                v.ov_norm_name,
                v.ov_category,
                (o.osm_h3_8 = v.ov_h3_8) as match_h3_res8,
                (o.osm_h3_9 = v.ov_h3_9) as match_h3_res9,
                (o.osm_h3_10 = v.ov_h3_10) as match_h3_res10,
                round(sqrt((o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y)), 2) as distance_meters,
                'token_containment_100m' as strategy
            FROM osm_expanded o
            JOIN ov_tbl v ON o.gx = v.gx AND o.gy = v.gy
            WHERE (o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y) <= 10000.0 -- within 100m
              AND length(o.osm_norm_name) >= 4 AND length(v.ov_norm_name) >= 4
              AND (
                  contains(v.ov_norm_name, o.osm_norm_name) 
                  OR contains(o.osm_norm_name, v.ov_norm_name)
              );
        """)
        c_contain = self.con.execute("SELECT count(*) FROM cand_token_containment").fetchone()[0]
        print(f"  Generated {c_contain:,} name containment pairs in {time.time() - t0:.2f}s")

        # 4. Strategy D: Kannada Transliteration & Phonetic Variants
        print("\n[Strategy 4/5] Evaluating Transliteration and Phonetic Matching...")
        t0 = time.time()
        # Extract Kannada names in OSM and transliterate in memory, register temp table
        kannada_records = self.con.execute("""
            SELECT osm_source_id, osm_name, osm_norm_name, osm_name_kn
            FROM osm_tbl
            WHERE osm_name_kn IS NOT NULL OR regexp_matches(osm_name, '[\u0C80-\u0CFF]');
        """).fetchall()

        trans_tuples = []
        for sid, name, norm, n_kn in kannada_records:
            source_txt = n_kn or name
            t_lat, _ = self.trans_engine.transliterate_kannada_to_latin(source_txt)
            if t_lat:
                p_norm, _ = self.trans_engine.apply_phonetic_normalization(t_lat)
                trans_tuples.append((sid, t_lat, p_norm))

        self.con.execute("""
            CREATE OR REPLACE TEMP TABLE osm_transliterated (
                osm_source_id VARCHAR,
                transliterated_latin VARCHAR,
                phonetic_norm VARCHAR
            );
        """)
        if trans_tuples:
            self.con.executemany("INSERT INTO osm_transliterated VALUES (?, ?, ?);", trans_tuples)

        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE cand_transliteration AS
            SELECT 
                o.osm_source_id,
                v.ov_source_id,
                o.osm_name,
                o.osm_norm_name,
                o.osm_category,
                v.ov_name,
                v.ov_norm_name,
                v.ov_category,
                (o.osm_h3_8 = v.ov_h3_8) as match_h3_res8,
                (o.osm_h3_9 = v.ov_h3_9) as match_h3_res9,
                (o.osm_h3_10 = v.ov_h3_10) as match_h3_res10,
                round(sqrt((o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y)), 2) as distance_meters,
                'transliteration_phonetic' as strategy
            FROM osm_tbl o
            JOIN osm_transliterated t ON o.osm_source_id = t.osm_source_id
            JOIN ov_tbl v ON (
                t.transliterated_latin = v.ov_norm_name 
                OR t.phonetic_norm = v.ov_norm_name
                OR contains(v.ov_norm_name, t.phonetic_norm)
            )
            WHERE (o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y) <= 400000.0; -- within 630m
        """)
        c_trans = self.con.execute("SELECT count(*) FROM cand_transliteration").fetchone()[0]
        print(f"  Generated {c_trans:,} transliteration/phonetic candidate pairs in {time.time() - t0:.2f}s")

        # 5. Union All Strategies & Compute Feature Columns & Filter Incompatible Categories
        print("\n[Strategy 5/5] Merging Candidates into Unified Deduplicated Dataset...")
        t0 = time.time()
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE raw_candidates_union AS
            SELECT * FROM cand_spatial_50m
            UNION ALL
            SELECT * FROM cand_exact_name
            UNION ALL
            SELECT * FROM cand_token_containment
            UNION ALL
            SELECT * FROM cand_transliteration;
        """)

        # Aggregate strategy provenance per pair and apply category compatibility
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE deduplicated_candidates AS
            SELECT 
                osm_source_id || '::' || ov_source_id as candidate_pair_id,
                osm_source_id,
                ov_source_id,
                any_value(osm_name) as osm_name,
                any_value(osm_norm_name) as osm_norm_name,
                any_value(osm_category) as osm_category,
                any_value(ov_name) as ov_name,
                any_value(ov_norm_name) as ov_norm_name,
                any_value(ov_category) as ov_category,
                min(distance_meters) as distance_meters,
                bool_or(match_h3_res8) as match_h3_res8,
                bool_or(match_h3_res9) as match_h3_res9,
                bool_or(match_h3_res10) as match_h3_res10,
                (any_value(osm_norm_name) = any_value(ov_norm_name) AND length(any_value(osm_norm_name)) >= 3) as exact_name_match,
                (
                    contains(any_value(ov_norm_name), any_value(osm_norm_name)) 
                    OR contains(any_value(osm_norm_name), any_value(ov_norm_name))
                ) as name_containment,
                CASE 
                    WHEN any_value(osm_category) = any_value(ov_category) AND any_value(osm_category) != 'other' THEN 'STRONGLY_COMPATIBLE'
                    WHEN any_value(osm_category) = 'other' OR any_value(ov_category) = 'other' THEN 'COMPATIBLE_UNKNOWN'
                    WHEN {incompat_sql} THEN 'INCOMPATIBLE'
                    ELSE 'POTENTIALLY_COMPATIBLE'
                END as category_compatibility,
                list_distinct(list(strategy)) as blocking_strategies
            FROM raw_candidates_union
            GROUP BY osm_source_id, ov_source_id;
        """)

        # Prune strictly incompatible pairs
        self.con.execute("""
            CREATE OR REPLACE TEMP TABLE final_candidates AS
            SELECT *
            FROM deduplicated_candidates
            WHERE category_compatibility != 'INCOMPATIBLE';
        """)

        total_final = self.con.execute("SELECT count(*) FROM final_candidates").fetchone()[0]
        pruned_incompat = self.con.execute("""
            SELECT count(*) FROM deduplicated_candidates WHERE category_compatibility = 'INCOMPATIBLE';
        """).fetchone()[0]
        print(f"  Deduplicated union: {total_final:,} candidate pairs ({pruned_incompat:,} incompatible pairs pruned) in {time.time() - t0:.2f}s")

        # Export to Parquet
        print(f"Exporting final candidate pairs to {self.output_parquet}...")
        t_exp = time.time()
        self.con.execute(f"""
            COPY final_candidates TO '{self.output_parquet}' (FORMAT PARQUET, COMPRESSION ZSTD);
        """)
        export_time = round(time.time() - t_exp, 2)
        parquet_mb = self.output_parquet.stat().st_size / 1e6
        print(f"Wrote {self.output_parquet} ({parquet_mb:.2f} MB) in {export_time}s")

        # Summary statistics
        stats_q = """
        SELECT 
            count(*) as total_candidates,
            count(distinct osm_source_id) as unique_osm_records,
            count(distinct ov_source_id) as unique_ov_records,
            avg(distance_meters) as avg_distance_m,
            median(distance_meters) as median_distance_m,
            min(distance_meters) as min_distance_m,
            max(distance_meters) as max_distance_m,
            count(CASE WHEN exact_name_match THEN 1 END) as exact_name_pairs,
            count(CASE WHEN name_containment THEN 1 END) as name_containment_pairs,
            count(CASE WHEN category_compatibility = 'STRONGLY_COMPATIBLE' THEN 1 END) as strongly_compat_pairs,
            count(CASE WHEN category_compatibility = 'POTENTIALLY_COMPATIBLE' THEN 1 END) as potentially_compat_pairs,
            count(CASE WHEN category_compatibility = 'COMPATIBLE_UNKNOWN' THEN 1 END) as unknown_compat_pairs
        FROM final_candidates;
        """
        sr = self.con.execute(stats_q).fetchone()
        cols = [c[0] for c in self.con.description]
        metrics = dict(zip(cols, sr))

        total_osm = 49036
        total_overture = 197820
        theoretical_pairs = total_osm * total_overture  # 9,700,301,520
        reduction_ratio = 1.0 - (metrics["total_candidates"] / theoretical_pairs)

        # Candidates per OSM record distribution
        cand_dist_q = """
        SELECT 
            avg(c) as avg_candidates,
            median(c) as median_candidates,
            max(c) as max_candidates
        FROM (
            SELECT osm_source_id, count(*) as c
            FROM final_candidates
            GROUP BY osm_source_id
        );
        """
        cdr = self.con.execute(cand_dist_q).fetchone()

        total_runtime = round(time.time() - t_start, 2)
        summary = {
            "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_osm_universe": total_osm,
            "total_overture_universe": total_overture,
            "theoretical_pair_space": theoretical_pairs,
            "final_candidate_pairs": metrics["total_candidates"],
            "reduction_ratio_pct": round(reduction_ratio * 100.0, 5),
            "unique_osm_records_reached": metrics["unique_osm_records"],
            "osm_coverage_pct": round(100.0 * metrics["unique_osm_records"] / total_osm, 2),
            "unique_overture_records_reached": metrics["unique_ov_records"],
            "overture_coverage_pct": round(100.0 * metrics["unique_ov_records"] / total_overture, 2),
            "osm_records_zero_candidates": total_osm - metrics["unique_osm_records"],
            "candidates_per_osm_distribution": {
                "avg_per_matched_osm": round(cdr[0], 2) if cdr[0] else 0.0,
                "median_per_matched_osm": cdr[1] if cdr[1] else 0,
                "max_per_matched_osm": cdr[2] if cdr[2] else 0,
            },
            "strategy_breakdown": {
                "spatial_50m_generated": c_spatial,
                "exact_name_generated": c_exact,
                "token_containment_generated": c_contain,
                "transliteration_phonetic_generated": c_trans,
                "incompatible_category_pairs_pruned": pruned_incompat
            },
            "distance_metrics": {
                "min_meters": round(metrics["min_distance_m"], 2),
                "avg_meters": round(metrics["avg_distance_m"], 2),
                "median_meters": round(metrics["median_distance_m"], 2),
                "max_meters": round(metrics["max_distance_m"], 2),
            },
            "category_compatibility_distribution": {
                "strongly_compatible": metrics["strongly_compat_pairs"],
                "potentially_compatible": metrics["potentially_compat_pairs"],
                "compatible_unknown": metrics["unknown_compat_pairs"],
            },
            "runtime_seconds": total_runtime,
            "output_file": str(self.output_parquet),
            "output_size_mb": round(parquet_mb, 2),
        }

        # Save summary report
        summary_path = self.reports_dir / "candidate_generation_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"\nCandidate generation complete in {total_runtime}s")
        print(f"Summary saved to: {summary_path}")
        return summary
