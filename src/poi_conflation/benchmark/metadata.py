"""Benchmark versioning and metadata manifest management.

Tracks:
- Source snapshot versions (OSM PBF extract date, Overture release timestamp).
- Candidate generation commit hash.
- Annotation schema version (semver).
- Sampling configuration and random seed.
- Current queue, annotation, adjudication, and audit file counts and statuses.
- Known methodology constraints and limitations.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


BENCHMARK_SCHEMA_VERSION = "1.0.0"


class BenchmarkMetadataManager:
    """Creates and updates versioned benchmark manifest in data/processed/benchmark/."""

    def __init__(
        self,
        benchmark_dir: str = "data/processed/benchmark",
        reports_dir: str = "reports"
    ):
        self.benchmark_dir = Path(benchmark_dir)
        self.reports_dir = Path(reports_dir)
        self.manifest_path = self.benchmark_dir / "benchmark_metadata.json"
        self.reports_manifest_path = self.reports_dir / "benchmark_metadata.json"

    def generate_manifest(
        self,
        candidate_generation_commit: str = "2a1e60f",
        seed: int = 42,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive benchmark metadata manifest."""
        queue_csv = self.benchmark_dir / "annotation_queue.csv"
        adjudication_csv = self.benchmark_dir / "adjudication_queue.csv"
        missed_match_csv = self.benchmark_dir / "missed_match_audit.csv"
        annotations_dir = self.benchmark_dir / "annotations"

        # Count lines in files
        queue_count = 0
        if queue_csv.exists():
            with open(queue_csv, "r", encoding="utf-8") as f:
                queue_count = max(0, sum(1 for _ in f) - 1)

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

        manifest = {
            "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
            "manifest_timestamp": datetime.now(timezone.utc).isoformat(),
            "target_city": "Bengaluru (BBMP), Karnataka, India",
            "boundary_relation_id": 7902476,
            "source_snapshots": {
                "overture_places_release": "2026-10-21.0",
                "osm_geofabrik_extract": "2026-11-16T21:22:36Z",
                "canonical_poi_dataset": "data/processed/canonical_pois_h3.parquet",
                "candidate_pairs_dataset": "data/processed/candidate_pairs/candidate_pairs_union.parquet"
            },
            "candidate_generation_commit": candidate_generation_commit,
            "sampling_parameters": {
                "population_size": 605428,
                "sample_size": queue_count,
                "strata_count": 10,
                "target_per_stratum": 50,
                "random_seed": seed,
                "sampling_strategy": "Deterministic stratified random sampling across 10 difficulty strata"
            },
            "files": {
                "annotation_queue_csv": str(queue_csv),
                "annotation_queue_records": queue_count,
                "adjudication_queue_csv": str(adjudication_csv),
                "adjudication_queue_records": adjudication_count,
                "missed_match_audit_csv": str(missed_match_csv),
                "missed_match_audit_records": missed_match_count,
                "annotator_files": annotator_summary
            },
            "known_limitations": [
                "Annotation queue is a stratified diagnostic sample (500 pairs) and is not representative of random pair distribution.",
                "Candidate pairs do not constitute matches; ground truth decisions must not be inferred automatically.",
                "Missed-match audit demonstrates that ~39% of unrepresented OSM POIs have zero presence in Overture directories.",
                "Cohen's Kappa is sensitive to category prevalence and class imbalance."
            ],
            "benchmark_status": "QUEUE_GENERATED_AND_INITIALIZED",
            "notes": notes or "Initial Milestone 5 human ground truth benchmark initialization."
        }

        # Write manifest to data/processed/benchmark/ and reports/
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        with open(self.reports_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest
