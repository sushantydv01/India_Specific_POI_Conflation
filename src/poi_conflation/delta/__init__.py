"""Delta ingestion and snapshot change detection package."""

from src.poi_conflation.delta.snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    compute_record_content_hash,
    SourceSnapshotManifest,
    build_snapshot_from_records,
)
from src.poi_conflation.delta.detector import (
    RecordDeltaType,
    SourceRecordDelta,
    SnapshotDeltaSummary,
    SourceDeltaDetector,
    detect_field_changes,
)

__all__ = [
    "SNAPSHOT_SCHEMA_VERSION",
    "compute_record_content_hash",
    "SourceSnapshotManifest",
    "build_snapshot_from_records",
    "RecordDeltaType",
    "SourceRecordDelta",
    "SnapshotDeltaSummary",
    "SourceDeltaDetector",
    "detect_field_changes",
]
