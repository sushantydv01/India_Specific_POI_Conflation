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
    AnnotationProvenance,
    AnnotationQueueItem,
    AnnotationRecord,
)
from src.poi_conflation.benchmark.ai_schema import (
    HumanAction,
    AIPairSuggestion,
    AIAuditRecord,
)
from src.poi_conflation.benchmark.metadata import (
    BenchmarkMetadataManager,
    BenchmarkLifecycleState,
)


class AnnotationWorkflow:
    """Manages local human annotation sessions, validation, and persistence."""

    def __init__(
        self,
        queue_csv: str = "data/processed/benchmark/annotation_queue.csv",
        annotations_dir: str = "data/processed/benchmark/annotations",
        adjudication_csv: str = "data/processed/benchmark/adjudication_queue.csv",
        audit_trail_csv: Optional[str] = None,
        ai_suggestions_file: str = "data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl",
    ):
        self.queue_csv = Path(queue_csv)
        self.annotations_dir = Path(annotations_dir)
        self.adjudication_csv = Path(adjudication_csv)
        self.audit_trail_csv = Path(audit_trail_csv) if audit_trail_csv else self.annotations_dir / "audit_trail.csv"
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
                    try:
                        data = json.loads(line)
                        sugg = AIPairSuggestion.from_dict(data)
                        suggestions[sugg.pair_id] = sugg
                    except Exception:
                        continue
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

    def load_all_existing_annotations(self) -> Dict[str, List[AnnotationRecord]]:
        """Load all annotations across all annotators in annotations_dir, keyed by pair_id."""
        all_records: Dict[str, List[AnnotationRecord]] = {}
        for af in self.annotations_dir.glob("annotations_*.csv"):
            with open(af, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    rec = AnnotationRecord.from_dict(r)
                    all_records.setdefault(rec.pair_id, []).append(rec)
        return all_records

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
        provenance: str = AnnotationProvenance.HUMAN_VERIFIED.value,
    ) -> AnnotationRecord:
        """Create, validate, and append an annotation record, and log human-AI audit trail."""
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
            notes=notes,
            provenance=provenance,
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

    def auto_adopt_ai_suggestions(
        self,
        annotator_id: str = "ai_auto_adopter",
        suggestions_path: Optional[str] = None,
        report_path: Optional[str] = None,
        consolidated_csv_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Automatically adopt valid AI suggestions for unannotated pilot queue items.

        Guarantees:
        - Existing human annotations are preserved and never overwritten.
        - Strict provenance tracking distinguishes AI_GENERATED, AUTO_ADOPTED_AI, and HUMAN_VERIFIED.
        - Idempotent execution (running repeatedly does not duplicate records).
        - Comprehensive statistical and risk breakdown report is generated.
        - Benchmark lifecycle manifest is updated to AI_AUTO_ANNOTATED_PILOT.
        """
        import statistics
        from collections import Counter

        actual_report_path = Path(report_path) if report_path else (
            Path("reports/pilot_auto_adoption_report.json")
            if self.annotations_dir == Path("data/processed/benchmark/annotations")
            else self.annotations_dir.parent / "pilot_auto_adoption_report.json"
        )
        actual_consolidated_path = Path(consolidated_csv_path) if consolidated_csv_path else (
            Path("data/processed/benchmark/pilot_annotations_adopted.csv")
            if self.annotations_dir == Path("data/processed/benchmark/annotations")
            else self.annotations_dir.parent / "pilot_annotations_adopted.csv"
        )

        items = self.load_queue()
        suggestions = self.load_ai_suggestions(suggestions_path)
        all_existing = self.load_all_existing_annotations()
        existing_adopter_records = {r.pair_id: r for r in self.load_existing_annotations(annotator_id)}

        annotator_file = self.get_annotator_file(annotator_id)
        file_exists = annotator_file.exists()

        total_pairs = len(items)
        available_suggestions = len(suggestions)
        newly_adopted = 0
        already_adopted = 0
        preserved_human_count = 0
        missing_or_invalid = []
        conflicting_annotations = []
        consolidated_records: List[AnnotationRecord] = []

        label_counts: Counter = Counter()
        conf_counts: Counter = Counter()
        evidence_counts: Counter = Counter()
        stratum_counts: Dict[str, Counter] = {}
        distances_by_label: Dict[str, List[float]] = {}
        compat_counts: Counter = Counter()
        strategy_counts: Counter = Counter()

        # Risk tracking
        low_confidence_pairs: List[str] = []
        uncertain_pairs: List[str] = []
        adjudication_pairs: List[str] = []
        potential_false_positive_risks: List[Dict[str, Any]] = []
        potential_false_negative_risks: List[Dict[str, Any]] = []
        transliteration_pairs: List[str] = []
        insufficient_evidence_pairs: List[str] = []

        for item in items:
            pid = item.pair_id
            sugg = suggestions.get(pid)

            # Check for existing human annotation
            human_recs = [r for r in all_existing.get(pid, []) if r.annotator_id != annotator_id]
            existing_human = human_recs[0] if human_recs else None

            if existing_human:
                preserved_human_count += 1
                if sugg and sugg.suggested_label != existing_human.decision:
                    conflicting_annotations.append({
                        "pair_id": pid,
                        "human_annotator": existing_human.annotator_id,
                        "human_decision": existing_human.decision.value,
                        "human_confidence": existing_human.confidence.value,
                        "ai_suggested_label": sugg.suggested_label.value,
                        "ai_suggested_confidence": sugg.suggested_confidence.value,
                    })

            # Check if suggestion exists and is valid
            if not sugg:
                missing_or_invalid.append({"pair_id": pid, "reason": "suggestion_missing"})
                if existing_human:
                    consolidated_records.append(existing_human)
                continue

            val_errors = sugg.validate()
            if val_errors:
                missing_or_invalid.append({"pair_id": pid, "reason": f"validation_errors: {'; '.join(val_errors)}"})
                if existing_human:
                    consolidated_records.append(existing_human)
                continue

            # Check adoption for this annotator (idempotency)
            if pid in existing_adopter_records:
                already_adopted += 1
                adopter_rec = existing_adopter_records[pid]
            else:
                adopter_rec = AnnotationRecord(
                    pair_id=item.pair_id,
                    osm_source_id=item.osm_source_id,
                    ov_source_id=item.ov_source_id,
                    osm_name_raw=item.osm_name_raw,
                    ov_name_raw=item.ov_name_raw,
                    osm_name_normalized=item.osm_name_normalized,
                    ov_name_normalized=item.ov_name_normalized,
                    osm_latitude=item.osm_latitude,
                    osm_longitude=item.osm_longitude,
                    ov_latitude=item.ov_latitude,
                    ov_longitude=item.ov_longitude,
                    distance_meters=item.distance_meters,
                    osm_category=item.osm_category,
                    ov_category=item.ov_category,
                    category_compatibility=item.category_compatibility,
                    blocking_strategies=item.blocking_strategies,
                    sampling_stratum=item.sampling_stratum,
                    decision=sugg.suggested_label,
                    annotator_id=annotator_id,
                    confidence=sugg.suggested_confidence,
                    evidence_type=sugg.suggested_evidence_type,
                    annotation_timestamp=datetime.now(timezone.utc).isoformat(),
                    notes=f"Auto-adopted from {sugg.model_identifier}. {sugg.explanation}",
                    provenance=AnnotationProvenance.AUTO_ADOPTED_AI.value,
                )
                rec_errors = adopter_rec.validate()
                if rec_errors:
                    missing_or_invalid.append({"pair_id": pid, "reason": f"record_errors: {'; '.join(rec_errors)}"})
                    continue

                fieldnames = list(adopter_rec.to_dict().keys())
                with open(annotator_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if not file_exists and newly_adopted == 0:
                        writer.writeheader()
                    writer.writerow(adopter_rec.to_dict())

                audit_rec = AIAuditRecord(
                    pair_id=pid,
                    annotator_id=annotator_id,
                    human_decision=sugg.suggested_label,
                    human_confidence=sugg.suggested_confidence,
                    human_evidence_type=sugg.suggested_evidence_type,
                    human_action=HumanAction.AUTO_ADOPTED_AI,
                    ai_suggested_label=sugg.suggested_label,
                    ai_suggested_confidence=sugg.suggested_confidence,
                    ai_evidence_type=sugg.suggested_evidence_type,
                    ai_model_id=sugg.model_identifier,
                    review_timestamp=adopter_rec.annotation_timestamp,
                    notes="Automated adoption of deterministic heuristic suggestion",
                )
                self._append_to_audit_trail(audit_rec)
                newly_adopted += 1

            # In consolidated pilot dataset: preserve human record if present, else adopter record
            consolidated_records.append(existing_human if existing_human else adopter_rec)

            # Record stats
            lbl = sugg.suggested_label.value
            cnf = sugg.suggested_confidence.value
            evd = sugg.suggested_evidence_type.value
            label_counts[lbl] += 1
            conf_counts[cnf] += 1
            evidence_counts[evd] += 1

            strat = item.sampling_stratum
            if strat not in stratum_counts:
                stratum_counts[strat] = Counter()
            stratum_counts[strat][lbl] += 1

            distances_by_label.setdefault(lbl, []).append(item.distance_meters)
            compat_counts[item.category_compatibility] += 1
            for strat_part in item.blocking_strategies.split("+"):
                strategy_counts[strat_part] += 1

            # Risk and ambiguity tagging
            if sugg.suggested_confidence == ConfidenceLevel.LOW:
                low_confidence_pairs.append(pid)
            if sugg.suggested_label == LabelDecision.UNCERTAIN:
                uncertain_pairs.append(pid)
            if sugg.suggested_label == LabelDecision.NEEDS_ADJUDICATION or sugg.adjudication_recommended:
                adjudication_pairs.append(pid)
            if sugg.suggested_label == LabelDecision.MATCH and item.distance_meters > 25.0:
                potential_false_positive_risks.append({
                    "pair_id": pid,
                    "reason": f"MATCH at distance {item.distance_meters:.1f}m > 25m",
                    "osm_name": item.osm_name_raw,
                    "ov_name": item.ov_name_raw,
                })
            if sugg.suggested_label == LabelDecision.NON_MATCH and item.distance_meters <= 25.0:
                potential_false_negative_risks.append({
                    "pair_id": pid,
                    "reason": f"NON_MATCH at close distance {item.distance_meters:.1f}m <= 25m",
                    "osm_name": item.osm_name_raw,
                    "ov_name": item.ov_name_raw,
                })
            if item.sampling_stratum == "KANNADA_TRANSLITERATION" or sugg.suggested_evidence_type == EvidenceType.TRANSLITERATION_OR_PHONETIC_MATCH:
                transliteration_pairs.append(pid)
            if sugg.suggested_evidence_type == EvidenceType.INSUFFICIENT_EVIDENCE:
                insufficient_evidence_pairs.append(pid)

        # Write consolidated pilot dataset if path provided
        if actual_consolidated_path and consolidated_records:
            actual_consolidated_path.parent.mkdir(parents=True, exist_ok=True)
            with open(actual_consolidated_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(consolidated_records[0].to_dict().keys()))
                writer.writeheader()
                for rec in consolidated_records:
                    writer.writerow(rec.to_dict())

        # Distance distribution statistics
        distance_stats = {}
        for lbl, dists in distances_by_label.items():
            if dists:
                distance_stats[lbl] = {
                    "count": len(dists),
                    "min_meters": round(min(dists), 2),
                    "max_meters": round(max(dists), 2),
                    "mean_meters": round(statistics.mean(dists), 2),
                    "median_meters": round(statistics.median(dists), 2),
                }

        unannotated_pairs = [item.pair_id for item in items if item.pair_id not in existing_adopter_records and newly_adopted == 0]

        report_data = {
            "metadata": {
                "report_timestamp": datetime.now(timezone.utc).isoformat(),
                "queue_file": str(self.queue_csv),
                "annotator_id": annotator_id,
                "model_identifier": "heuristic_rule_v1",
                "adoption_policy": "deterministic_heuristic_adoption_preserving_human_annotations",
            },
            "dataset_coverage": {
                "total_pilot_pairs": total_pairs,
                "available_ai_suggestions": available_suggestions,
                "successfully_auto_adopted_total": already_adopted + newly_adopted,
                "newly_adopted_this_run": newly_adopted,
                "already_adopted_previously": already_adopted,
                "existing_human_annotations_preserved": preserved_human_count,
                "missing_or_invalid_suggestions_count": len(missing_or_invalid),
                "missing_or_invalid_details": missing_or_invalid,
                "conflicting_annotations_count": len(conflicting_annotations),
                "conflicting_details": conflicting_annotations,
                "unannotated_pairs_count": len(unannotated_pairs),
            },
            "label_distribution": {
                lbl: {"count": count, "percentage": round((count / total_pairs) * 100, 2)}
                for lbl, count in label_counts.items()
            },
            "confidence_distribution": {
                cnf: {"count": count, "percentage": round((count / total_pairs) * 100, 2)}
                for cnf, count in conf_counts.items()
            },
            "evidence_type_distribution": {
                evd: {"count": count, "percentage": round((count / total_pairs) * 100, 2)}
                for evd, count in evidence_counts.items()
            },
            "per_stratum_label_distribution": {
                strat: dict(counts) for strat, counts in stratum_counts.items()
            },
            "distance_distribution_by_label": distance_stats,
            "category_compatibility_distribution": dict(compat_counts),
            "blocking_strategy_distribution": dict(strategy_counts),
            "error_and_risk_analysis": {
                "low_confidence_decisions": {
                    "count": len(low_confidence_pairs),
                    "pair_ids": low_confidence_pairs,
                },
                "uncertain_decisions": {
                    "count": len(uncertain_pairs),
                    "pair_ids": uncertain_pairs,
                },
                "cases_requiring_adjudication": {
                    "count": len(adjudication_pairs),
                    "pair_ids": adjudication_pairs,
                },
                "potential_false_positive_risks": {
                    "count": len(potential_false_positive_risks),
                    "details": potential_false_positive_risks,
                },
                "potential_false_negative_risks": {
                    "count": len(potential_false_negative_risks),
                    "details": potential_false_negative_risks,
                },
                "transliteration_decisions": {
                    "count": len(transliteration_pairs),
                    "pair_ids": transliteration_pairs,
                },
                "insufficient_evidence_cases": {
                    "count": len(insufficient_evidence_pairs),
                    "pair_ids": insufficient_evidence_pairs,
                },
                "methodological_notice": (
                    "These risk indicators represent heuristic edge cases and classification sensitivity, "
                    "NOT confirmed ground truth errors. No precision, recall, or F1 metrics are asserted "
                    "without independent human validation."
                ),
            },
        }

        # Save report JSON
        if actual_report_path:
            actual_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(actual_report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

        # Update Benchmark Manifest
        reports_dir = "reports" if self.annotations_dir == Path("data/processed/benchmark/annotations") else str(self.annotations_dir.parent)
        meta_manager = BenchmarkMetadataManager(
            benchmark_dir=str(self.queue_csv.parent),
            reports_dir=reports_dir,
        )
        meta_manager.generate_manifest(
            lifecycle_state=BenchmarkLifecycleState.AI_AUTO_ANNOTATED_PILOT,
            annotation_metadata={
                "annotation_method": "automated_heuristic_adoption",
                "model_identifier": "heuristic_rule_v1",
                "total_processed_pairs": total_pairs,
                "auto_adopted_pairs": already_adopted + newly_adopted,
                "preserved_human_annotations": preserved_human_count,
                "provenance_breakdown": {
                    "AUTO_ADOPTED_AI": already_adopted + newly_adopted,
                    "HUMAN_VERIFIED": preserved_human_count,
                },
            },
            notes="Milestone 8: Automated AI adoption of heuristic suggestions for 50-pair pilot queue.",
        )

        return report_data

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
