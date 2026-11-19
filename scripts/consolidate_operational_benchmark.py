#!/usr/bin/env python3
"""Consolidate existing annotation and benchmark artifacts into an operational dataset for M15.

Audits all available labels:
- data/processed/benchmark/human_verified/benchmark_human_verified_v1.csv (Dataset C, 50 pairs)
- data/processed/benchmark/annotations/annotations_reviewer_1.csv (Dataset A human review, 1 pair)
- data/processed/benchmark/annotations/annotations_human_reviewer_1.csv (M11 human reviewer 1)
- data/processed/benchmark/annotations/annotations_human_reviewer_2.csv (M11 human reviewer 2)
- data/processed/benchmark/adjudicated/adjudication_records.jsonl (M11 adjudications)
- data/processed/benchmark/annotations/annotations_ai_auto_adopter.csv (Dataset A pilot, 50 pairs)
- data/processed/benchmark/pilot_annotations_adopted.csv (Dataset A pilot, 50 pairs)
- data/processed/benchmark/annotation_queue.csv (Dataset A representative sample, 500 pairs)

Precedence Rules:
1. HUMAN_ADJUDICATED > HUMAN_VERIFIED > AUTO_ADOPTED_AI > UNANNOTATED
2. Ambiguous/uncertain labels ('UNCERTAIN', 'NEEDS_ADJUDICATION') are preserved but flagged
   as excluded from binary training targets (is_binary_target=False).
3. The resulting dataset is explicitly framed as an AI-assisted operational benchmark,
   NOT as an independent gold standard.

Outputs:
- data/processed/benchmark/operational/operational_benchmark_consolidated.parquet
- data/processed/benchmark/operational/operational_benchmark_consolidated.csv
- reports/operational_benchmark_audit.json
"""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("consolidate_operational_benchmark")


def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_precedence_rank(provenance: str) -> int:
    ranks = {
        "HUMAN_ADJUDICATED": 4,
        "HUMAN_VERIFIED": 3,
        "AUTO_ADOPTED_AI": 2,
        "AI_GENERATED": 1,
        "UNANNOTATED": 0,
        "UNKNOWN": -1,
    }
    return ranks.get(provenance, 0)


