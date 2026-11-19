"""Evaluation benchmark provenance management and dual-view dataset construction.

Establishes strict, uncompromised provenance tracking for all candidate pair annotations:
- HUMAN_DUAL_REVIEWED: Independently reviewed by 2 annotators with consensus or senior adjudication.
- HUMAN_REVIEWED: Reviewed by a single human annotator.
- AI_ADOPTED: Heuristic/AI suggestions automatically adopted without direct human inspection.
- AI_GENERATED: Raw, unadopted AI suggestions.
- HEURISTIC: Deterministic rule proposals.
- UNREVIEWED: Unannotated candidate pairs from population or queues.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger("benchmark_provenance")


class EvaluationProvenance(str, Enum):
    """Explicit provenance categories for conflation evaluation labels."""
    HUMAN_DUAL_REVIEWED = "HUMAN_DUAL_REVIEWED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    AI_ADOPTED = "AI_ADOPTED"
    AI_GENERATED = "AI_GENERATED"
    HEURISTIC = "HEURISTIC"
    UNREVIEWED = "UNREVIEWED"


class EvaluationViewType(str, Enum):
    """Evaluation dataset views."""
    GOLD_HUMAN = "GOLD_HUMAN"
    CONSOLIDATED_OPERATIONAL = "CONSOLIDATED_OPERATIONAL"
    REPRESENTATIVE_POPULATION = "REPRESENTATIVE_POPULATION"
    CHALLENGE_DIFFICULTY = "CHALLENGE_DIFFICULTY"


@dataclass
class EvaluationRecord:
    """Standardized record for benchmark evaluation with full provenance lineage."""
    pair_id: str
    osm_source_id: str
    ov_source_id: str
    osm_name_raw: str
    ov_name_raw: str
    osm_name_norm: str
    ov_name_norm: str
    osm_category: str
    ov_category: str
    distance_meters: float
    ground_truth_decision: Optional[str]  # MATCH, NON_MATCH, UNCERTAIN, NEEDS_ADJUDICATION, None
    binary_label: Optional[int]           # 1 (match), 0 (non-match), None (uncertain/unannotated)
    provenance: EvaluationProvenance
    annotator_ids: List[str] = field(default_factory=list)
    review_timestamps: List[str] = field(default_factory=list)
    initial_decisions: Dict[str, str] = field(default_factory=dict)
    adjudication_rationale: Optional[str] = None
    is_gold_standard: bool = False
    is_challenge_case: bool = False
    sampling_stratum: Optional[str] = None
    partition_split: Optional[str] = None # train, validation, test, pool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "osm_source_id": self.osm_source_id,
            "ov_source_id": self.ov_source_id,
            "osm_name_raw": self.osm_name_raw,
            "ov_name_raw": self.ov_name_raw,
            "osm_name_norm": self.osm_name_norm,
            "ov_name_norm": self.ov_name_norm,
            "osm_category": self.osm_category,
            "ov_category": self.ov_category,
            "distance_meters": self.distance_meters,
            "ground_truth_decision": self.ground_truth_decision,
            "binary_label": self.binary_label,
            "provenance": self.provenance.value,
            "annotator_ids": json.dumps(self.annotator_ids),
            "review_timestamps": json.dumps(self.review_timestamps),
            "initial_decisions": json.dumps(self.initial_decisions),
            "adjudication_rationale": self.adjudication_rationale,
            "is_gold_standard": self.is_gold_standard,
            "is_challenge_case": self.is_challenge_case,
            "sampling_stratum": self.sampling_stratum,
            "partition_split": self.partition_split,
            "metadata_json": json.dumps(self.metadata, ensure_ascii=False),
        }


class BenchmarkProvenanceAuditor:
    """Inspects all historical and active annotation artifacts to assemble auditable benchmarks."""

    def __init__(self, project_root: Optional[Path] = None):
        self.root = project_root or Path(".")

    def assemble_audited_records(self) -> Dict[str, EvaluationRecord]:
        """Load and resolve authoritative provenance across all annotation records."""
        con = duckdb.connect()

        # 1. Load Human Annotator 1 (50 pairs)
        rev1_path = self.root / "data/processed/benchmark/annotations/annotations_human_reviewer_1.csv"
        rev1_dict: Dict[str, Dict[str, Any]] = {}
        if rev1_path.exists():
            rows = con.sql(f"SELECT * FROM read_csv_auto('{rev1_path}')").to_arrow_table().to_pylist()
            for r in rows:
                rev1_dict[r["pair_id"]] = r

        # 2. Load Human Annotator 2 (20 dual-review pairs)
        rev2_path = self.root / "data/processed/benchmark/annotations/annotations_human_reviewer_2.csv"
        rev2_dict: Dict[str, Dict[str, Any]] = {}
        if rev2_path.exists():
            rows = con.sql(f"SELECT * FROM read_csv_auto('{rev2_path}')").to_arrow_table().to_pylist()
            for r in rows:
                rev2_dict[r["pair_id"]] = r

        # 3. Load Adjudication Records (3 adjudicated disputes)
        adj_path = self.root / "data/processed/benchmark/adjudicated/adjudication_records.jsonl"
        adj_dict: Dict[str, Dict[str, Any]] = {}
        if adj_path.exists():
            with open(adj_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        adj_dict[d["pair_id"]] = d

        # 4. Load AI Adopted Pilot Annotations (50 pairs)
        pilot_path = self.root / "data/processed/benchmark/pilot_annotations_adopted.csv"
        pilot_dict: Dict[str, Dict[str, Any]] = {}
        if pilot_path.exists():
            rows = con.sql(f"SELECT * FROM read_csv_auto('{pilot_path}')").to_arrow_table().to_pylist()
            for r in rows:
                pilot_dict[r["pair_id"]] = r

        # 5. Load Full Benchmark Pool (550 pairs with partition splits)
        pool_path = self.root / "data/processed/benchmark/operational/operational_benchmark_full_pool.csv"
        pool_dict: Dict[str, Dict[str, Any]] = {}
        if pool_path.exists():
            rows = con.sql(f"SELECT * FROM read_csv_auto('{pool_path}')").to_arrow_table().to_pylist()
            for r in rows:
                pool_dict[r["pair_id"]] = r

        # 6. Load Partition Mappings (train, validation, test)
        partitions_dict: Dict[str, str] = {}
        for split_name in ["train", "validation", "test"]:
            feat_split_path = self.root / f"data/processed/supervised/{split_name}_features.parquet"
            if feat_split_path.exists():
                tbl = pq.read_table(feat_split_path, columns=["pair_id"])
                for pid in tbl["pair_id"].to_pylist():
                    partitions_dict[pid] = split_name
            else:
                part_path = self.root / f"data/processed/benchmark/partitions/{split_name}_partition.csv"
                if part_path.exists():
                    part_rows = con.sql(f"SELECT pair_id, partition_split FROM read_csv_auto('{part_path}')").to_arrow_table().to_pylist()
                    for pr in part_rows:
                        partitions_dict[pr["pair_id"]] = split_name

        # Synthesize records
        all_pair_ids = sorted(list(set(list(pool_dict.keys()) + list(rev1_dict.keys()) + list(pilot_dict.keys()))))
        audited_records: Dict[str, EvaluationRecord] = {}

        for pid in all_pair_ids:
            p_base = pool_dict.get(pid) or rev1_dict.get(pid) or pilot_dict.get(pid) or {}
            osm_name = str(p_base.get("osm_name_raw") or "")
            ov_name = str(p_base.get("ov_name_raw") or "")
            osm_norm = str(p_base.get("osm_name_normalized") or osm_name.lower())
            ov_norm = str(p_base.get("ov_name_normalized") or ov_name.lower())
            dist_m = float(p_base.get("distance_meters") or 0.0)
            osm_cat = str(p_base.get("osm_category") or "unknown")
            ov_cat = str(p_base.get("ov_category") or "unknown")
            split = partitions_dict.get(pid) or p_base.get("partition_split")
            stratum = p_base.get("sampling_stratum")

            annotators: List[str] = []
            timestamps: List[str] = []
            initial_decs: Dict[str, str] = {}
            adjudication_rationale: Optional[str] = None
            provenance: EvaluationProvenance = EvaluationProvenance.UNREVIEWED
            final_decision: Optional[str] = None

            # Check if adjudicated
            if pid in adj_dict:
                provenance = EvaluationProvenance.HUMAN_DUAL_REVIEWED
                adj = adj_dict[pid]
                annotators = ["human_reviewer_1", "human_reviewer_2", adj.get("adjudicator_id", "senior_adjudicator")]
                timestamps.append(adj.get("timestamp", ""))
                initial_decs["human_reviewer_1"] = adj.get("primary_review", {}).get("decision", "")
                initial_decs["human_reviewer_2"] = adj.get("secondary_review", {}).get("decision", "")
                adjudication_rationale = adj.get("rationale")
                final_decision = adj.get("final_decision")
            # Check if dual reviewed
            elif pid in rev1_dict and pid in rev2_dict:
                provenance = EvaluationProvenance.HUMAN_DUAL_REVIEWED
                r1 = rev1_dict[pid]
                r2 = rev2_dict[pid]
                annotators = ["human_reviewer_1", "human_reviewer_2"]
                initial_decs["human_reviewer_1"] = r1.get("decision", "")
                initial_decs["human_reviewer_2"] = r2.get("decision", "")
                # If they agreed:
                final_decision = r1.get("decision")
            # Check if single human reviewed
            elif pid in rev1_dict:
                provenance = EvaluationProvenance.HUMAN_REVIEWED
                r1 = rev1_dict[pid]
                annotators = [r1.get("reviewer_id") or "human_reviewer_1"]
                timestamps.append(r1.get("review_timestamp") or "")
                initial_decs[annotators[0]] = r1.get("decision", "")
                final_decision = r1.get("decision")
            # Check if AI adopted
            elif pid in pilot_dict:
                pi = pilot_dict[pid]
                pi_prov = pi.get("provenance", "")
                if pi_prov == "AUTO_ADOPTED_AI":
                    provenance = EvaluationProvenance.AI_ADOPTED
                    annotators = ["ai_auto_adopter"]
                    timestamps.append(pi.get("review_timestamp") or "")
                    initial_decs["ai_auto_adopter"] = pi.get("decision", "")
                    final_decision = pi.get("decision")
                elif pi_prov == "HUMAN_VERIFIED" or pi_prov == "UNKNOWN_LEGACY":
                    provenance = EvaluationProvenance.HUMAN_REVIEWED
                    annotators = ["reviewer_1"]
                    initial_decs["reviewer_1"] = pi.get("decision", "")
                    final_decision = pi.get("decision")
            else:
                provenance = EvaluationProvenance.UNREVIEWED

            # Determine binary label
            binary_label = None
            if final_decision == "MATCH":
                binary_label = 1
            elif final_decision == "NON_MATCH":
                binary_label = 0

            is_gold = provenance in (EvaluationProvenance.HUMAN_DUAL_REVIEWED, EvaluationProvenance.HUMAN_REVIEWED)
            is_challenge = False
            if is_gold:
                # Challenge case criteria: high distance (>=25m), non-exact names, or disputed
                if dist_m >= 25.0 or osm_norm != ov_norm or pid in adj_dict:
                    is_challenge = True

            record = EvaluationRecord(
                pair_id=pid,
                osm_source_id=str(p_base.get("osm_source_id") or ""),
                ov_source_id=str(p_base.get("ov_source_id") or ""),
                osm_name_raw=osm_name,
                ov_name_raw=ov_name,
                osm_name_norm=osm_norm,
                ov_name_norm=ov_norm,
                osm_category=osm_cat,
                ov_category=ov_cat,
                distance_meters=dist_m,
                ground_truth_decision=final_decision,
                binary_label=binary_label,
                provenance=provenance,
                annotator_ids=annotators,
                review_timestamps=timestamps,
                initial_decisions=initial_decs,
                adjudication_rationale=adjudication_rationale,
                is_gold_standard=is_gold,
                is_challenge_case=is_challenge,
                sampling_stratum=str(stratum) if stratum else None,
                partition_split=str(split) if split else None,
                metadata={
                    "blocking_strategies": p_base.get("blocking_strategies"),
                    "graph_component_id": p_base.get("graph_component_id"),
                },
            )
            audited_records[pid] = record

        return audited_records

    def export_evaluation_views(
        self,
        output_dir: Path,
    ) -> Dict[str, Path]:
        """Generate separate Parquet and CSV files for evaluation views."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        records = self.assemble_audited_records()
        record_list = list(records.values())

        # 1. Gold Human Standard View
        gold_records = [r for r in record_list if r.is_gold_standard]
        # 2. Consolidated Operational View (Gold Human + AI Adopted)
        op_records = [r for r in record_list if r.provenance != EvaluationProvenance.UNREVIEWED]
        # 3. Challenge Evaluation View (Difficult subset of gold standard)
        challenge_records = [r for r in record_list if r.is_challenge_case]
        # 4. Unreviewed Expansion Queue (Prioritized queue for future human labeling)
        unreviewed_records = [r for r in record_list if r.provenance == EvaluationProvenance.UNREVIEWED]

        views = {
            "view_gold_human": gold_records,
            "view_consolidated_operational": op_records,
            "view_challenge_difficulty": challenge_records,
            "view_unreviewed_pool": unreviewed_records,
        }

        exported_paths: Dict[str, Path] = {}

        for view_name, recs in views.items():
            dicts = [r.to_dict() for r in recs]
            pq_path = output_dir / f"{view_name}.parquet"
            csv_path = output_dir / f"{view_name}.csv"

            if dicts:
                tbl = pa.Table.from_pylist(dicts)
                pq.write_table(tbl, pq_path, compression="snappy")
                con = duckdb.connect()
                con.execute(f"COPY (SELECT * FROM '{pq_path}') TO '{csv_path}' (HEADER, DELIMITER ',')")
            else:
                pq_path.write_text("")
                csv_path.write_text("")

            exported_paths[f"{view_name}_parquet"] = pq_path
            exported_paths[f"{view_name}_csv"] = csv_path

        logger.info(f"Exported evaluation views to {output_dir}: Gold={len(gold_records)}, Operational={len(op_records)}, Challenge={len(challenge_records)}, Pool={len(unreviewed_records)}")
        return exported_paths
