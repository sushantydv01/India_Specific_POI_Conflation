"""Canonical entity lineage ledger and change tracking.

Maintains immutable historical audit records of all canonical entity lifecycle events,
including creation, attribute updates, component merges, splits, and retirements.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import uuid
import pyarrow as pa
import pyarrow.parquet as pq


class LineageEventType(str, Enum):
    ENTITY_CREATED = "ENTITY_CREATED"
    ENTITY_UPDATED = "ENTITY_UPDATED"
    ENTITY_MERGED = "ENTITY_MERGED"
    ENTITY_SPLIT = "ENTITY_SPLIT"
    ENTITY_RETIRED = "ENTITY_RETIRED"
    ENTITY_UNCHANGED = "ENTITY_UNCHANGED"


@dataclass
class LineageEvent:
    """An individual canonical entity lifecycle transition record."""
    lineage_id: str
    event_type: LineageEventType
    previous_entity_ids: List[str]
    current_entity_ids: List[str]
    contributing_osm_ids: List[str]
    contributing_ov_ids: List[str]
    trigger_snapshot_id: str
    trigger_run_id: str
    timestamp: str
    explanation: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "event_type": self.event_type.value,
            "previous_entity_ids": self.previous_entity_ids,
            "current_entity_ids": self.current_entity_ids,
            "contributing_osm_ids": self.contributing_osm_ids,
            "contributing_ov_ids": self.contributing_ov_ids,
            "trigger_snapshot_id": self.trigger_snapshot_id,
            "trigger_run_id": self.trigger_run_id,
            "timestamp": self.timestamp,
            "explanation": self.explanation,
            "metadata_json": json.dumps(self.metadata, ensure_ascii=False),
        }


class LineageLedger:
    """Persistent ledger tracking canonical entity identity transitions."""

    def __init__(self):
        self.events: List[LineageEvent] = []

    def record_event(
        self,
        event_type: LineageEventType,
        previous_entity_ids: List[str],
        current_entity_ids: List[str],
        contributing_osm_ids: List[str],
        contributing_ov_ids: List[str],
        trigger_snapshot_id: str,
        trigger_run_id: str,
        explanation: str,
        metadata: Optional[Dict[str, Any]] = None,
        event_timestamp: Optional[str] = None,
    ) -> LineageEvent:
        """Create and append a new lineage event."""
        if event_timestamp is None:
            event_timestamp = datetime.now(timezone.utc).isoformat()

        evt = LineageEvent(
            lineage_id=str(uuid.uuid4()),
            event_type=event_type,
            previous_entity_ids=sorted(list(set(previous_entity_ids))),
            current_entity_ids=sorted(list(set(current_entity_ids))),
            contributing_osm_ids=sorted(list(set(contributing_osm_ids))),
            contributing_ov_ids=sorted(list(set(contributing_ov_ids))),
            trigger_snapshot_id=trigger_snapshot_id,
            trigger_run_id=trigger_run_id,
            timestamp=event_timestamp,
            explanation=explanation,
            metadata=metadata or {},
        )
        self.events.append(evt)
        return evt

    def get_events_by_type(self, event_type: LineageEventType) -> List[LineageEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def get_history_for_canonical_id(self, canonical_id: str) -> List[LineageEvent]:
        """Retrieve all events referencing a given canonical ID (past or present)."""
        return [
            e for e in self.events
            if canonical_id in e.previous_entity_ids or canonical_id in e.current_entity_ids
        ]

    def get_history_for_source_id(self, source_id: str) -> List[LineageEvent]:
        """Retrieve all events involving a given source POI ID."""
        return [
            e for e in self.events
            if source_id in e.contributing_osm_ids or source_id in e.contributing_ov_ids
        ]

    def get_summary(self) -> Dict[str, int]:
        """Count events by event type."""
        summary = {t.value: 0 for t in LineageEventType}
        for e in self.events:
            summary[e.event_type.value] += 1
        summary["total_events"] = len(self.events)
        return summary

    def save(self, path: Path) -> None:
        """Persist lineage events to Parquet."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = [e.to_dict() for e in self.events]
        if not rows:
            # Empty table with schema
            schema = pa.schema([
                ("lineage_id", pa.string()),
                ("event_type", pa.string()),
                ("previous_entity_ids", pa.list_(pa.string())),
                ("current_entity_ids", pa.list_(pa.string())),
                ("contributing_osm_ids", pa.list_(pa.string())),
                ("contributing_ov_ids", pa.list_(pa.string())),
                ("trigger_snapshot_id", pa.string()),
                ("trigger_run_id", pa.string()),
                ("timestamp", pa.string()),
                ("explanation", pa.string()),
                ("metadata_json", pa.string()),
            ])
            tbl = pa.Table.from_batches([], schema=schema)
        else:
            tbl = pa.Table.from_pylist(rows)
        
        pq.write_table(tbl, path, compression="snappy")

    @classmethod
    def load(cls, path: Path) -> "LineageLedger":
        """Load lineage events from Parquet."""
        ledger = cls()
        path = Path(path)
        if not path.exists():
            return ledger
        
        tbl = pq.read_table(path)
        pydict = tbl.to_pylist()
        for d in pydict:
            evt = LineageEvent(
                lineage_id=d["lineage_id"],
                event_type=LineageEventType(d["event_type"]),
                previous_entity_ids=d.get("previous_entity_ids") or [],
                current_entity_ids=d.get("current_entity_ids") or [],
                contributing_osm_ids=d.get("contributing_osm_ids") or [],
                contributing_ov_ids=d.get("contributing_ov_ids") or [],
                trigger_snapshot_id=d.get("trigger_snapshot_id") or "",
                trigger_run_id=d.get("trigger_run_id") or "",
                timestamp=d.get("timestamp") or "",
                explanation=d.get("explanation") or "",
                metadata=json.loads(d["metadata_json"]) if d.get("metadata_json") else {},
            )
            ledger.events.append(evt)
        return ledger
