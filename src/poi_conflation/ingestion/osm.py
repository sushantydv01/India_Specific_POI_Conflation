"""OpenStreetMap (OSM) POI ingestion module for Bengaluru (BBMP).

Extracts bounded OSM PBF extracts and parses physical POIs across standard
taxonomic tags into structured Parquet format with exact spatial containment.
"""

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq
import osmium
from shapely.geometry import Point
from src.poi_conflation.ingestion.boundary import BBMPBoundary

POI_PRIMARY_TAGS = (
    "amenity",
    "shop",
    "tourism",
    "healthcare",
    "leisure",
    "office",
    "craft",
    "historic",
)


class _OSMPOIHandler(osmium.SimpleHandler):
    """Osmium stream handler extracting POI elements with geometries."""

    def __init__(self, boundary: BBMPBoundary):
        super().__init__()
        self.boundary = boundary
        self.records: List[Dict[str, Any]] = []

    def _extract_record(
        self,
        elem_type: str,
        elem_id: int,
        version: int,
        timestamp: str,
        lon: float,
        lat: float,
        tags: Dict[str, str],
        matched_keys: List[str]
    ):
        # Exact point-in-polygon check
        if not self.boundary.contains_point(lon, lat):
            return

        name = tags.get("name")
        name_en = tags.get("name:en")
        name_kn = tags.get("name:kn")
        name_hi = tags.get("name:hi")
        
        # Primary category determination
        primary_key = matched_keys[0]
        category_original = f"{primary_key}={tags.get(primary_key)}"

        # Addressing
        addr_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:suburb") or tags.get("addr:neighbourhood")
        ]
        addr_freeform = ", ".join([p for p in addr_parts if p]) or None
        addr_locality = tags.get("addr:city") or tags.get("addr:suburb")
        addr_postcode = tags.get("addr:postcode")

        # Contact
        phone = tags.get("phone") or tags.get("contact:phone")
        website = tags.get("website") or tags.get("contact:website")

        self.records.append({
            "osm_type": elem_type,
            "osm_id": f"{elem_type}/{elem_id}",
            "numeric_id": elem_id,
            "version": version,
            "timestamp": timestamp,
            "latitude": lat,
            "longitude": lon,
            "geometry_wkt": f"POINT ({lon:.7f} {lat:.7f})",
            "name": name,
            "name_en": name_en,
            "name_kn": name_kn,
            "name_hi": name_hi,
            "category_original": category_original,
            "matched_keys": matched_keys,
            "addr_freeform": addr_freeform,
            "addr_locality": addr_locality,
            "addr_postcode": addr_postcode,
            "phone": phone,
            "website": website,
            "raw_tags": tags
        })

    def node(self, n):
        tags = {t.k: t.v for t in n.tags}
        matched = [k for k in POI_PRIMARY_TAGS if k in tags]
        if matched and n.location.valid():
            self._extract_record(
                elem_type="node",
                elem_id=n.id,
                version=n.version,
                timestamp=n.timestamp.isoformat() if hasattr(n.timestamp, "isoformat") else str(n.timestamp),
                lon=n.location.lon,
                lat=n.location.lat,
                tags=tags,
                matched_keys=matched
            )

    def way(self, w):
        tags = {t.k: t.v for t in w.tags}
        matched = [k for k in POI_PRIMARY_TAGS if k in tags]
        if matched:
            coords = []
            for n in w.nodes:
                try:
                    coords.append((n.lon, n.lat))
                except Exception:
                    pass
            if coords:
                # Compute centroid of way nodes
                avg_lon = sum(c[0] for c in coords) / len(coords)
                avg_lat = sum(c[1] for c in coords) / len(coords)
                self._extract_record(
                    elem_type="way",
                    elem_id=w.id,
                    version=w.version,
                    timestamp=w.timestamp.isoformat() if hasattr(w.timestamp, "isoformat") else str(w.timestamp),
                    lon=avg_lon,
                    lat=avg_lat,
                    tags=tags,
                    matched_keys=matched
                )


