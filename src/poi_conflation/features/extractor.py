"""Pairwise feature extraction engine and streaming pipeline.

Coordinates name similarity, Indic transliteration, metric spatial projections,
category compatibility, and blocking strategy indicators across candidate pairs.
Designed for memory-bounded execution on Apple Silicon (8 GB RAM).
"""

import time
import resource
from pathlib import Path
from typing import Dict, Any, List
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from src.poi_conflation.features.schema import (
    FEATURE_SCHEMA_VERSION,
    ALL_COLUMNS,
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


def extract_pair_features_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Extract full 44-feature dictionary for a single joined pair record."""
    record: Dict[str, Any] = {
        "candidate_pair_id": row["candidate_pair_id"],
        "osm_source_id": row["osm_source_id"],
        "ov_source_id": row["ov_source_id"],
    }

    # 1. Name features
    record.update(extract_name_features(row.get("osm_norm_name"), row.get("ov_norm_name")))

    # 2. Indic transliteration features
    record.update(
        extract_translit_features(
            osm_raw_name=row.get("osm_name"),
            ov_raw_name=row.get("ov_name"),
            osm_kn_name=row.get("osm_kn"),
            ov_kn_name=row.get("ov_kn"),
            osm_norm_name=row.get("osm_norm_name"),
            ov_norm_name=row.get("ov_norm_name"),
        )
    )

    # 3. Spatial metric features
    record.update(
        extract_spatial_features(
            utm_x_osm=row.get("utm_x_osm"),
            utm_y_osm=row.get("utm_y_osm"),
            utm_x_ov=row.get("utm_x_ov"),
            utm_y_ov=row.get("utm_y_ov"),
        )
    )

    # 4. Category compatibility features
    record.update(
        extract_category_features(
            osm_cat=row.get("osm_category"),
            ov_cat=row.get("ov_category"),
            precomputed_compat=row.get("category_compatibility"),
        )
    )

    # 5. Blocking strategy features
    record.update(extract_strategy_features(row.get("blocking_strategies")))

    return record


class PairwiseFeatureExtractor:
    """Batch-oriented feature extraction engine with streaming Parquet persistence."""

    def __init__(
        self,
        canonical_pois_path: str = "data/processed/canonical_pois_h3.parquet",
        candidate_pairs_path: str = "data/processed/candidate_pairs/candidate_pairs_union.parquet",
        output_parquet_path: str = "data/processed/features/pairwise_features.parquet",
        batch_size: int = 50000,
    ):
        self.canonical_pois_path = canonical_pois_path
        self.candidate_pairs_path = candidate_pairs_path
        self.output_parquet_path = output_parquet_path
        self.batch_size = batch_size
        self.schema = get_pyarrow_feature_schema()

    def _setup_duckdb(self) -> duckdb.DuckDBPyConnection:
        """Initialize DuckDB with spatial extensions and projected UTM 43N coordinates."""
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")
        
        # Prepare indexed projected POI table
        con.execute(f"""
            CREATE TEMP TABLE projected_pois AS 
            SELECT 
                source_record_id,
                name_original,
                name_normalized,
                name_kn,
                category_normalized,
                latitude,
                longitude,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
            FROM '{self.canonical_pois_path}'
        """)
        return con

    def run_pipeline(self) -> Dict[str, Any]:
        """Execute full streaming feature extraction over the complete candidate universe."""
        start_time = time.time()
        mem_start_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

        out_path = Path(self.output_parquet_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        con = self._setup_duckdb()

        # Query all pairs joined with projected coordinates
        query = f"""
            SELECT 
                c.candidate_pair_id,
                c.osm_source_id,
                c.ov_source_id,
                c.osm_name,
                c.ov_name,
                c.osm_norm_name,
                c.ov_norm_name,
                p_osm.name_kn as osm_kn,
                p_ov.name_kn as ov_kn,
                c.osm_category,
                c.ov_category,
                c.category_compatibility,
                c.blocking_strategies,
                p_osm.utm_x as utm_x_osm,
                p_osm.utm_y as utm_y_osm,
                p_ov.utm_x as utm_x_ov,
                p_ov.utm_y as utm_y_ov
            FROM '{self.candidate_pairs_path}' c
            LEFT JOIN projected_pois p_osm ON c.osm_source_id = p_osm.source_record_id
            LEFT JOIN projected_pois p_ov ON c.ov_source_id = p_ov.source_record_id
            ORDER BY c.candidate_pair_id
        """

        rel = con.execute(query)

        writer = pq.ParquetWriter(
            str(out_path),
            schema=self.schema,
            compression="snappy",
        )

        total_processed = 0
        batch_count = 0

        col_names = [desc[0] for desc in rel.description]

        try:
            while True:
                rows = rel.fetchmany(self.batch_size)
                if not rows:
                    break

                batch_dicts = [dict(zip(col_names, row)) for row in rows]
                extracted_records = [extract_pair_features_dict(d) for d in batch_dicts]

                # Convert to columnar dictionary for PyArrow
                columnar: Dict[str, List[Any]] = {col: [] for col in ALL_COLUMNS}
                for rec in extracted_records:
                    for col in ALL_COLUMNS:
                        columnar[col].append(rec[col])

                batch_table = pa.Table.from_pydict(columnar, schema=self.schema)
                writer.write_table(batch_table)

                total_processed += len(rows)
                batch_count += 1

        finally:
            writer.close()
            con.close()

        peak_mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

        elapsed_sec = time.time() - start_time
        file_size_bytes = out_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        summary = {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "total_candidate_pairs_processed": total_processed,
            "batches_executed": batch_count,
            "batch_size": self.batch_size,
            "total_features_count": len(ALL_FEATURE_COLUMNS),
            "output_file": str(out_path),
            "output_size_bytes": file_size_bytes,
            "output_size_mb": round(file_size_mb, 2),
            "execution_time_seconds": round(elapsed_sec, 2),
            "processing_throughput_pairs_per_sec": round(total_processed / elapsed_sec, 1) if elapsed_sec > 0 else 0,
            "initial_memory_mb": round(mem_start_mb, 2),
            "peak_memory_mb": round(peak_mem_mb, 2),
            "feature_columns": {
                "name_features": len(NAME_FEATURE_COLUMNS),
                "translit_features": len(TRANSLIT_FEATURE_COLUMNS),
                "spatial_features": len(SPATIAL_FEATURE_COLUMNS),
                "category_features": len(CATEGORY_FEATURE_COLUMNS),
                "strategy_features": len(STRATEGY_FEATURE_COLUMNS),
            },
        }

        return summary
