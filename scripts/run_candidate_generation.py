#!/usr/bin/env python3
"""Master pipeline runner for Milestone 4: Candidate Generation and Multi-Attribute Blocking.

Executes:
1. Multi-strategy candidate generation engine.
2. Independent strategy comparison evaluation.
3. Candidate review sample generation (reports/candidate_review_sample.csv).
4. Machine-readable audit reports.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.blocking.candidate_engine import CandidateEngine
from src.poi_conflation.blocking.spatial import SpatialBlocker
from src.poi_conflation.blocking.lexical import LexicalBlocker
import duckdb


def generate_review_sample(engine: CandidateEngine, output_csv: Path):
    """Generate bounded, representative review sample with diverse edge cases."""
    print(f"\nGenerating candidate review sample -> {output_csv}...")
    
    # Select balanced representative sample across diverse conflation phenomena
    q = f"""
    COPY (
        WITH ranked AS (
            SELECT *,
                   row_number() OVER (
                       PARTITION BY 
                           CASE 
                               WHEN exact_name_match THEN 'HIGH_LEXICAL_MATCH'
                               WHEN list_contains(blocking_strategies, 'transliteration_phonetic') THEN 'TRANSLITERATION_PHONETIC'
                               WHEN distance_meters <= 15.0 AND NOT exact_name_match AND NOT name_containment THEN 'CLOSE_SPATIAL_DISTINCT'
                               WHEN osm_norm_name IS NULL OR length(osm_norm_name) = 0 THEN 'MISSING_OSM_NAME'
                               WHEN category_compatibility = 'POTENTIALLY_COMPATIBLE' THEN 'CATEGORY_ADJACENCY'
                               ELSE 'SPATIAL_CLUSTER'
                           END
                       ORDER BY distance_meters ASC
                   ) as rank_in_stratum,
                   CASE 
                       WHEN exact_name_match THEN 'HIGH_LEXICAL_MATCH'
                       WHEN list_contains(blocking_strategies, 'transliteration_phonetic') THEN 'TRANSLITERATION_PHONETIC'
                       WHEN distance_meters <= 15.0 AND NOT exact_name_match AND NOT name_containment THEN 'CLOSE_SPATIAL_DISTINCT'
                       WHEN osm_norm_name IS NULL OR length(osm_norm_name) = 0 THEN 'MISSING_OSM_NAME'
                       WHEN category_compatibility = 'POTENTIALLY_COMPATIBLE' THEN 'CATEGORY_ADJACENCY'
                       ELSE 'SPATIAL_CLUSTER'
                   END as review_stratum
            FROM '{engine.output_parquet}'
        )
        SELECT 
            candidate_pair_id,
            review_stratum,
            osm_source_id,
            osm_name,
            osm_category,
            ov_source_id,
            ov_name,
            ov_category,
            distance_meters,
            exact_name_match,
            name_containment,
            category_compatibility,
            array_to_string(blocking_strategies, '+') as strategies_provenance
        FROM ranked
        WHERE rank_in_stratum <= 50
        ORDER BY review_stratum, distance_meters ASC
    ) TO '{output_csv}' (HEADER, DELIMITER ',');
    """
    engine.con.execute(q)
    print(f"Sample exported successfully to {output_csv}")


def evaluate_independent_strategies(engine: CandidateEngine) -> List[Dict[str, Any]]:
    """Evaluate candidate generation performance of each strategy independently."""
    print("\n" + "=" * 70)
    print("INDEPENDENT BLOCKING STRATEGY COMPARISON")
    print("=" * 70)

    strategies_comparison = []

    # 1. Spatial 50m
    t0 = time.time()
    r = engine.con.execute("""
        SELECT count(*), count(distinct osm_source_id), count(distinct ov_source_id)
        FROM cand_spatial_50m;
    """).fetchone()
    strategies_comparison.append({
        "strategy": "Spatial Only (<=50m)",
        "candidate_count": r[0],
        "unique_osm_records": r[1],
        "unique_overture_records": r[2],
        "runtime_seconds": round(time.time() - t0, 3)
    })

    # 2. Exact Normalized Name
    t0 = time.time()
    r = engine.con.execute("""
        SELECT count(*), count(distinct osm_source_id), count(distinct ov_source_id)
        FROM cand_exact_name;
    """).fetchone()
    strategies_comparison.append({
        "strategy": "Exact Name Matching",
        "candidate_count": r[0],
        "unique_osm_records": r[1],
        "unique_overture_records": r[2],
        "runtime_seconds": round(time.time() - t0, 3)
    })

    # 3. Token Overlap & Containment (<=100m)
    t0 = time.time()
    r = engine.con.execute("""
        SELECT count(*), count(distinct osm_source_id), count(distinct ov_source_id)
        FROM cand_token_containment;
    """).fetchone()
    strategies_comparison.append({
        "strategy": "Token Containment (<=100m)",
        "candidate_count": r[0],
        "unique_osm_records": r[1],
        "unique_overture_records": r[2],
        "runtime_seconds": round(time.time() - t0, 3)
    })

    # 4. Transliteration & Phonetic
    t0 = time.time()
    r = engine.con.execute("""
        SELECT count(*), count(distinct osm_source_id), count(distinct ov_source_id)
        FROM cand_transliteration;
    """).fetchone()
    strategies_comparison.append({
        "strategy": "Transliteration / Phonetic",
        "candidate_count": r[0],
        "unique_osm_records": r[1],
        "unique_overture_records": r[2],
        "runtime_seconds": round(time.time() - t0, 3)
    })

    # 5. Combined Deduplicated Union (Filtered)
    t0 = time.time()
    r = engine.con.execute("""
        SELECT count(*), count(distinct osm_source_id), count(distinct ov_source_id)
        FROM final_candidates;
    """).fetchone()
    strategies_comparison.append({
        "strategy": "Combined Multi-Strategy Union",
        "candidate_count": r[0],
        "unique_osm_records": r[1],
        "unique_overture_records": r[2],
        "runtime_seconds": round(time.time() - t0, 3)
    })

    comp_report = engine.reports_dir / "blocking_strategy_comparison.json"
    with open(comp_report, "w", encoding="utf-8") as f:
        json.dump(strategies_comparison, f, indent=2)

    print(f"\n{'Strategy':<32} | {'Candidates':<12} | {'OSM Recs':<10} | {'Overture Recs':<14} | {'Runtime':<8}")
    print("-" * 85)
    for sc in strategies_comparison:
        print(f"{sc['strategy']:<32} | {sc['candidate_count']:<12,} | {sc['unique_osm_records']:<10,} | {sc['unique_overture_records']:<14,} | {sc['runtime_seconds']}s")
    print("-" * 85)

    return strategies_comparison


def main():
    t_start = time.time()
    engine = CandidateEngine()
    summary = engine.run_multi_strategy_generation()
    strategies = evaluate_independent_strategies(engine)

    sample_csv = engine.reports_dir / "candidate_review_sample.csv"
    generate_review_sample(engine, sample_csv)

    print("\n" + "=" * 70)
    print(f"PIPELINE COMPLETED IN {time.time() - t_start:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
