"""Inter-annotator agreement and quality control module for POI conflation benchmark.

Calculates:
- Overlapping annotation volume between annotator pairs.
- Observed percent agreement (p_o).
- Expected agreement by chance (p_e).
- Cohen's Kappa:
    kappa = (p_o - p_e) / (1.0 - p_e)
- Confusion / cross-tabulation matrix.
- Automatic routing of disagreed decisions to adjudication_queue.csv.
- Tracking of uncertain decisions and confidence distributions.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    AnnotationRecord,
)


class AgreementEvaluator:
    """Evaluates inter-annotator reliability and routes conflicts to adjudication."""

    def __init__(
        self,
        annotations_dir: str = "data/processed/benchmark/annotations",
        adjudication_csv: str = "data/processed/benchmark/adjudication_queue.csv"
    ):
        self.annotations_dir = Path(annotations_dir)
        self.adjudication_csv = Path(adjudication_csv)

    def load_all_annotator_records(self) -> Dict[str, List[AnnotationRecord]]:
        """Load annotations grouped by annotator_id."""
        files = list(self.annotations_dir.glob("annotations_*.csv"))
        annotator_data: Dict[str, List[AnnotationRecord]] = defaultdict(list)

        for f in files:
            with open(f, "r", encoding="utf-8") as fp:
                reader = csv.DictReader(fp)
                for r in reader:
                    rec = AnnotationRecord.from_dict(r)
                    annotator_data[rec.annotator_id].append(rec)
        return annotator_data

    def evaluate_pair_agreement(
        self,
        annotator_a: str,
        annotator_b: str,
        records_a: Optional[List[AnnotationRecord]] = None,
        records_b: Optional[List[AnnotationRecord]] = None
    ) -> Dict[str, Any]:
        """Compute pairwise Cohen's Kappa and confusion matrix between two annotators."""
        if records_a is None or records_b is None:
            all_records = self.load_all_annotator_records()
            records_a = all_records.get(annotator_a, [])
            records_b = all_records.get(annotator_b, [])

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
                "disagreements": 0,
                "uncertain_count": 0,
                "note": "No overlapping annotated pairs found between these annotators"
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

        return {
            "annotator_a": annotator_a,
            "annotator_b": annotator_b,
            "overlapping_pairs": pairs_total,
            "agreements": agreements,
            "disagreements": disagreements,
            "raw_agreement_pct": round(p_o * 100.0, 2),
            "cohens_kappa": kappa,
            "expected_agreement_pe": round(p_e, 4),
            "uncertain_count": uncertain_count,
            "confusion_matrix": matrix,
            "disagreed_pairs": disagree_items
        }

    def sync_disagreements_to_adjudication_queue(self, evaluation: Dict[str, Any]) -> int:
        """Route disagreements from pairwise evaluation to adjudication_queue.csv."""
        disagreed = evaluation.get("disagreed_pairs", [])
        if not disagreed:
            return 0

        existing_pids: Set[str] = set()
        if self.adjudication_csv.exists():
            with open(self.adjudication_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    existing_pids.add(r["pair_id"])

        all_records = self.load_all_annotator_records()
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
                # Pick record from annotator A as template, set decision to NEEDS_ADJUDICATION
                rec_a = next(r for r in all_records[item["annotator_a"]] if r.pair_id == pid)
                d = rec_a.to_dict()
                d["decision"] = LabelDecision.NEEDS_ADJUDICATION.value
                d["annotator_id"] = "consensus_system"
                d["notes"] = f"Conflict: {item['annotator_a']} marked '{item['decision_a']}' vs {item['annotator_b']} marked '{item['decision_b']}'"
                writer.writerow(d)
                existing_pids.add(pid)
                appended += 1

        return appended