def main():
    root = Path(__file__).resolve().parent.parent
    bench_dir = root / "data" / "processed" / "benchmark"
    annot_dir = bench_dir / "annotations"
    human_dir = bench_dir / "human_verified"
    output_dir = bench_dir / "operational"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load source datasets
    gold_50 = load_csv(human_dir / "benchmark_human_verified_v1.csv")
    queue_500 = load_csv(bench_dir / "annotation_queue.csv")
    pilot_adopted = load_csv(bench_dir / "pilot_annotations_adopted.csv")
    ai_adopter = load_csv(annot_dir / "annotations_ai_auto_adopter.csv")
    rev1 = load_csv(annot_dir / "annotations_reviewer_1.csv")
    h_rev1 = load_csv(annot_dir / "annotations_human_reviewer_1.csv")
    h_rev2 = load_csv(annot_dir / "annotations_human_reviewer_2.csv")

    logger.info(f"Loaded {len(gold_50)} Dataset C records")
    logger.info(f"Loaded {len(queue_500)} Dataset A representative sample records")
    logger.info(f"Loaded {len(pilot_adopted)} Dataset A pilot adopted records")
    logger.info(f"Loaded {len(rev1)} reviewer_1 manual records")

    # Map candidate pair IDs
    # Precedence-based record resolution dictionary: pair_id -> consolidated record
    consolidated_map: Dict[str, Dict[str, Any]] = {}

    # Helper to insert or update with precedence
    def register_record(
        pair_id: str,
        record_data: Dict[str, Any],
        source_file: str,
        provenance: str,
        decision: str,
        annotator_id: str,
        evidence_type: str = "",
        confidence: str = "",
        notes: str = "",
        timestamp: str = "",
    ):
        current = consolidated_map.get(pair_id)
        new_rank = get_precedence_rank(provenance)

        if current is not None:
            curr_rank = get_precedence_rank(current["provenance"])
            if new_rank <= curr_rank:
                # Keep existing record if higher or equal precedence
                return

        # Prepare new consolidated record
        consolidated_map[pair_id] = {
            "pair_id": pair_id,
            "osm_source_id": record_data.get("osm_source_id", ""),
            "ov_source_id": record_data.get("ov_source_id", ""),
            "osm_name_raw": record_data.get("osm_name_raw", ""),
            "ov_name_raw": record_data.get("ov_name_raw", ""),
            "osm_name_normalized": record_data.get("osm_name_normalized", ""),
            "ov_name_normalized": record_data.get("ov_name_normalized", ""),
            "osm_latitude": float(record_data.get("osm_latitude", 0.0)),
            "osm_longitude": float(record_data.get("osm_longitude", 0.0)),
            "ov_latitude": float(record_data.get("ov_latitude", 0.0)),
            "ov_longitude": float(record_data.get("ov_longitude", 0.0)),
            "distance_meters": float(record_data.get("distance_meters", 0.0)),
            "osm_category": record_data.get("osm_category", ""),
            "ov_category": record_data.get("ov_category", ""),
            "category_compatibility": record_data.get("category_compatibility", ""),
            "blocking_strategies": record_data.get("blocking_strategies", ""),
            "sampling_stratum": record_data.get("sampling_stratum", ""),
            "decision": decision,
            "annotator_id": annotator_id,
            "confidence": confidence,
            "evidence_type": evidence_type,
            "annotation_timestamp": timestamp,
            "notes": notes,
            "provenance": provenance,
            "source_benchmark": "DATASET_C_TARGETED_GOLD" if "benchmark_human_verified" in source_file else "DATASET_A_REPRESENTATIVE_PILOT",
            "source_file": source_file,
            "is_binary_target": decision in ("MATCH", "NON_MATCH"),
            "binary_label": 1 if decision == "MATCH" else (0 if decision == "NON_MATCH" else None),
        }

    # First, register AI-adopted pilot annotations
    for r in pilot_adopted:
        pid = r["pair_id"]
        # In pilot_annotations_adopted, reviewer_1 has provenance UNKNOWN_LEGACY or annotator_id reviewer_1
        prov = "HUMAN_VERIFIED" if r.get("annotator_id") == "reviewer_1" else "AUTO_ADOPTED_AI"
        register_record(
            pair_id=pid,
            record_data=r,
            source_file="pilot_annotations_adopted.csv",
            provenance=prov,
            decision=r.get("decision", ""),
            annotator_id=r.get("annotator_id", "ai_auto_adopter"),
            evidence_type=r.get("evidence_type", ""),
            confidence=r.get("confidence", ""),
            notes=r.get("notes", ""),
            timestamp=r.get("annotation_timestamp", ""),
        )

    # Next, register reviewer_1 human review (overrides AI adopted)
    for r in rev1:
        pid = r["pair_id"]
        register_record(
            pair_id=pid,
            record_data=r,
            source_file="annotations_reviewer_1.csv",
            provenance="HUMAN_VERIFIED",
            decision=r.get("decision", ""),
            annotator_id=r.get("annotator_id", "reviewer_1"),
            evidence_type=r.get("evidence_type", ""),
            confidence=r.get("confidence", "HIGH"),
            notes=r.get("notes", ""),
            timestamp=r.get("annotation_timestamp", ""),
        )

    # Next, register Dataset C human verified (gold standard 50)
    for r in gold_50:
        pid = r["pair_id"]
        prov = r.get("provenance", "HUMAN_VERIFIED")
        register_record(
            pair_id=pid,
            record_data=r,
            source_file="benchmark_human_verified_v1.csv",
            provenance=prov,
            decision=r.get("decision", ""),
            annotator_id=r.get("annotator_id", "human_reviewer"),
            evidence_type=r.get("evidence_type", ""),
            confidence=r.get("confidence", "HIGH"),
            notes=r.get("notes", ""),
            timestamp=r.get("annotation_timestamp", ""),
        )

    # Record total labeled universe
    labeled_records = list(consolidated_map.values())
    labeled_pair_ids = set(consolidated_map.keys())

    # Now add unannotated pairs from Dataset A (500 queue) so we have a complete inventory
    unannotated_records = []
    for r in queue_500:
        pid = r["pair_id"]
        if pid not in labeled_pair_ids:
            rec = {
                "pair_id": pid,
                "osm_source_id": r.get("osm_source_id", ""),
                "ov_source_id": r.get("ov_source_id", ""),
                "osm_name_raw": r.get("osm_name_raw", ""),
                "ov_name_raw": r.get("ov_name_raw", ""),
                "osm_name_normalized": r.get("osm_name_normalized", ""),
                "ov_name_normalized": r.get("ov_name_normalized", ""),
                "osm_latitude": float(r.get("osm_latitude", 0.0)),
                "osm_longitude": float(r.get("osm_longitude", 0.0)),
                "ov_latitude": float(r.get("ov_latitude", 0.0)),
                "ov_longitude": float(r.get("ov_longitude", 0.0)),
                "distance_meters": float(r.get("distance_meters", 0.0)),
                "osm_category": r.get("osm_category", ""),
                "ov_category": r.get("ov_category", ""),
                "category_compatibility": r.get("category_compatibility", ""),
                "blocking_strategies": r.get("blocking_strategies", ""),
                "sampling_stratum": r.get("sampling_stratum", ""),
                "decision": "UNANNOTATED",
                "annotator_id": "",
                "confidence": "",
                "evidence_type": "",
                "annotation_timestamp": "",
                "notes": "Representative sample pending annotation",
                "provenance": "UNANNOTATED",
                "source_benchmark": "DATASET_A_REPRESENTATIVE_QUEUE",
                "source_file": "annotation_queue.csv",
                "is_binary_target": False,
                "binary_label": None,
            }
            unannotated_records.append(rec)

    total_pool = labeled_records + unannotated_records
    logger.info(f"Consolidated {len(labeled_records)} labeled records + {len(unannotated_records)} unannotated records = {len(total_pool)} total pairs")

    # Metrics for audit report
    match_count = sum(1 for r in labeled_records if r["decision"] == "MATCH")
    non_match_count = sum(1 for r in labeled_records if r["decision"] == "NON_MATCH")
    uncertain_count = sum(1 for r in labeled_records if r["decision"] == "UNCERTAIN")
    needs_adj_count = sum(1 for r in labeled_records if r["decision"] == "NEEDS_ADJUDICATION")
    human_adj_count = sum(1 for r in labeled_records if r["provenance"] == "HUMAN_ADJUDICATED")
    human_ver_count = sum(1 for r in labeled_records if r["provenance"] == "HUMAN_VERIFIED")
    ai_adopted_count = sum(1 for r in labeled_records if r["provenance"] == "AUTO_ADOPTED_AI")

    audit_summary = {
        "metadata": {
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "milestone": "Milestone 15",
            "framework": "Operational Benchmark Consolidation",
            "operational_characterization": "AI-Assisted Operational Benchmark for Supervised POI Matching",
            "independent_human_gold_standard": False,
            "notes": "Combines Dataset C (50 human-verified pairs) with Dataset A pilot (49 AI-adopted + 1 human-verified pairs). Excludes ambiguous/uncertain labels from binary targets. Precedence strictly enforced."
        },
        "inventory": {
            "total_labeled_pairs": len(labeled_records),
            "total_unannotated_pairs": len(unannotated_records),
            "total_combined_sample": len(total_pool),
            "binary_classification_targets": {
                "total_binary_pairs": match_count + non_match_count,
                "MATCH": match_count,
                "NON_MATCH": non_match_count,
                "class_balance_match_pct": round(match_count / (match_count + non_match_count) * 100, 2),
                "class_balance_non_match_pct": round(non_match_count / (match_count + non_match_count) * 100, 2),
            },
            "excluded_non_binary_pairs": {
                "total_excluded": uncertain_count + needs_adj_count,
                "UNCERTAIN": uncertain_count,
                "NEEDS_ADJUDICATION": needs_adj_count,
                "handling_policy": "Excluded from binary target training/evaluation to prevent target pollution"
            },
            "provenance_breakdown": {
                "HUMAN_ADJUDICATED": human_adj_count,
                "HUMAN_VERIFIED": human_ver_count,
                "AUTO_ADOPTED_AI": ai_adopted_count,
                "human_verified_total": human_adj_count + human_ver_count,
                "human_verified_pct": round((human_adj_count + human_ver_count) / len(labeled_records) * 100, 2),
                "ai_adopted_pct": round(ai_adopted_count / len(labeled_records) * 100, 2),
            },
            "source_benchmark_breakdown": {
                "DATASET_C_TARGETED_GOLD": len([r for r in labeled_records if r["source_benchmark"] == "DATASET_C_TARGETED_GOLD"]),
                "DATASET_A_REPRESENTATIVE_PILOT": len([r for r in labeled_records if r["source_benchmark"] == "DATASET_A_REPRESENTATIVE_PILOT"]),
            }
        },
        "precedence_rules_applied": [
            "HUMAN_ADJUDICATED supersedes HUMAN_VERIFIED, AUTO_ADOPTED_AI, and UNANNOTATED",
            "HUMAN_VERIFIED supersedes AUTO_ADOPTED_AI and UNANNOTATED (e.g. node/3556214256 reviewed by reviewer_1)",
            "AUTO_ADOPTED_AI supersedes UNANNOTATED",
            "Ambiguous/uncertain decisions (UNCERTAIN, NEEDS_ADJUDICATION) retain provenance but have is_binary_target=False and binary_label=None"
        ]
    }

    # Write audit report
    audit_report_path = reports_dir / "operational_benchmark_audit.json"
    with open(audit_report_path, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)
    logger.info(f"Wrote audit report to {audit_report_path}")

    # Write output CSV (operational labeled dataset)
    csv_out_path = output_dir / "operational_benchmark_consolidated.csv"
    with open(csv_out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(labeled_records[0].keys()))
        writer.writeheader()
        writer.writerows(labeled_records)
    logger.info(f"Wrote CSV operational benchmark ({len(labeled_records)} pairs) to {csv_out_path}")

    # Write output Parquet (operational labeled dataset)
    parquet_out_path = output_dir / "operational_benchmark_consolidated.parquet"
    arrow_table = pa.Table.from_pylist(labeled_records)
    pq.write_table(arrow_table, parquet_out_path)
    logger.info(f"Wrote Parquet operational benchmark to {parquet_out_path}")

    # Also write complete sample CSV including unannotated records for full tracking
    full_csv_path = output_dir / "operational_benchmark_full_pool.csv"
    with open(full_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(total_pool[0].keys()))
        writer.writeheader()
        writer.writerows(total_pool)
    logger.info(f"Wrote full pool CSV ({len(total_pool)} pairs) to {full_csv_path}")

    print("--- Operational Benchmark Consolidation Summary ---")
    print(f"Total labeled pairs: {len(labeled_records)}")
    print(f"  - MATCH: {match_count}")
    print(f"  - NON_MATCH: {non_match_count}")
    print(f"  - UNCERTAIN / NEEDS_ADJUDICATION: {uncertain_count + needs_adj_count}")
    print(f"Provenance:")
    print(f"  - HUMAN_ADJUDICATED: {human_adj_count}")
    print(f"  - HUMAN_VERIFIED: {human_ver_count}")
    print(f"  - AUTO_ADOPTED_AI: {ai_adopted_count}")
    print(f"Unannotated representative pairs: {len(unannotated_records)}")
    print("Done!")


if __name__ == "__main__":
    main()
