"""Master execution script for initializing POI Conflation Ground Truth Benchmark.

Executes:
1. Mutually exclusive stratified sampling of 500 candidate pairs across 10 difficulty strata.
2. Extraction of 50-pair pilot batch (5 per stratum) for initial human review.
3. Independent missed-match diagnostic audit of 120 unrepresented/weak OSM records.
4. Category-pruned candidate audit (100-pair sample across 11 incompatible rules).
5. Generation of versioned benchmark metadata manifest (v1.1.0, QUEUE_GENERATED).
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.benchmark.sampling import BenchmarkSampler
from src.poi_conflation.benchmark.missed_match import MissedMatchAuditor
from src.poi_conflation.benchmark.category_audit import CategoryPruneAuditor
from src.poi_conflation.benchmark.metadata import BenchmarkMetadataManager


def main():
    print("=" * 70)
    print("MILESTONE 6: BENCHMARK INTEGRITY & ANNOTATION PILOT SETUP")
    print("=" * 70)

    # 1. Mutually Exclusive Stratified Sampling
    print("\n[Stage 1/4] Executing Mutually Exclusive Stratified Sampling (500 queue + 50 pilot)...")
    sampler = BenchmarkSampler()
    queue_csv, pilot_csv, sample_report = sampler.export_queue()
    print(f"  -> Generated Main Queue:  {queue_csv}")
    print(f"  -> Generated Pilot Batch: {pilot_csv}")
    print(f"  -> Generated Report:      {sample_report}")

    # 2. Missed-Match Diagnostic Audit
    print("\n[Stage 2/4] Executing Independent Missed-Match Diagnostic Audit (120 POIs)...")
    auditor = MissedMatchAuditor()
    audit_csv, audit_report = auditor.export_audit()
    print(f"  -> Generated Audit CSV:   {audit_csv}")
    print(f"  -> Generated Report:      {audit_report}")

    # 3. Category Pruning Audit
    print("\n[Stage 3/4] Executing Category Pruning Audit (100 pairs across 11 rules)...")
    cat_auditor = CategoryPruneAuditor()
    pruned_csv, pruned_report = cat_auditor.export_audit()
    print(f"  -> Generated Pruned CSV:  {pruned_csv}")
    print(f"  -> Generated Report:      {pruned_report}")

    # 4. Benchmark Metadata Manifest
    print("\n[Stage 4/4] Generating Versioned Benchmark Lifecycle Manifest...")
    meta_mgr = BenchmarkMetadataManager()
    manifest = meta_mgr.generate_manifest(candidate_generation_commit="2a1e60f", seed=42)
    print(f"  -> Manifest written to {meta_mgr.manifest_path} and {meta_mgr.reports_manifest_path}")

    print("\n" + "=" * 70)
    print("BENCHMARK SETUP & PILOT PREPARATION COMPLETE")
    print("=" * 70)
    print(f"Main Queue Records:   {manifest['files']['annotation_queue_records']}")
    print(f"Pilot Batch Records:  {manifest['files']['pilot_batch_records']}")
    print(f"Missed Match Records: {manifest['files']['missed_match_audit_records']}")
    print(f"Benchmark Lifecycle:  {manifest['lifecycle_state']}")
    print(f"Benchmark Frozen?:    {manifest['is_frozen']}")


if __name__ == "__main__":
    main()
