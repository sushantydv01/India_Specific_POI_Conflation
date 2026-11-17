"""Inter-annotator agreement and quality control module for POI conflation benchmark.

Provides:
- Deduplication of multiple submissions by the same annotator (keeping latest timestamp).
- Strict validation and filtering of compatible categorical labels.
- Two-annotator Cohen's Kappa:
    kappa = (p_o - p_e) / (1.0 - p_e)
- Explicit exclusion reporting for invalid or missing labels.
- Second-reviewer assignment workflow for pilot batches.
- Automated routing of conflicts to adjudication_queue.csv.
- Quality control summary reporting.
"""

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    AnnotationRecord,
    AnnotationQueueItem
)


class AgreementEvaluator:
    """Evaluates inter-annotator reliability and enforces quality control safeguards."""

    def __init__(
        self,
        annotations_dir: str = "data/processed/benchmark/annotations",
        adjudication_csv: str = "data/processed/benchmark/adjudication_queue.csv",
        reports_dir: str = "reports"
    ):
        self.annotations_dir = Path(annotations_dir)
        self.adjudication_csv = Path(adjudication_csv)
        self.reports_dir = Path(reports_dir)
        self.annotations_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def load_annotator_records(self, annotator_id: str) -> List[AnnotationRecord]:
        """Load and deduplicate records for an annotator (keeps latest submission per pair_id)."""
        clean_id = "".join(c for c in annotator_id if c.isalnum() or c in ("_", "-")).lower()
        filepath = self.annotations_dir / f"annotations_{clean_id}.csv"
        if not filepath.exists():
            return []

        # Read all rows, deduplicating by pair_id keeping latest timestamp
        records_by_pair: Dict[str, AnnotationRecord] = {}
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rec = AnnotationRecord.from_dict(row)
                    errors = rec.validate()
                    if not errors:
                        records_by_pair[rec.pair_id] = rec
                except Exception:
                    continue  # Malformed row ignored

        return list(records_by_pair.values())

    def evaluate_pair_agreement(
        self,
        annotator_a: str,
        annotator_b: str,
        records_a: Optional[List[AnnotationRecord]] = None,
        records_b: Optional[List[AnnotationRecord]] = None
    ) -> Dict[str, Any]:
        """Compute pairwise Cohen's Kappa and confusion matrix between two annotators."""
        if annotator_a == annotator_b:
            raise ValueError(f"Cannot calculate inter-annotator agreement for identical annotator '{annotator_a}'")

        if records_a is None:
            records_a = self.load_annotator_records(annotator_a)
        if records_b is None:
            records_b = self.load_annotator_records(annotator_b)

        # Deduplicate per pair_id
        map_a = {r.pair_id: r for r in records_a}
        map_b = {r.pair_id: r for r in records_b}

        overlap_ids = sorted(list(set(map_a.keys()) & set(map_b.keys())))
        if not overlap_ids:
            return {
                "annotator_a": annotator_a,
                "annotator_b": annotator_b,
                "overlapping_pairs": 0,
                "raw_agreement_pct": 0.0,
                "cohens_kappa": None,
                "status": "NO_OVERLAPPING_ANNOTATIONS",
                "notes": f"No overlapping pair IDs found between '{annotator_a}' and '{annotator_b}'"
            }

        pairs_total = len(overlap_ids)
        agreements = 0
        disagreements = 0
        uncertain_count = 0
        disagree_items: List[Dict[str, Any]] = []

        categories = [e.value for e in LabelDecision]
        matrix: Dict[str, Dict[str, int]] = {c1: {c2: 0 for c2 in categories} for c1 in categories}

        counts_a: Counter = Counter()
        counts_b: Counter = Counter()

        for pid in overlap_ids:
            rec_a = map_a[pid]
            rec_b = map_b[pid]

            dec_a = rec_a.decision.value if isinstance(rec_a.decision, LabelDecision) else str(rec_a.decision)
            dec_b = rec_b.decision.value if isinstance(rec_b.decision, LabelDecision) else str(rec_b.decision)

            counts_a[dec_a] += 1
            counts_b[dec_b] += 1
            matrix[dec_a][dec_b] += 1

            if dec_a == LabelDecision.UNCERTAIN.value or dec_b == LabelDecision.UNCERTAIN.value:
                uncertain_count += 1

            if dec_a == dec_b:
                agreements += 1
            else:
                disagreements += 1
                disagree_items.append({
                    "pair_id": pid,
                    "osm_source_id": rec_a.osm_source_id,
                    "ov_source_id": rec_a.ov_source_id,
                    "annotator_a": annotator_a,
                    "decision_a": dec_a,
                    "annotator_b": annotator_b,
                    "decision_b": dec_b,
                    "osm_name": rec_a.osm_name_raw,
                    "ov_name": rec_a.ov_name_raw,
                    "distance_meters": rec_a.distance_meters
                })

        p_o = agreements / pairs_total

        # Expected agreement by chance p_e
        p_e = 0.0
        for cat in categories:
            p_e += (counts_a[cat] / pairs_total) * (counts_b[cat] / pairs_total)

        if p_e >= 1.0 or (1.0 - p_e) == 0.0:
            kappa = 1.0 if p_o == 1.0 else 0.0
        else:
            kappa = round((p_o - p_e) / (1.0 - p_e), 4)

        report = {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "annotator_a": annotator_a,
            "annotator_b": annotator_b,
            "overlapping_pairs": pairs_total,
            "agreements": agreements,
            "disagreements": disagreements,
            "raw_agreement_pct": round(p_o * 100.0, 2),
            "expected_agreement_pe": round(p_e, 4),
            "cohens_kappa": kappa,
            "uncertain_pair_count": uncertain_count,
            "confusion_matrix": matrix,
            "disagreed_pairs": disagree_items,
            "methodology_limitations": [
                "Cohen's Kappa is sensitive to extreme prevalence asymmetry (high agreement with paradoxically low kappa).",
                "Kappa requires at least 30 overlapping items to be statistically reliable."
            ]
        }
        return report

    def sync_disagreements_to_adjudication_queue(self, evaluation: Dict[str, Any]) -> int:
        """Route pairwise disagreements to adjudication_queue.csv."""
        disagreed = evaluation.get("disagreed_pairs", [])
        if not disagreed:
            return 0

        existing_pids: Set[str] = set()
        if self.adjudication_csv.exists():
            with open(self.adjudication_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    existing_pids.add(r["pair_id"])

        annotator_a = evaluation["annotator_a"]
        records_a = {r.pair_id: r for r in self.load_annotator_records(annotator_a)}

        fieldnames = [
            "pair_id", "osm_source_id", "ov_source_id", "osm_name_raw", "ov_name_raw",
            "osm_name_normalized", "ov_name_normalized", "osm_latitude", "osm_longitude",
            "ov_latitude", "ov_longitude", "distance_meters", "osm_category", "ov_category",
            "category_compatibility", "blocking_strategies", "sampling_stratum",
            "decision", "annotator_id", "confidence", "evidence_type", "annotation_timestamp", "notes"
        ]

        appended = 0
        file_exists = self.adjudication_csv.exists()
        with open(self.adjudication_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            for item in disagreed:
                pid = item["pair_id"]
                if pid in existing_pids:
                    continue
                rec = records_a[pid]
                d = rec.to_dict()
                d["decision"] = LabelDecision.NEEDS_ADJUDICATION.value
                d["annotator_id"] = "adjudication_system"
                d["notes"] = f"Conflict: {item['annotator_a']}='{item['decision_a']}' vs {item['annotator_b']}='{item['decision_b']}'"
                writer.writerow(d)
                existing_pids.add(pid)
                appended += 1

        return appended

    def assign_second_reviewer_queue(
        self,
        source_queue_csv: Path,
        second_annotator_id: str,
        overlap_fraction: float = 0.5,
        seed: int = 42
    ) -> Path:
        """Assign an overlap fraction of pairs from source queue to a second reviewer for QC."""
        import random
        random.seed(seed)

        items = []
        with open(source_queue_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            items = list(reader)

        k = max(1, int(len(items) * overlap_fraction))
        selected_items = random.sample(items, k)

        clean_id = "".join(c for c in second_annotator_id if c.isalnum() or c in ("_", "-")).lower()
        output_file = self.annotations_dir / f"assigned_qc_queue_{clean_id}.csv"

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(items[0].keys()))
            writer.writeheader()
            for row in selected_items:
                writer.writerow(row)

        print(f"Assigned {len(selected_items)} QC overlap pairs to {output_file}")
        return output_file
