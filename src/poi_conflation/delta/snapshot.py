"""Source snapshot management and deterministic content fingerprinting.

Provides versioned snapshot manifests and content hashing over conflation-relevant
attributes to support reliable delta detection.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pyarrow.parquet as pq


SNAPSHOT_SCHEMA_VERSION = "1.0.0"


def compute_record_content_hash(record: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash over conflation-relevant attributes.
    
    Excludes non-conflation attributes like ingestion timestamps, acquisition dates,
    and row indexes to ensure identical physical entities remain UNCHANGED.
    """
    poi_source = str(record.get("poi_source") or "").strip().upper()
    source_record_id = str(record.get("source_record_id") or record.get("source_id") or "").strip()
    
    # Naming
    name_norm = str(record.get("name_normalized") or "").strip().lower()
    name_orig = str(record.get("name_original") or "").strip().lower()
    alt_names = sorted([str(n).strip().lower() for n in (record.get("alternate_names") or []) if str(n).strip()])
    name_en = str(record.get("name_en") or "").strip().lower()
    name_kn = str(record.get("name_kn") or "").strip()
    
    # Coordinates (rounded to 7 decimals ~1.1cm precision)
    try:
        lat = round(float(record.get("latitude", 0.0)), 7)
        lon = round(float(record.get("longitude", 0.0)), 7)
    except (ValueError, TypeError):
        lat = 0.0
        lon = 0.0

    # Categorization
    cat_norm = str(record.get("category_normalized") or "").strip().lower()
    cat_orig = str(record.get("category_original") or "").strip().lower()

    # Locality & Contact
    locality = str(record.get("address_locality") or "").strip().lower()
    postcode = str(record.get("address_postcode") or "").strip()
    phone = str(record.get("phone") or "").strip()
    website = str(record.get("website") or "").strip().lower()

    payload = {
        "source": poi_source,
        "source_id": source_record_id,
        "name_normalized": name_norm,
        "name_original": name_orig,
        "alternate_names": alt_names,
        "name_en": name_en,
        "name_kn": name_kn,
        "latitude": lat,
        "longitude": lon,
        "category_normalized": cat_norm,
        "category_original": cat_orig,
        "address_locality": locality,
        "address_postcode": postcode,
        "phone": phone,
        "website": website,
    }

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class SourceSnapshotManifest:
    """Metadata describing an ingested source snapshot."""
    snapshot_id: str
    source_name: str  # "OSM", "OVERTURE", or "COMBINED"
    source_release: str
    acquisition_timestamp: str
    processing_timestamp: str
    schema_version: str = SNAPSHOT_SCHEMA_VERSION
    record_count: int = 0
    unique_source_id_count: int = 0
    geographic_bounds: Dict[str, float] = field(default_factory=dict)
    content_fingerprint: str = ""
    input_files: List[str] = field(default_factory=list)
    validation_status: str = "VALID"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "SourceSnapshotManifest":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def build_snapshot_from_records(
    records: List[Dict[str, Any]],
    snapshot_id: str,
    source_name: str,
    source_release: str,
    input_files: List[str],
    acquisition_timestamp: Optional[str] = None,
) -> Tuple[SourceSnapshotManifest, Dict[str, str]]:
    """Build a snapshot manifest and content hash mapping from records.
    
    Returns:
        manifest: SourceSnapshotManifest
        record_hashes: Dict[source_record_id -> sha256_hash]
    """
    now = datetime.now(timezone.utc).isoformat()
    if acquisition_timestamp is None:
        acquisition_timestamp = now

    record_hashes: Dict[str, str] = {}
    unique_ids: set = set()
    min_lat, max_lat = 90.0, -90.0
    min_lon, max_lon = 180.0, -180.0

    for r in records:
        sid = str(r.get("source_record_id") or r.get("source_id") or "")
        unique_ids.add(sid)
        h = compute_record_content_hash(r)
        record_hashes[sid] = h

        try:
            lat = float(r.get("latitude", 0.0))
            lon = float(r.get("longitude", 0.0))
            if lat != 0.0 or lon != 0.0:
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)
        except (ValueError, TypeError):
            pass

    # Compute overall snapshot content fingerprint from sorted record hashes
    hasher = hashlib.sha256()
    for sid in sorted(record_hashes.keys()):
        hasher.update(f"{sid}:{record_hashes[sid]}".encode("utf-8"))
    content_fingerprint = hasher.hexdigest()

    bounds = {
        "min_latitude": min_lat if min_lat <= max_lat else 0.0,
        "max_latitude": max_lat if min_lat <= max_lat else 0.0,
        "min_longitude": min_lon if min_lon <= max_lon else 0.0,
        "max_longitude": max_lon if min_lon <= max_lon else 0.0,
    }

    manifest = SourceSnapshotManifest(
        snapshot_id=snapshot_id,
        source_name=source_name,
        source_release=source_release,
        acquisition_timestamp=acquisition_timestamp,
        processing_timestamp=now,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        record_count=len(records),
        unique_source_id_count=len(unique_ids),
        geographic_bounds=bounds,
        content_fingerprint=content_fingerprint,
        input_files=input_files,
        validation_status="VALID" if len(unique_ids) == len(records) else "DUPLICATE_IDS",
    )

    return manifest, record_hashes