class OSMIngestor:
    """Manages acquisition, spatial slicing, and structured ingestion of OSM POIs."""

    def __init__(
        self,
        boundary: BBMPBoundary = None,
        source_url: str = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf",
        output_dir: str = "data/raw/osm",
        cache_dir: str = "data/cache"
    ):
        self.boundary = boundary or BBMPBoundary()
        self.source_url = source_url
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.extracted_pbf = self.output_dir / "bengaluru_bbmp.osm.pbf"
        self.output_file = self.output_dir / "bengaluru_osm_pois.parquet"
        self.metadata_file = self.output_dir / "extraction_metadata.json"

    def acquire_pbf(self) -> Path:
        """Download regional extract and slice BBMP bounding box via osmium."""
        if self.extracted_pbf.exists() and self.extracted_pbf.stat().st_size > 100_000:
            print(f"Bounded OSM PBF already exists at: {self.extracted_pbf} ({self.extracted_pbf.stat().st_size / 1e6:.1f} MB)")
            return self.extracted_pbf

        cache_regional_pbf = self.cache_dir / "southern-zone-latest.osm.pbf"
        
        if not cache_regional_pbf.exists() or cache_regional_pbf.stat().st_size < 100_000_000:
            print(f"Downloading Southern Zone extract from {self.source_url} (~534 MB)...")
            t_down0 = time.time()
            subprocess.run(
                ["curl", "-L", "-o", str(cache_regional_pbf), self.source_url],
                check=True
            )
            print(f"Download complete in {time.time() - t_down0:.1f}s!")

        print(f"Extracting BBMP boundary using osmium-tool...")
        t_ext0 = time.time()
        # Use osmium extract with polygon geojson
        cmd = [
            "osmium", "extract",
            "-p", str(self.boundary.boundary_path),
            str(cache_regional_pbf),
            "-o", str(self.extracted_pbf),
            "--overwrite"
        ]
        subprocess.run(cmd, check=True)
        print(f"Extraction complete in {time.time() - t_ext0:.1f}s! ({self.extracted_pbf.stat().st_size / 1e6:.1f} MB)")

        # Optionally cleanup large regional cache file to conserve disk space
        if cache_regional_pbf.exists():
            print("Cleaning up regional cache PBF to conserve local disk space...")
            cache_regional_pbf.unlink()

        return self.extracted_pbf

    def run(self) -> Dict[str, Any]:
        """Execute full acquisition and structured POI parsing into Parquet."""
        pbf_path = self.acquire_pbf()
        
        print(f"Parsing POIs from {pbf_path} using pyosmium...")
        t0 = time.time()
        handler = _OSMPOIHandler(self.boundary)
        handler.apply_file(str(pbf_path), locations=True)
        t1 = time.time()
        
        records = handler.records
        print(f"Parsed {len(records):,} contained OSM POIs in {t1 - t0:.2f}s!")

        # Convert to PyArrow Table
        arrow_records = []
        for r in records:
            arrow_records.append({
                "osm_type": r["osm_type"],
                "osm_id": r["osm_id"],
                "numeric_id": r["numeric_id"],
                "version": r["version"],
                "timestamp": r["timestamp"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "geometry_wkt": r["geometry_wkt"],
                "name": r["name"],
                "name_en": r["name_en"],
                "name_kn": r["name_kn"],
                "name_hi": r["name_hi"],
                "category_original": r["category_original"],
                "matched_keys": r["matched_keys"],
                "addr_freeform": r["addr_freeform"],
                "addr_locality": r["addr_locality"],
                "addr_postcode": r["addr_postcode"],
                "phone": r["phone"],
                "website": r["website"],
                "raw_tags_json": json.dumps(r["raw_tags"], ensure_ascii=False)
            })

        schema = pa.schema([
            ("osm_type", pa.string()),
            ("osm_id", pa.string()),
            ("numeric_id", pa.int64()),
            ("version", pa.int32()),
            ("timestamp", pa.string()),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("geometry_wkt", pa.string()),
            ("name", pa.string()),
            ("name_en", pa.string()),
            ("name_kn", pa.string()),
            ("name_hi", pa.string()),
            ("category_original", pa.string()),
            ("matched_keys", pa.list_(pa.string())),
            ("addr_freeform", pa.string()),
            ("addr_locality", pa.string()),
            ("addr_postcode", pa.string()),
            ("phone", pa.string()),
            ("website", pa.string()),
            ("raw_tags_json", pa.string()),
        ])

        table = pa.Table.from_pylist(arrow_records, schema=schema)
        pq.write_table(table, self.output_file, compression="ZSTD")
        print(f"Saved OSM POIs to {self.output_file} ({self.output_file.stat().st_size / 1e6:.2f} MB)")

        metadata = {
            "source": "OpenStreetMap",
            "provider": "Geofabrik GmbH",
            "download_url": self.source_url,
            "ingestion_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "execution_duration_seconds": round(t1 - t0, 2),
            "record_count": len(records),
            "output_file": str(self.output_file),
            "file_size_bytes": self.output_file.stat().st_size,
            "boundary_relation_id": self.boundary.metadata.get("osm_id", 7902476)
        }

        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata
