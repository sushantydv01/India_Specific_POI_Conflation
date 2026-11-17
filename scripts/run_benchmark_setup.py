"""Master execution script for initializing POI Conflation Ground Truth Benchmark.

Executes:
1. Stratified sampling of 500 candidate pairs across 10 difficulty strata.
2. Independent missed-match diagnostic audit of 120 unrepresented/weak OSM records.
3. Initialization of annotation files and empty adjudication queue.
4. Generation of versioned benchmark metadata manifest.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.benchmark.sampling import BenchmarkSampler
from src.poi_conflation.benchmark.missed_match import MissedMatchAuditor
from src.poi_conflation.benchmark.metadata import BenchmarkMetadataManager


def main():
    print("=" * 70)
    print("MILESTONE 5: POI GROUND TRUTH BENCHMARK INITIALIZATION")
    print("=" * 70)

    # 1. Stratified Sampling
    print("\n[Stage 1/3] Executing Stratified Candidate Sampling (500 pairs)...")
    sampler = BenchmarkSampler()
    queue_csv, sample_report = sampler.export_queue()
    print(f"  -> Generated {queue_csv}")
    print(f"  -> Generated {sample_report}")

    # 2. Missed-Match Diagnostic Audit
    print("\n[Stage 2/3] Executing Independent Missed-Match Diagnostic Audit (120 POIs)...")
    auditor = MissedMatchAuditor()
    audit_csv, audit_report = auditor.export_audit()
    print(f"  -> Generated {audit_csv}")
    print(f"  -> Generated {audit_report}")

    # 3. Benchmark Metadata Manifest
    print("\n[Stage 3/3] Generating Versioned Benchmark Metadata Manifest...")
    meta_mgr = BenchmarkMetadataManager()
    manifest = meta_mgr.generate_manifest(candidate_generation_commit="2a1e60f", seed=42)
    print(f"  -> Manifest written to {meta_mgr.manifest_path} and {meta_mgr.reports_manifest_path}")

    print("\n" + "=" * 70)
    print("BENCHMARK SETUP COMPLETE")
    print("=" * 70)
    print(f"Queue Records:        {manifest['files']['annotation_queue_records']}")
    print(f"Missed Match Records: {manifest['files']['missed_match_audit_records']}")
    print(f"Benchmark Status:     {manifest['benchmark_status']}")


if __name__ == "__main__":
    main()
