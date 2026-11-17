"""Cross-source spatial proximity analysis between OpenStreetMap and Overture Places.

Computes candidate pairings across geodesic / projected metric distances
(10m, 25m, 50m, 100m, 200m) using high-performance spatial grid equi-joins in DuckDB.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List

import duckdb


class SpatialProximityAnalyzer:
    """Evaluates spatial proximity candidate distributions between OSM and Overture."""

    DISTANCE_THRESHOLDS = [10.0, 25.0, 50.0, 100.0, 200.0]

    def __init__(
        self,
        indexed_dataset_path: str = "data/processed/canonical_pois_h3.parquet",
        output_dir: str = "reports"
    ):
        self.dataset_path = Path(indexed_dataset_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect()
        self.con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")

    def _setup_metric_projections(self):
        """Project coordinates to EPSG:32643 (UTM 43N metric grid) and partition into 200m bins."""
        print("Projecting POI coordinates to EPSG:32643 UTM Zone 43N metric grid...")
        t0 = time.time()
        self.con.execute(f"""
            CREATE TEMP TABLE osm_utm AS 
            SELECT 
                canonical_poi_id,
                source_record_id,
                name_original,
                name_normalized,
                category_normalized,
                latitude,
                longitude,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
            FROM '{self.dataset_path}'
            WHERE poi_source = 'OSM';

            CREATE TEMP TABLE ov_utm AS 
            SELECT 
                canonical_poi_id,
                source_record_id,
                name_original,
                name_normalized,
                category_normalized,
                latitude,
                longitude,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y,
                CAST(floor(ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) / 200.0) AS INT) as gx,
                CAST(floor(ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) / 200.0) AS INT) as gy
            FROM '{self.dataset_path}'
            WHERE poi_source = 'OVERTURE';

            -- Offsets for 3x3 neighboring 200m grid cells
            CREATE TEMP TABLE grid_offsets (dx INT, dy INT);
            INSERT INTO grid_offsets VALUES 
                (-1,-1), (-1,0), (-1,1),
                ( 0,-1), ( 0,0), ( 0,1),
                ( 1,-1), ( 1,0), ( 1,1);

            CREATE TEMP TABLE osm_expanded AS
            SELECT 
                o.canonical_poi_id,
                o.source_record_id,
                o.name_original,
                o.name_normalized,
                o.category_normalized,
                o.utm_x,
                o.utm_y,
                CAST(floor(o.utm_x / 200.0) AS INT) + off.dx as gx,
                CAST(floor(o.utm_y / 200.0) AS INT) + off.dy as gy
            FROM osm_utm o
            CROSS JOIN grid_offsets off;
        """)
        print(f"Spatial projection and grid partitioning ready in {time.time() - t0:.2f}s")

    def _materialize_candidate_pairs(self) -> str:
        """Join on grid bins and compute exact Euclidean distance in meters for pairs <= 200m."""
        print("Computing exact candidate pairs within 200m maximum spatial window...")
        t0 = time.time()
        self.con.execute("""
            CREATE TEMP TABLE candidate_pairs_200m AS
            SELECT 
                o.canonical_poi_id as osm_poi_id,
                o.source_record_id as osm_source_id,
                o.name_original as osm_name,
                o.name_normalized as osm_norm_name,
                o.category_normalized as osm_category,
                v.canonical_poi_id as ov_poi_id,
                v.source_record_id as ov_source_id,
                v.name_original as ov_name,
                v.name_normalized as ov_norm_name,
                v.category_normalized as ov_category,
                round(sqrt((o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y)), 2) as distance_meters
            FROM osm_expanded o
            JOIN ov_utm v ON o.gx = v.gx AND o.gy = v.gy
            WHERE (o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y) <= 40000.0;
        """)
        count = self.con.execute("SELECT count(*) FROM candidate_pairs_200m").fetchone()[0]
        print(f"Materialized {count:,} candidate pairs (<=200m) in {time.time() - t0:.2f}s")
        return "candidate_pairs_200m"

    def run_analysis(self) -> Dict[str, Any]:
        """Execute threshold sweep across 10m, 25m, 50m, 100m, 200m."""
        t_start = time.time()
        print("=" * 70)
        print("CROSS-SOURCE SPATIAL PROXIMITY ANALYSIS")
        print("=" * 70)

        self._setup_metric_projections()
        table_name = self._materialize_candidate_pairs()

        total_osm = 49036
        total_overture = 197820

        threshold_results = []
        for d in self.DISTANCE_THRESHOLDS:
            print(f"Evaluating distance threshold <= {d}m...")
            q = f"""
            WITH filtered AS (
                SELECT osm_poi_id, ov_poi_id, distance_meters
                FROM {table_name}
                WHERE distance_meters <= {d}
            ),
            osm_grouped AS (
                SELECT osm_poi_id, count(*) as cand_count
                FROM filtered
                GROUP BY osm_poi_id
            )
            SELECT 
                (SELECT count(*) FROM filtered) as total_pairs,
                (SELECT count(distinct osm_poi_id) FROM filtered) as matched_osm_records,
                (SELECT count(distinct ov_poi_id) FROM filtered) as matched_ov_records,
                (SELECT avg(cand_count) FROM osm_grouped) as avg_candidates_per_matched_osm,
                (SELECT median(cand_count) FROM osm_grouped) as median_candidates_per_matched_osm,
                (SELECT max(cand_count) FROM osm_grouped) as max_candidates_per_matched_osm,
                (SELECT avg(distance_meters) FROM filtered) as avg_distance,
                (SELECT median(distance_meters) FROM filtered) as median_distance
            """
            r = self.con.execute(q).fetchone()
            tot_pairs, m_osm, m_ov, avg_c, med_c, max_c, avg_dist, med_dist = r

            threshold_results.append({
                "distance_threshold_meters": d,
                "total_candidate_pairs": tot_pairs,
                "osm_records_with_candidates": m_osm,
                "osm_coverage_pct": round(100.0 * m_osm / total_osm, 2),
                "overture_records_with_candidates": m_ov,
                "overture_coverage_pct": round(100.0 * m_ov / total_overture, 2),
                "avg_candidates_per_matched_osm": round(avg_c, 2) if avg_c is not None else 0.0,
                "median_candidates_per_matched_osm": med_c if med_c is not None else 0,
                "max_candidates_per_matched_osm": max_c if max_c is not None else 0,
                "avg_distance_meters": round(avg_dist, 2) if avg_dist is not None else 0.0,
                "median_distance_meters": round(med_dist, 2) if med_dist is not None else 0.0,
            })

        # Distance distribution percentiles across all <= 200m pairs
        print("Computing distance distribution percentiles...")
        dist_stats_q = f"""
        SELECT 
            min(distance_meters) as min_dist,
            quantile_cont(distance_meters, 0.10) as p10,
            quantile_cont(distance_meters, 0.25) as p25,
            quantile_cont(distance_meters, 0.50) as p50,
            quantile_cont(distance_meters, 0.75) as p75,
            quantile_cont(distance_meters, 0.90) as p90,
            max(distance_meters) as max_dist,
            avg(distance_meters) as avg_dist,
            stddev(distance_meters) as std_dist
        FROM {table_name}
        """
        dr = self.con.execute(dist_stats_q).fetchone()
        dist_percentiles = {
            "min_meters": round(dr[0], 2),
            "p10_meters": round(dr[1], 2),
            "p25_meters": round(dr[2], 2),
            "p50_median_meters": round(dr[3], 2),
            "p75_meters": round(dr[4], 2),
            "p90_meters": round(dr[5], 2),
            "max_meters": round(dr[6], 2),
            "mean_meters": round(dr[7], 2),
            "std_dev_meters": round(dr[8], 2),
        }

        # Export sample of pairs for research inspection
        sample_path = self.output_dir / "candidate_pairs_50m_sample.csv"
        print(f"Exporting sample of 50m candidate pairs to {sample_path}...")
        self.con.execute(f"""
            COPY (
                SELECT osm_source_id, osm_name, osm_category,
                       ov_source_id, ov_name, ov_category, distance_meters
                FROM {table_name}
                WHERE distance_meters <= 50.0
                LIMIT 500
            ) TO '{sample_path}' (HEADER, DELIMITER ',');
        """)

        total_duration = round(time.time() - t_start, 2)
        summary = {
            "analysis_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_osm_universe": total_osm,
            "total_overture_universe": total_overture,
            "distance_thresholds": threshold_results,
            "distance_distribution_200m": dist_percentiles,
            "execution_duration_seconds": total_duration,
            "research_notes": (
                "Spatial proximity provides candidate blocking evidence, not proof of entity identity. "
                "Multiple distinct businesses operate in close physical proximity (e.g., multistory shopping complexes). "
                "Counts represent unique record pairs (OSM POI, Overture Place) unless explicitly stated as unique records."
            )
        }

        out_json = self.output_dir / "spatial_proximity_summary.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"Spatial proximity analysis complete in {total_duration}s")
        print(f"Summary saved to: {out_json}")
        return summary
