"""Canonical Point of Interest (POI) data model.

Provides a unified, source-agnostic schema for heterogeneous geospatial
POI records from OpenStreetMap and Overture Maps Foundation.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import pyarrow as pa


@dataclass
class CanonicalPOI:
    """Canonical representation of an ingested Point of Interest."""

    # Source Provenance
    poi_source: str  # "OSM" or "OVERTURE"
    source_record_id: str  # e.g., "node/12345" or Overture UUID
    source_release: str  # e.g., "2026-10-21.0" or "geofabrik-2026-11-17"
    
    # Naming
    name_original: str
    name_normalized: str
    alternate_names: List[str] = field(default_factory=list)
    name_en: Optional[str] = None
    name_kn: Optional[str] = None  # Kannada script representation
    
    # Coordinates & Spatial Geometry
    latitude: float = 0.0
    longitude: float = 0.0
    geometry_wkt: str = ""  # "POINT (lon lat)"
    
    # Categorization
    category_original: str = ""
    category_normalized: str = "other"  # High-level canonical category
    
    # Addressing & Contact
    address_original: Optional[str] = None
    address_locality: Optional[str] = None
    address_postcode: Optional[str] = None  # 6-digit Indian PIN Code
    phone: Optional[str] = None
    website: Optional[str] = None
    
    # Quality & Provenance Metadata
    confidence: Optional[float] = None
    source_timestamp: Optional[str] = None
    ingestion_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    provenance_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert canonical POI instance to dictionary."""
        d = asdict(self)
        # Serialize nested dict for columnar storage
        d["provenance_metadata"] = json.dumps(self.provenance_metadata, ensure_ascii=False)
        return d


def get_canonical_arrow_schema() -> pa.Schema:
    """Return explicit PyArrow schema for canonical POI datasets."""
    return pa.schema([
        ("poi_source", pa.string()),
        ("source_record_id", pa.string()),
        ("source_release", pa.string()),
        ("name_original", pa.string()),
        ("name_normalized", pa.string()),
        ("alternate_names", pa.list_(pa.string())),
        ("name_en", pa.string()),
        ("name_kn", pa.string()),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("geometry_wkt", pa.string()),
        ("category_original", pa.string()),
        ("category_normalized", pa.string()),
        ("address_original", pa.string()),
        ("address_locality", pa.string()),
        ("address_postcode", pa.string()),
        ("phone", pa.string()),
        ("website", pa.string()),
        ("confidence", pa.float64()),
        ("source_timestamp", pa.string()),
        ("ingestion_timestamp", pa.string()),
        ("provenance_metadata", pa.string()),
    ])
