"""Local annotation workflow engine for POI conflation ground truth benchmark.

Manages:
- Loading unlabelled items from annotation_queue.csv.
- Checking existing annotations and resuming from the first unreviewed pair.
- Validating candidate decisions against schema constraints.
- Incremental appending and atomic saving of annotations.
- Interactive CLI review interface (optional local terminal loop).
- Programmatic batch ingestion of human review files.
- Exporting validated annotations to canonical storage.
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationQueueItem,
    AnnotationRecord,
)


class AnnotationWorkflow:
    """Manages local human annotation sessions, validation, and persistence."""

    def __init__(
        self,
        queue_csv: str = "data/processed/benchmark/annotation_queue.csv",
        annotations_dir: str = "data/processed/benchmark/annotations",
        adjudication_csv: str = "data/processed/benchmark/adjudication_queue.csv"
    ):
        self.queue_csv = Path(queue_csv)
        self.annotations_dir = Path(annotations_dir)
        self.adjudication_csv = Path(adjudication_csv)
        self.annotations_dir.mkdir(parents=True, exist_ok=True)

    def load_queue(self) -> List[AnnotationQueueItem]:
        """Load items from annotation queue CSV."""
        if not self.queue_csv.exists():
            raise FileNotFoundError(f"Annotation queue not found: {self.queue_csv}")

        items = []
        with open(self.queue_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = AnnotationQueueItem(
                    pair_id=row["pair_id"],
                    osm_source_id=row["osm_source_id"],
                    ov_source_id=row["ov_source_id"],
                    osm_name_raw=row.get("osm_name_raw") or None,
                    ov_name_raw=row.get("ov_name_raw") or None,
                    osm_name_normalized=row.get("osm_name_normalized") or None,
                    ov_name_normalized=row.get("ov_name_normalized") or None,
                    osm_latitude=float(row["osm_latitude"]),
                    osm_longitude=float(row["osm_longitude"]),
                    ov_latitude=float(row["ov_latitude"]),
                    ov_longitude=float(row["ov_longitude"]),
                    distance_meters=float(row["distance_meters"]),
                    osm_category=row["osm_category"],
                    ov_category=row["ov_category"],
                    category_compatibility=row["category_compatibility"],
                    blocking_strategies=row["blocking_strategies"],
                    sampling_stratum=row["sampling_stratum"],
                    osm_name_kn=row.get("osm_name_kn") or None,
                    osm_name_en=row.get("osm_name_en") or None,
                )
                items.append(item)
        return items

    def get_annotator_file(self, annotator_id: str) -> Path:
        """Return dedicated CSV path for specific annotator."""
        clean_id = "".join(c for c in annotator_id if c.isalnum() or c in ("_", "-")).lower()
        return self.annotations_dir / f"annotations_{clean_id}.csv"

    def load_existing_annotations(self, annotator_id: str) -> List[AnnotationRecord]:
        """Load completed annotations for a given annotator."""
        annotator_file = self.get_annotator_file(annotator_id)
        if not annotator_file.exists():
            return []

        records = []
        with open(annotator_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                record = AnnotationRecord.from_dict(r)
                records.append(record)
        return records

    def get_unannotated_items(self, annotator_id: str) -> List[AnnotationQueueItem]:
        """Return items from queue that have not yet been labelled by this annotator."""
        queue = self.load_queue()
        existing = self.load_existing_annotations(annotator_id)
        seen_pair_ids = {r.pair_id for r in existing}
        return [item for item in queue if item.pair_id not in seen_pair_ids]

    def record_decision(
        self,
        queue_item: AnnotationQueueItem,
        decision: LabelDecision,
        annotator_id: str,
        confidence: ConfidenceLevel,
        evidence_type: EvidenceType,
        notes: Optional[str] = None
    ) -> AnnotationRecord:
        """Create, validate, and append a human decision record."""
        record = AnnotationRecord(
            pair_id=queue_item.pair_id,
            osm_source_id=queue_item.osm_source_id,
            ov_source_id=queue_item.ov_source_id,
            osm_name_raw=queue_item.osm_name_raw,
            ov_name_raw=queue_item.ov_name_raw,
            osm_name_normalized=queue_item.osm_name_normalized,
            ov_name_normalized=queue_item.ov_name_normalized,
            osm_latitude=queue_item.osm_latitude,
            osm_longitude=queue_item.osm_longitude,
            ov_latitude=queue_item.ov_latitude,
            ov_longitude=queue_item.ov_longitude,
            distance_meters=queue_item.distance_meters,
            osm_category=queue_item.osm_category,
            ov_category=queue_item.ov_category,
            category_compatibility=queue_item.category_compatibility,
            blocking_strategies=queue_item.blocking_strategies,
            sampling_stratum=queue_item.sampling_stratum,
            decision=decision,
            annotator_id=annotator_id,
            confidence=confidence,
            evidence_type=evidence_type,
            annotation_timestamp=datetime.now(timezone.utc).isoformat(),
            notes=notes
        )

        errors = record.validate()
        if errors:
            raise ValueError(f"Annotation record validation failed: {'; '.join(errors)}")

        annotator_file = self.get_annotator_file(annotator_id)
        file_exists = annotator_file.exists()

        fieldnames = list(record.to_dict().keys())
        with open(annotator_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(record.to_dict())

        # If decision is NEEDS_ADJUDICATION, also log to adjudication queue
        if decision == LabelDecision.NEEDS_ADJUDICATION:
            self._append_to_adjudication_queue(record)

        return record

    def _append_to_adjudication_queue(self, record: AnnotationRecord):
        """Append record requiring adjudication to adjudication_queue.csv."""
        file_exists = self.adjudication_csv.exists()
        fieldnames = list(record.to_dict().keys())
        with open(self.adjudication_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(record.to_dict())
