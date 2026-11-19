"""Source delta detection between consecutive POI snapshots.

Identifies ADDED, MODIFIED, DELETED, and UNCHANGED source records with field-level
change classification.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple


class RecordDeltaType(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    UNCHANGED = "UNCHANGED"


@dataclass
class SourceRecordDelta:
    """Represents a delta state for an individual source record."""
    poi_source: str
    source_record_id: str
    delta_type: RecordDeltaType
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    changed_fields: List[str] = field(default_factory=list)
    old_record: Optional[Dict[str, Any]] = None
    new_record: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "poi_source": self.poi_source,
            "source_record_id": self.source_record_id,
            "delta_type": self.delta_type.value,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "changed_fields": self.changed_fields,
        }


@dataclass
class SnapshotDeltaSummary:
    """Summary of delta detection across two snapshots."""
    source_name: str
    old_snapshot_id: Optional[str]
    new_snapshot_id: str
    added_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    unchanged_count: int = 0
    total_active_count: int = 0
    deltas: Dict[str, SourceRecordDelta] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "old_snapshot_id": self.old_snapshot_id,
            "new_snapshot_id": self.new_snapshot_id,
            "added_count": self.added_count,
            "modified_count": self.modified_count,
            "deleted_count": self.deleted_count,
            "unchanged_count": self.unchanged_count,
            "total_active_count": self.total_active_count,
        }

    @property
    def has_changes(self) -> bool:
        return (self.added_count > 0 or self.modified_count > 0 or self.deleted_count > 0)

    @property
    def affected_record_ids(self) -> Set[str]:
        """Set of source IDs that were ADDED, MODIFIED, or DELETED."""
        return {
            sid for sid, d in self.deltas.items()
            if d.delta_type in (RecordDeltaType.ADDED, RecordDeltaType.MODIFIED, RecordDeltaType.DELETED)
        }


def detect_field_changes(old_r: Dict[str, Any], new_r: Dict[str, Any]) -> List[str]:
    """Detect which conflation-relevant fields changed between two record revisions."""
    changed = []
    
    # Names
    old_name = str(old_r.get("name_normalized") or old_r.get("name_original") or "").strip().lower()
    new_name = str(new_r.get("name_normalized") or new_r.get("name_original") or "").strip().lower()
    if old_name != new_name:
        changed.append("name")

    old_alt = sorted([str(x).strip().lower() for x in (old_r.get("alternate_names") or []) if str(x).strip()])
    new_alt = sorted([str(x).strip().lower() for x in (new_r.get("alternate_names") or []) if str(x).strip()])
    if old_alt != new_alt and "name" not in changed:
        changed.append("alternate_names")

    # Coordinates
    try:
        old_lat = round(float(old_r.get("latitude", 0.0)), 7)
        old_lon = round(float(old_r.get("longitude", 0.0)), 7)
        new_lat = round(float(new_r.get("latitude", 0.0)), 7)
        new_lon = round(float(new_r.get("longitude", 0.0)), 7)
        if old_lat != new_lat or old_lon != new_lon:
            changed.append("coordinates")
    except (ValueError, TypeError):
        pass

    # Category
    old_cat = str(old_r.get("category_normalized") or old_r.get("category_original") or "").strip().lower()
    new_cat = str(new_r.get("category_normalized") or new_r.get("category_original") or "").strip().lower()
    if old_cat != new_cat:
        changed.append("category")

    # Locality / Address
    old_loc = str(old_r.get("address_locality") or "").strip().lower()
    new_loc = str(new_r.get("address_locality") or "").strip().lower()
    if old_loc != new_loc:
        changed.append("locality")

    # Contact
    old_phone = str(old_r.get("phone") or "").strip()
    new_phone = str(new_r.get("phone") or "").strip()
    if old_phone != new_phone:
        changed.append("phone")

    old_web = str(old_r.get("website") or "").strip().lower()
    new_web = str(new_r.get("website") or "").strip().lower()
    if old_web != new_web:
        changed.append("website")

    return changed


class SourceDeltaDetector:
    """Detects deltas between two source snapshots."""

    def compare_snapshots(
        self,
        old_hashes: Dict[str, str],
        new_hashes: Dict[str, str],
        old_records: Optional[Dict[str, Dict[str, Any]]] = None,
        new_records: Optional[Dict[str, Dict[str, Any]]] = None,
        source_name: str = "COMBINED",
        old_snapshot_id: Optional[str] = None,
        new_snapshot_id: str = "v_latest",
    ) -> SnapshotDeltaSummary:
        """Compare hash mappings and produce a SnapshotDeltaSummary."""
        old_ids = set(old_hashes.keys())
        new_ids = set(new_hashes.keys())

        added_ids = new_ids - old_ids
        deleted_ids = old_ids - new_ids
        common_ids = old_ids & new_ids

        deltas: Dict[str, SourceRecordDelta] = {}
        added_cnt = 0
        modified_cnt = 0
        deleted_cnt = 0
        unchanged_cnt = 0

        # Process ADDED
        for sid in added_ids:
            new_r = (new_records or {}).get(sid)
            poi_src = (new_r.get("poi_source") if new_r else None) or ("OSM" if "/" in sid else "OVERTURE")
            deltas[sid] = SourceRecordDelta(
                poi_source=poi_src,
                source_record_id=sid,
                delta_type=RecordDeltaType.ADDED,
                new_hash=new_hashes[sid],
                new_record=new_r,
            )
            added_cnt += 1

        # Process DELETED
        for sid in deleted_ids:
            old_r = (old_records or {}).get(sid)
            poi_src = (old_r.get("poi_source") if old_r else None) or ("OSM" if "/" in sid else "OVERTURE")
            deltas[sid] = SourceRecordDelta(
                poi_source=poi_src,
                source_record_id=sid,
                delta_type=RecordDeltaType.DELETED,
                old_hash=old_hashes[sid],
                old_record=old_r,
            )
            deleted_cnt += 1

        # Process COMMON
        for sid in common_ids:
            old_h = old_hashes[sid]
            new_h = new_hashes[sid]
            old_r = (old_records or {}).get(sid)
            new_r = (new_records or {}).get(sid)
            poi_src = (new_r.get("poi_source") if new_r else (old_r.get("poi_source") if old_r else None)) or ("OSM" if "/" in sid else "OVERTURE")

            if old_h == new_h:
                deltas[sid] = SourceRecordDelta(
                    poi_source=poi_src,
                    source_record_id=sid,
                    delta_type=RecordDeltaType.UNCHANGED,
                    old_hash=old_h,
                    new_hash=new_h,
                    old_record=old_r,
                    new_record=new_r,
                )
                unchanged_cnt += 1
            else:
                changed = detect_field_changes(old_r, new_r) if (old_r and new_r) else ["content"]
                deltas[sid] = SourceRecordDelta(
                    poi_source=poi_src,
                    source_record_id=sid,
                    delta_type=RecordDeltaType.MODIFIED,
                    old_hash=old_h,
                    new_hash=new_h,
                    changed_fields=changed,
                    old_record=old_r,
                    new_record=new_r,
                )
                modified_cnt += 1

        return SnapshotDeltaSummary(
            source_name=source_name,
            old_snapshot_id=old_snapshot_id,
            new_snapshot_id=new_snapshot_id,
            added_count=added_cnt,
            modified_count=modified_cnt,
            deleted_count=deleted_cnt,
            unchanged_count=unchanged_cnt,
            total_active_count=len(new_ids),
            deltas=deltas,
        )
