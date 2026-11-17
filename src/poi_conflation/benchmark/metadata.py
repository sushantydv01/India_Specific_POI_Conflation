"""Benchmark versioning and lifecycle manifest management.

Defines formal benchmark lifecycle states:
- QUEUE_GENERATED: Stratified queue and pilot batch generated and validated.
- ANNOTATION_IN_PROGRESS: Human review is actively underway.
- ANNOTATION_COMPLETED: First-pass human annotation complete across target queue.
- ADJUDICATION_PENDING: Disagreements routed to adjudication queue awaiting consensus.
- ADJUDICATED: Consensus reached on all conflicted items.
- BENCHMARK_FROZEN: Canonical benchmark finalized and locked for evaluation.
"""

import json
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List


BENCHMARK_SCHEMA_VERSION = "1.1.0"


class BenchmarkLifecycleState(str, Enum):
    """Permitted lifecycle stages for the ground truth benchmark."""
    QUEUE_GENERATED = "QUEUE_GENERATED"
    ANNOTATION_IN_PROGRESS = "ANNOTATION_IN_PROGRESS"
    ANNOTATION_COMPLETED = "ANNOTATION_COMPLETED"
    ADJUDICATION_PENDING = "ADJUDICATION_PENDING"
    ADJUDICATED = "ADJUDICATED"
    BENCHMARK_FROZEN = "BENCHMARK_FROZEN"


class BenchmarkMetadataManager:
    """Creates and manages versioned benchmark lifecycle manifests."""

    def __init__(
        self,
        benchmark_dir: str = "data/processed/benchmark",
        reports_dir: str = "reports"
    ):
        self.benchmark_dir = Path(benchmark_dir)
        self.reports_dir = Path(reports_dir)
        self.manifest_path = self.benchmark_dir / "benchmark_metadata.json"
        self.reports_manifest_path = self.reports_dir / "benchmark_metadata.json"

    def determine_lifecycle_state(
        self,
        queue_count: int,
        adjudication_count: int,
        annotator_summary: Dict[str, int]
    ) -> BenchmarkLifecycleState:
        """Evaluate actual filesystem evidence to determine lifecycle state without manual override."""
        total_annotations = sum(annotator_summary.values())
        if total_annotations == 0:
            return BenchmarkLifecycleState.QUEUE_GENERATED
        if adjudication_count > 0:
            return BenchmarkLifecycleState.ADJUDICATION_PENDING
        if total_annotations < queue_count:
            return BenchmarkLifecycleState.ANNOTATION_IN_PROGRESS
        return BenchmarkLifecycleState.ANNOTATION_COMPLETED

    def generate_manifest(
        self,
        candidate_generation_commit: str = "2a1e60f",
        seed: int = 42,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive benchmark metadata manifest with verifiable lifecycle state."""
        queue_csv = self.benchmark_dir / "annotation_queue.csv"
        pilot_csv = self.benchmark_dir / "pilot_batch_50.csv"
        adjudication_csv = self.benchmark_dir / "adjudication_queue.csv"
        missed_match_csv = self.benchmark_dir / "missed_match_audit.csv"
        annotations_dir = self.benchmark_dir / "annotations"

        queue_count = 0
        if queue_csv.exists():
            with open(queue_csv, "r", encoding="utf-8") as f:
                queue_count = max(0, sum(1 for _ in f) - 1)

        pilot_count = 0
        if pilot_csv.exists():
            with open(pilot_csv, "r", encoding="utf-8") as f:
                pilot_count = max(0, sum(1 for _ in f) - 1)

        adjudication_count = 0
        if adjudication_csv.exists():
            with open(adjudication_csv, "r", encoding="utf-8") as f:
                adjudication_count = max(0, sum(1 for _ in f) - 1)

        missed_match_count = 0
        if missed_match_csv.exists():
            with open(missed_match_csv, "r", encoding="utf-8") as f:
                missed_match_count = max(0, sum(1 for _ in f) - 1)

        annotator_files = list(annotations_dir.glob("annotations_*.csv")) if annotations_dir.exists() else []
        annotator_summary = {}
        for af in annotator_files:
            with open(af, "r", encoding="utf-8") as f:
                cnt = max(0, sum(1 for _ in f) - 1)
            annotator_summary[af.stem] = cnt

        lifecycle_state = self.determine_lifecycle_state(queue_count, adjudication_count, annotator_summary)

        manifest = {
            "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
            "manifest_timestamp": datetime.now(timezone.utc).isoformat(),
            "target_city": "Bengaluru (BBMP), Karnataka, India",
            "boundary_relation_id": 7902476,
            "lifecycle_state": lifecycle_state.value,
            "is_frozen": lifecycle_state == BenchmarkLifecycleState.BENCHMARK_FROZEN,
            "source_snapshots": {
                "overture_places_release": "2026-10-21.0",
                "osm_geofabrik_extract": "2026-11-16T21:22:36Z",
                "canonical_poi_dataset": "data/processed/canonical_pois_h3.parquet",
                "candidate_pairs_dataset": "data/processed/candidate_pairs/candidate_pairs_union.parquet"
            },
            "candidate_generation_commit": candidate_generation_commit,
            "sampling_parameters": {
                "population_size": 605428,
                "main_queue_size": queue_count,
                "pilot_batch_size": pilot_count,
                "strata_count": 10,
                "random_seed": seed,
                "sampling_strategy": "Mutually Exclusive Priority Stratification (50 pairs per stratum)"
            },
            "files": {
                "annotation_queue_csv": str(queue_csv),
                "annotation_queue_records": queue_count,
                "pilot_batch_csv": str(pilot_csv),
                "pilot_batch_records": pilot_count,
                "adjudication_queue_csv": str(adjudication_csv),
                "adjudication_queue_records": adjudication_count,
                "missed_match_audit_csv": str(missed_match_csv),
                "missed_match_audit_records": missed_match_count,
                "annotator_files": annotator_summary
            },
            "lifecycle_definitions": {
                "QUEUE_GENERATED": "Review queue generated; awaiting human annotator review.",
                "ANNOTATION_IN_PROGRESS": "Human annotator sessions in progress.",
                "ANNOTATION_COMPLETED": "Full queue reviewed by primary annotator.",
                "ADJUDICATION_PENDING": "Inter-annotator conflicts queued for adjudication.",
                "ADJUDICATED": "All conflicts adjudicated by consensus.",
                "BENCHMARK_FROZEN": "Benchmark locked and approved for model evaluation."
            },
            "known_methodology_constraints": [
                "The 500-pair queue is a diagnostic difficulty-stratified sample, NOT a representative estimate of natural candidate prevalence.",
                "Benchmark remains in QUEUE_GENERATED status until human annotator review commences.",
                "Missed-match diagnostic audit (120 records) cannot be extrapolated to a global blocking recall metric without complete universe verification."
            ],
            "notes": notes or "Milestone 6 benchmark integrity, mutually exclusive stratification, and pilot batch preparation."
        }

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        with open(self.reports_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest
