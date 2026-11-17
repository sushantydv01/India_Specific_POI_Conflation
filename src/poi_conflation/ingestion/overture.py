"""Overture Places ingestion module for Bengaluru (BBMP).

Queries remote Overture GeoParquet over S3 with bounding box pruning
and strict point-in-polygon containment against the BBMP boundary.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any
import duckdb
from src.poi_conflation.ingestion.boundary import BBMPBoundary


class OvertureIngestor:
    """Ingests and filters Overture Maps Places for the BBMP municipal boundary."""

    def __init__(
        self,
        release: str = "2026-10-21.0",
        s3_region: str = "us-west-2",
        boundary: BBMPBoundary = None,
        output_dir: str = "data/raw/overture"
    ):
        self.release = release
        self.s3_region = s3_region
        self.boundary = boundary or BBMPBoundary()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.output_dir / "bengaluru_overture_places.parquet"
        self.metadata_file = self.output_dir / "extraction_metadata.json"

    def run(self) -> Dict[str, Any]:
        """Execute the ingestion query and export raw bounded Parquet extract."""
        print(f"Connecting to DuckDB and querying Overture Places release {self.release}...")
        t0 = time.time()
        
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
        con.execute(f"SET s3_region = '{self.s3_region}'; SET geometry_always_xy = true;")

        parquet_uri = f"s3://overturemaps-us-west-2/release/{self.release}/theme=places/type=place/*.parquet"
        min_lon, min_lat, max_lon, max_lat = self.boundary.bounds
        bbmp_wkt = self.boundary.wkt

        # Extract only relevant structured columns with spatial containment
        query = f"""
        COPY (
            SELECT
                id,
                names.primary AS name_primary,
                names.rules AS names_rules,
                basic_category,
                taxonomy.primary AS taxonomy_primary,
                taxonomy.alternates AS taxonomy_alternates,
                confidence,
                addresses,
                addresses[1].freeform AS addr_freeform,
                addresses[1].locality AS addr_locality,
                addresses[1].postcode AS addr_postcode,
                sources,
                operating_status,
                version,
                ST_X(geometry) AS longitude,
                ST_Y(geometry) AS latitude,
                ST_AsText(geometry) AS geometry_wkt
            FROM read_parquet('{parquet_uri}')
            WHERE bbox.xmin >= {min_lon} AND bbox.xmax <= {max_lon}
              AND bbox.ymin >= {min_lat} AND bbox.ymax <= {max_lat}
              AND ST_Within(geometry, ST_GeomFromText(?))
        ) TO '{self.output_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
        """
        
        con.execute(query, [bbmp_wkt])
        t1 = time.time()
        
        # Verify row count
        count_res = con.execute(f"SELECT count(*) FROM read_parquet('{self.output_file}')").fetchone()[0]
        con.close()
        
        elapsed = round(t1 - t0, 2)
        print(f"Overture ingestion complete! {count_res:,} records written to {self.output_file} in {elapsed}s")

        metadata = {
            "source": "Overture Maps Foundation",
            "theme": "places",
            "type": "place",
            "release": self.release,
            "s3_uri": parquet_uri,
            "ingestion_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "execution_duration_seconds": elapsed,
            "record_count": count_res,
            "bounding_box": [min_lon, min_lat, max_lon, max_lat],
            "boundary_relation_id": self.boundary.metadata.get("osm_id", 7902476),
            "output_file": str(self.output_file),
            "file_size_bytes": self.output_file.stat().st_size
        }
        
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata
