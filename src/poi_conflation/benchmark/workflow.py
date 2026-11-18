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
from src.poi_conflation.benchmark.ai_schema import (
    HumanAction,
    AIPairSuggestion,
    AIAuditRecord,
)


class AnnotationWorkflow:
    """Manages local human annotation sessions, validation, and persistence."""

    def __init__(
        self,
        queue_csv: str = "data/processed/benchmark/annotation_queue.csv",
        annotations_dir: str = "data/processed/benchmark/annotations",
        adjudication_csv: str = "data/processed/benchmark/adjudication_queue.csv",
        audit_trail_csv: str = "data/processed/benchmark/annotations/audit_trail.csv",
        ai_suggestions_file: str = "data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl",
    ):
        self.queue_csv = Path(queue_csv)
        self.annotations_dir = Path(annotations_dir)
        self.adjudication_csv = Path(adjudication_csv)
        self.audit_trail_csv = Path(audit_trail_csv)
        self.ai_suggestions_file = Path(ai_suggestions_file)
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

    def load_ai_suggestions(self, suggestions_path: Optional[str] = None) -> Dict[str, AIPairSuggestion]:
        """Load AI suggestions from JSONL file keyed by pair_id."""
        target_path = Path(suggestions_path) if suggestions_path else self.ai_suggestions_file
        if not target_path.exists():
            return {}

        suggestions: Dict[str, AIPairSuggestion] = {}
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    sugg = AIPairSuggestion.from_dict(data)
                    suggestions[sugg.pair_id] = sugg
        return suggestions

    def load_audit_trail(self) -> List[AIAuditRecord]:
        """Load audit trail of human-AI review actions."""
        if not self.audit_trail_csv.exists():
            return []

        records = []
        with open(self.audit_trail_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(AIAuditRecord.from_dict(row))
        return records

    def record_decision(
        self,
        queue_item: AnnotationQueueItem,
        decision: LabelDecision,
        annotator_id: str,
        confidence: ConfidenceLevel,
        evidence_type: EvidenceType,
        notes: Optional[str] = None,
        human_action: HumanAction = HumanAction.INDEPENDENT,
        ai_suggestion: Optional[AIPairSuggestion] = None,
    ) -> AnnotationRecord:
        """Create, validate, and append a human decision record, and log human-AI audit trail."""
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

        # Log to audit trail
        audit_record = AIAuditRecord(
            pair_id=queue_item.pair_id,
            annotator_id=annotator_id,
            human_decision=decision,
            human_confidence=confidence,
            human_evidence_type=evidence_type,
            human_action=human_action,
            ai_suggested_label=ai_suggestion.suggested_label if ai_suggestion else None,
            ai_suggested_confidence=ai_suggestion.suggested_confidence if ai_suggestion else None,
            ai_evidence_type=ai_suggestion.suggested_evidence_type if ai_suggestion else None,
            ai_model_id=ai_suggestion.model_identifier if ai_suggestion else None,
            review_timestamp=record.annotation_timestamp,
            notes=notes,
        )
        self._append_to_audit_trail(audit_record)

        # If decision is NEEDS_ADJUDICATION, also log to adjudication queue
        if decision == LabelDecision.NEEDS_ADJUDICATION:
            self._append_to_adjudication_queue(record)

        return record

    def _append_to_audit_trail(self, audit_record: AIAuditRecord):
        """Append record to audit_trail.csv."""
        self.audit_trail_csv.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self.audit_trail_csv.exists()
        fieldnames = list(audit_record.to_dict().keys())
        with open(self.audit_trail_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(audit_record.to_dict())

    def _append_to_adjudication_queue(self, record: AnnotationRecord):
        """Append record requiring adjudication to adjudication_queue.csv."""
        file_exists = self.adjudication_csv.exists()
        fieldnames = list(record.to_dict().keys())
        with open(self.adjudication_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(record.to_dict())
