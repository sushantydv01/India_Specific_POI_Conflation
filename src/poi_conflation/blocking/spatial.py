"""Spatial blocking and metric proximity candidate generation using H3 and DuckDB.

Evaluates multi-resolution H3 indexing (Res 8, 9, 10) and metric distance thresholds
(10m, 25m, 50m, 100m, 200m) in EPSG:32643 UTM Zone 43N.
"""

import time
from typing import Dict, Any, List, Optional
import duckdb


class SpatialBlocker:
    """Generates cross-source candidate pairs using H3 indexing and metric Euclidean distance."""

    def __init__(self, dataset_path: str = "data/processed/canonical_pois_h3.parquet"):
        self.dataset_path = dataset_path
        self.con = duckdb.connect()
        self.con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")

    def _setup_metric_tables(self):
        """Prepare projected tables in DuckDB with UTM 43N coordinates and H3 fields."""
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE osm_points AS 
            SELECT 
                canonical_poi_id as osm_poi_id,
                source_record_id as osm_source_id,
                name_original as osm_name,
                name_normalized as osm_norm_name,
                category_normalized as osm_category,
                h3_res8 as osm_h3_8,
                h3_res9 as osm_h3_9,
                h3_res10 as osm_h3_10,
                latitude as osm_lat,
                longitude as osm_lon,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
            FROM '{self.dataset_path}'
            WHERE poi_source = 'OSM';

            CREATE OR REPLACE TEMP TABLE ov_points AS 
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
            FROM '{self.dataset_path}'
            WHERE poi_source = 'OVERTURE';

            -- 3x3 neighboring 200m bins for complete 200m distance coverage
            CREATE OR REPLACE TEMP TABLE grid_offsets (dx INT, dy INT);
            DELETE FROM grid_offsets;
            INSERT INTO grid_offsets VALUES 
                (-1,-1), (-1,0), (-1,1),
                ( 0,-1), ( 0,0), ( 0,1),
                ( 1,-1), ( 1,0), ( 1,1);

            CREATE OR REPLACE TEMP TABLE osm_grid_expanded AS
            SELECT 
                o.*,
                CAST(floor(o.utm_x / 200.0) AS INT) + off.dx as gx,
                CAST(floor(o.utm_y / 200.0) AS INT) + off.dy as gy
            FROM osm_points o
            CROSS JOIN grid_offsets off;
        """)

    def evaluate_h3_same_cell_resolution(self, resolution: int) -> Dict[str, Any]:
        """Evaluate candidate generation using same-cell membership at a specific H3 resolution."""
        col_osm = f"osm_h3_{resolution}"
        col_ov = f"ov_h3_{resolution}"

        t0 = time.time()
        q = f"""
        SELECT 
            count(*) as pair_count,
            count(distinct o.osm_poi_id) as matched_osm,
            count(distinct v.ov_poi_id) as matched_ov,
            avg(ST_Distance(ST_Point(o.utm_x, o.utm_y), ST_Point(v.utm_x, v.utm_y))) as avg_dist_m
        FROM osm_points o
        JOIN ov_points v ON o.{col_osm} = v.{col_ov};
        """
        r = self.con.execute(q).fetchone()
        elapsed = round(time.time() - t0, 3)

        return {
            "h3_resolution": resolution,
            "method": "same_cell_unexpanded",
            "candidate_pairs": r[0],
            "unique_osm_records": r[1],
            "unique_overture_records": r[2],
            "avg_distance_meters": round(r[3], 2) if r[3] is not None else 0.0,
            "runtime_seconds": elapsed,
        }

    def generate_metric_candidates(self, max_distance_meters: float = 50.0) -> duckdb.DuckDBPyRelation:
        """Generate deduplicated cross-source candidate pairs within exact metric distance."""
        self._setup_metric_tables()
        max_dist_sq = max_distance_meters * max_distance_meters

        query = f"""
        SELECT 
            o.osm_source_id || '::' || v.ov_source_id as candidate_pair_id,
            o.osm_poi_id,
            o.osm_source_id,
            o.osm_name,
            o.osm_norm_name,
            o.osm_category,
            v.ov_poi_id,
            v.ov_source_id,
            v.ov_name,
            v.ov_norm_name,
            v.ov_category,
            o.osm_h3_8,
            o.osm_h3_9,
            o.osm_h3_10,
            v.ov_h3_8,
            v.ov_h3_9,
            v.ov_h3_10,
            (o.osm_h3_8 = v.ov_h3_8) as match_h3_res8,
            (o.osm_h3_9 = v.ov_h3_9) as match_h3_res9,
            (o.osm_h3_10 = v.ov_h3_10) as match_h3_res10,
            round(sqrt((o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y)), 2) as distance_meters
        FROM osm_grid_expanded o
        JOIN ov_points v ON o.gx = v.gx AND o.gy = v.gy
        WHERE (o.utm_x - v.utm_x)*(o.utm_x - v.utm_x) + (o.utm_y - v.utm_y)*(o.utm_y - v.utm_y) <= {max_dist_sq}
        """
        return self.con.execute(query)
