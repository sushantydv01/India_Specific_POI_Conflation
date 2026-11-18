"""Human adjudication subsystem for resolving POI annotation conflicts and ambiguous graph clusters.

Defines data models, adjudication queue management, decision consensus workflows,
and gold-standard benchmark persistence with strict provenance tracking.
"""

import csv
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationProvenance,
    AnnotationRecord,
)

logger = logging.getLogger("adjudication")


@dataclass
class AdjudicationRecord:
    """Represents a definitive decision made by a senior adjudicator resolving an annotation conflict."""
    pair_id: str
    adjudicator_id: str
    primary_review: Dict[str, Any]
    secondary_review: Optional[Dict[str, Any]]
    final_decision: str              # LabelDecision value
    confidence: str                  # ConfidenceLevel value
    evidence_type: str               # EvidenceType value
    rationale: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provenance: str = AnnotationProvenance.HUMAN_ADJUDICATED.value
    graph_context: Dict[str, Any] = field(default_factory=dict)
    osm_attributes: Dict[str, Any] = field(default_factory=dict)
    ov_attributes: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate integrity of the adjudication record."""
        errors: List[str] = []
        if not self.pair_id or "::" not in self.pair_id:
            errors.append(f"Invalid pair_id format: '{self.pair_id}'")
        if not self.adjudicator_id or not self.adjudicator_id.strip():
            errors.append("adjudicator_id is required")
        if self.final_decision not in [e.value for e in LabelDecision]:
            errors.append(f"Invalid final_decision: '{self.final_decision}'")
        if self.confidence not in [e.value for e in ConfidenceLevel]:
            errors.append(f"Invalid confidence: '{self.confidence}'")
        if self.evidence_type not in [e.value for e in EvidenceType]:
            errors.append(f"Invalid evidence_type: '{self.evidence_type}'")
        if not self.rationale or len(self.rationale.strip()) < 5:
            errors.append("Explicit rationale is required for adjudication")
        if self.provenance != AnnotationProvenance.HUMAN_ADJUDICATED.value:
            errors.append(f"Provenance must be {AnnotationProvenance.HUMAN_ADJUDICATED.value}")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdjudicationRecord":
        return cls(**data)


class AdjudicationWorkflow:
    """Manages the lifecycle of contested pairs from disagreement detection through final adjudication."""

    def __init__(
        self,
        benchmark_dir: str = "data/processed/benchmark",
        reports_dir: str = "reports",
    ):
        self.benchmark_dir = Path(benchmark_dir)
        self.reports_dir = Path(reports_dir)
        self.adjudication_dir = self.benchmark_dir / "adjudicated"
        self.adjudication_dir.mkdir(parents=True, exist_ok=True)
        self.adjudication_records_file = self.adjudication_dir / "adjudication_records.jsonl"
        self.adjudication_csv = self.benchmark_dir / "adjudication_queue.csv"

    def load_adjudicated_records(self) -> Dict[str, AdjudicationRecord]:
        """Load previously saved adjudication records indexed by pair_id."""
        if not self.adjudication_records_file.exists():
            return {}
        records: Dict[str, AdjudicationRecord] = {}
        with open(self.adjudication_records_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rec = AdjudicationRecord.from_dict(data)
                    records[rec.pair_id] = rec
                except Exception as e:
                    logger.warning(f"Error parsing adjudication line: {e}")
        return records

    def record_adjudication(self, record: AdjudicationRecord) -> None:
        """Persist a single validated adjudication record."""
        errors = record.validate()
        if errors:
            raise ValueError(f"Adjudication record validation failed: {'; '.join(errors)}")

        existing = self.load_adjudicated_records()
        existing[record.pair_id] = record

        with open(self.adjudication_records_file, "w", encoding="utf-8") as f:
            for rec in existing.values():
                f.write(json.dumps(rec.to_dict()) + "\n")

    def load_queue_items(self) -> List[Dict[str, Any]]:
        """Load pending queue items from adjudication_queue.csv."""
        if not self.adjudication_csv.exists():
            return []
        items = []
        with open(self.adjudication_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(dict(row))
        return items

    def generate_adjudication_summary(
        self,
        output_report: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Generate machine-readable summary report of all completed adjudications."""
        records = list(self.load_adjudicated_records().values())
        out_path = output_report or (self.reports_dir / "adjudication_summary.json")

        decision_counts: Dict[str, int] = {}
        confidence_counts: Dict[str, int] = {}
        evidence_counts: Dict[str, int] = {}
        alignment_with_r1 = 0
        alignment_with_r2 = 0
        novel_consensus = 0

        for r in records:
            decision_counts[r.final_decision] = decision_counts.get(r.final_decision, 0) + 1
            confidence_counts[r.confidence] = confidence_counts.get(r.confidence, 0) + 1
            evidence_counts[r.evidence_type] = evidence_counts.get(r.evidence_type, 0) + 1

            r1_dec = r.primary_review.get("decision") if r.primary_review else None
            r2_dec = r.secondary_review.get("decision") if r.secondary_review else None

            if r.final_decision == r1_dec:
                alignment_with_r1 += 1
            elif r2_dec and r.final_decision == r2_dec:
                alignment_with_r2 += 1
            else:
                novel_consensus += 1

        summary = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_cases_adjudicated": len(records),
                "provenance_standard": AnnotationProvenance.HUMAN_ADJUDICATED.value,
            },
            "decision_distribution": decision_counts,
            "confidence_distribution": confidence_counts,
            "evidence_type_distribution": evidence_counts,
            "annotator_resolution_breakdown": {
                "upheld_primary_reviewer": alignment_with_r1,
                "upheld_secondary_reviewer": alignment_with_r2,
                "novel_or_independent_resolution": novel_consensus,
            },
            "sample_adjudications": [
                {
                    "pair_id": r.pair_id,
                    "adjudicator_id": r.adjudicator_id,
                    "final_decision": r.final_decision,
                    "confidence": r.confidence,
                    "evidence_type": r.evidence_type,
                    "rationale": r.rationale,
                }
                for r in records[:5]
            ],
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary
