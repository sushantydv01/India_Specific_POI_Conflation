"""Transforms raw OSM and Overture POI extracts into the Canonical POI schema."""

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

from src.poi_conflation.models.canonical import CanonicalPOI, get_canonical_arrow_schema
from src.poi_conflation.models.categories import (
    normalize_osm_category,
    normalize_overture_category,
)


def normalize_name_string(name: Optional[str]) -> str:
    """Normalize POI name string preserving Latin and Indic scripts.
    
    Preserves:
    - Letters (Unicode 'L*')
    - Combining Marks / Matras (Unicode 'M*': Mn, Mc, Me)
    - Numbers (Unicode 'N*')
    Replaces punctuation and symbols with space, collapses whitespace.
    Does NOT perform transliteration.
    """
    if not name:
        return ""
    # NFC normalization ensures composed characters are consistent
    s = unicodedata.normalize("NFC", name).lower()
    cleaned = [
        c if unicodedata.category(c).startswith(("L", "M", "N")) else " "
        for c in s
    ]
    return " ".join("".join(cleaned).split())


class CanonicalTransformer:
    """Harmonizes source-specific POI extracts into the canonical analytical schema."""

    def __init__(
        self,
        overture_raw_path: str = "data/raw/overture/bengaluru_overture_places.parquet",
        osm_raw_path: str = "data/raw/osm/bengaluru_osm_pois.parquet",
        output_path: str = "data/processed/canonical_pois.parquet",
        metadata_path: str = "data/processed/canonical_metadata.json",
    ):
        self.overture_raw_path = Path(overture_raw_path)
        self.osm_raw_path = Path(osm_raw_path)
        self.output_path = Path(output_path)
        self.metadata_path = Path(metadata_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def transform_overture(self) -> List[CanonicalPOI]:
        """Transform raw Overture Places records into CanonicalPOI instances."""
        if not self.overture_raw_path.exists():
            raise FileNotFoundError(f"Raw Overture file missing: {self.overture_raw_path}")

        print(f"Loading and transforming Overture records from {self.overture_raw_path}...")
        table = pq.read_table(self.overture_raw_path)
        pydict = table.to_pydict()
        num_rows = table.num_rows

        canonical_list = []
        for i in range(num_rows):
            oid = pydict["id"][i]
            name = pydict["name_primary"][i] or ""
            norm_name = normalize_name_string(name)
            
            # Alternate names from rules
            alt_names = []
            rules = pydict["names_rules"][i]
            if rules:
                for r in rules:
                    val = r.get("value")
                    if val and val != name and val not in alt_names:
                        alt_names.append(val)

            # Categorization
            basic_cat = pydict["basic_category"][i]
            tax_prim = pydict["taxonomy_primary"][i]
            orig_cat = tax_prim or basic_cat or "unclassified"
            norm_cat = normalize_overture_category(tax_prim, basic_cat)

            # Addressing
            addr_free = pydict["addr_freeform"][i]
            addr_loc = pydict["addr_locality"][i]
            addr_post = pydict["addr_postcode"][i]
            
            # PIN code clean
            if addr_post:
                match = re.search(r"\b(560\d{3})\b", str(addr_post))
                if match:
                    addr_post = match.group(1)

            # Confidence
            conf = pydict["confidence"][i]

            # Provenance
            sources_val = pydict["sources"][i]
            prov = {"upstream_sources": sources_val, "version": pydict["version"][i]}

            poi = CanonicalPOI(
                poi_source="OVERTURE",
                source_record_id=oid,
                source_release="2026-10-21.0",
                name_original=name,
                name_normalized=norm_name,
                alternate_names=alt_names,
                name_en=None,
                name_kn=None,
                latitude=float(pydict["latitude"][i]),
                longitude=float(pydict["longitude"][i]),
                geometry_wkt=pydict["geometry_wkt"][i],
                category_original=orig_cat,
                category_normalized=norm_cat,
                address_original=addr_free,
                address_locality=addr_loc,
                address_postcode=addr_post,
                phone=None,
                website=None,
                confidence=float(conf) if conf is not None else None,
                source_timestamp=None,
                provenance_metadata=prov,
            )
            canonical_list.append(poi)

        return canonical_list

    def transform_osm(self) -> List[CanonicalPOI]:
        """Transform raw OSM POI records into CanonicalPOI instances."""
        if not self.osm_raw_path.exists():
            raise FileNotFoundError(f"Raw OSM file missing: {self.osm_raw_path}")

        print(f"Loading and transforming OSM records from {self.osm_raw_path}...")
        table = pq.read_table(self.osm_raw_path)
        pydict = table.to_pydict()
        num_rows = table.num_rows

        canonical_list = []
        for i in range(num_rows):
            osm_id = pydict["osm_id"][i]
            name = pydict["name"][i] or ""
            norm_name = normalize_name_string(name)
            name_en = pydict["name_en"][i]
            name_kn = pydict["name_kn"][i]

            alt_names = []
            if name_en and name_en != name:
                alt_names.append(name_en)
            if name_kn and name_kn != name:
                alt_names.append(name_kn)
            if pydict["name_hi"][i] and pydict["name_hi"][i] != name:
                alt_names.append(pydict["name_hi"][i])

            # Raw tags for category normalization
            raw_tags = json.loads(pydict["raw_tags_json"][i])
            orig_cat = pydict["category_original"][i]
            norm_cat = normalize_osm_category(raw_tags)

            # Addressing
            addr_free = pydict["addr_freeform"][i]
            addr_loc = pydict["addr_locality"][i]
            addr_post = pydict["addr_postcode"][i]
            if addr_post:
                match = re.search(r"\b(560\d{3})\b", str(addr_post))
                if match:
                    addr_post = match.group(1)

            prov = {
                "osm_type": pydict["osm_type"][i],
                "numeric_id": pydict["numeric_id"][i],
                "version": pydict["version"][i],
                "matched_keys": pydict["matched_keys"][i],
            }

            poi = CanonicalPOI(
                poi_source="OSM",
                source_record_id=osm_id,
                source_release="geofabrik-2026-11-17",
                name_original=name,
                name_normalized=norm_name,
                alternate_names=alt_names,
                name_en=name_en,
                name_kn=name_kn,
                latitude=float(pydict["latitude"][i]),
                longitude=float(pydict["longitude"][i]),
                geometry_wkt=pydict["geometry_wkt"][i],
                category_original=orig_cat,
                category_normalized=norm_cat,
                address_original=addr_free,
                address_locality=addr_loc,
                address_postcode=addr_post,
                phone=pydict["phone"][i],
                website=pydict["website"][i],
                confidence=1.0,  # Curated crowdsourced baseline
                source_timestamp=pydict["timestamp"][i],
                provenance_metadata=prov,
            )
            canonical_list.append(poi)

        return canonical_list

    def run(self) -> Dict[str, Any]:
        """Execute full transformation and write combined canonical Parquet table."""
        t0 = time.time()
        overture_pois = self.transform_overture()
        osm_pois = self.transform_osm()
        all_pois = overture_pois + osm_pois

        print(f"Exporting {len(all_pois):,} canonical records ({len(overture_pois):,} Overture, {len(osm_pois):,} OSM)...")
        pylist = [p.to_dict() for p in all_pois]
        schema = get_canonical_arrow_schema()
        table = pa.Table.from_pylist(pylist, schema=schema)
        pq.write_table(table, self.output_path, compression="ZSTD")

        elapsed = round(time.time() - t0, 2)
        print(f"Canonical dataset created at {self.output_path} ({self.output_path.stat().st_size / 1e6:.2f} MB) in {elapsed}s")

        metadata = {
            "dataset": "Canonical India POI Conflation Benchmark (Bengaluru)",
            "creation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "execution_duration_seconds": elapsed,
            "total_canonical_records": len(all_pois),
            "overture_records": len(overture_pois),
            "osm_records": len(osm_pois),
            "output_file": str(self.output_path),
            "file_size_bytes": self.output_path.stat().st_size,
        }

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata
