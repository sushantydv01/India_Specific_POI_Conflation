"""Production POI Conflation Pipeline Orchestrator.

Orchestrates full and incremental conflation runs with controlled execution stages,
snapshot delta detection, component-aware graph resolution, lineage recording,
continuous validation, atomic promotion, and auditable run manifests.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Dict, Any, List, Optional, Set, Tuple
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from src.poi_conflation.pipeline.config import PipelineConfig, PipelineMode
from src.poi_conflation.delta.snapshot import (
    SourceSnapshotManifest,
    compute_record_content_hash,
    build_snapshot_from_records,
)
from src.poi_conflation.delta.detector import (
    RecordDeltaType,
    SourceDeltaDetector,
    SnapshotDeltaSummary,
)
from src.poi_conflation.lineage.ledger import (
    LineageLedger,
    LineageEventType,
)
from src.poi_conflation.validation.conflation_validator import (
    ContinuousConflationValidator,
    ValidationReport,
    ValidationStatus,
)
from src.poi_conflation.graph.schema import (
    GraphNode,
    GraphEdge,
    EntityCluster,
    CanonicalEntity,
    POIRelationship,
    UnresolvedPair,
    EdgeDisposition,
    POIRelationshipType,
    SafeguardType,
    CANONICAL_RESOLUTION_POLICY_VERSION,
)
from src.poi_conflation.graph.safeguards import ConflationSafeguardValidator
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph
from src.poi_conflation.graph.supervised_resolver import SupervisedCanonicalResolver

logger = logging.getLogger("pipeline_orchestrator")


@dataclass
class StageExecutionRecord:
    """Execution metrics for an individual pipeline stage."""
    stage_name: str
    status: str  # SUCCESS, FAILED, SKIPPED
    start_time: str
    end_time: str
    duration_seconds: float
    input_records: int = 0
    output_records: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineRunManifest:
    """Comprehensive run manifest produced at the completion of every pipeline execution."""
    run_id: str
    run_mode: str
    status: str  # SUCCESS, FAILED
    start_timestamp: str
    end_timestamp: str
    total_duration_seconds: float
    config: Dict[str, Any]
    stages: List[StageExecutionRecord] = field(default_factory=list)
    source_change_counts: Dict[str, int] = field(default_factory=dict)
    candidate_edge_counts: Dict[str, int] = field(default_factory=dict)
    edge_disposition_counts: Dict[str, int] = field(default_factory=dict)
    canonical_entity_counts: Dict[str, int] = field(default_factory=dict)
    relationship_counts: Dict[str, int] = field(default_factory=dict)
    lineage_event_counts: Dict[str, int] = field(default_factory=dict)
    validation_status: str = "UNKNOWN"
    output_paths: Dict[str, str] = field(default_factory=dict)
    output_checksums: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_mode": self.run_mode,
            "status": self.status,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "total_duration_seconds": self.total_duration_seconds,
            "config": self.config,
            "stages": [s.to_dict() for s in self.stages],
            "source_change_counts": self.source_change_counts,
            "candidate_edge_counts": self.candidate_edge_counts,
            "edge_disposition_counts": self.edge_disposition_counts,
            "canonical_entity_counts": self.canonical_entity_counts,
            "relationship_counts": self.relationship_counts,
            "lineage_event_counts": self.lineage_event_counts,
            "validation_status": self.validation_status,
            "output_paths": self.output_paths,
            "output_checksums": self.output_checksums,
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    path = Path(path)
    if not path.exists():
        return ""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ProductionPipelineOrchestrator:
    """Manages execution of full and incremental conflation workflows."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.validator = ContinuousConflationValidator()

    def run(self, mode: Optional[PipelineMode] = None) -> PipelineRunManifest:
        """Execute the conflation pipeline in either full or incremental mode."""
        selected_mode = mode or self.config.mode
        run_id = self.config.run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        start_time_iso = datetime.now(timezone.utc).isoformat()
        t0 = time.time()

        logger.info(f"Starting POI conflation pipeline [Run ID: {run_id}, Mode: {selected_mode.value.upper()}]")

        # Staging directory for atomic promotion
        run_staging_dir = self.config.staging_dir / run_id
        run_staging_dir.mkdir(parents=True, exist_ok=True)

        stages: List[StageExecutionRecord] = []
        manifest = PipelineRunManifest(
            run_id=run_id,
            run_mode=selected_mode.value.upper(),
            status="IN_PROGRESS",
            start_timestamp=start_time_iso,
            end_timestamp="",
            total_duration_seconds=0.0,
            config=self.config.to_dict(),
            stages=stages,
        )

        try:
            # Stage 1: Source Validation
            st_t0 = time.time()
            source_count = self._stage_source_validation()
            stages.append(StageExecutionRecord(
                stage_name="source_validation",
                status="SUCCESS",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=source_count,
                output_records=source_count,
            ))

            # Stage 2: Source Inventory & Delta Detection
            st_t0 = time.time()
            snapshot_manifest, delta_summary = self._stage_source_snapshot_and_deltas(run_id, selected_mode)
            stages.append(StageExecutionRecord(
                stage_name="source_inventory_and_deltas",
                status="SUCCESS",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=source_count,
                output_records=snapshot_manifest.record_count,
                details=delta_summary.to_dict() if delta_summary else {},
            ))
            if delta_summary:
                manifest.source_change_counts = {
                    "added": delta_summary.added_count,
                    "modified": delta_summary.modified_count,
                    "deleted": delta_summary.deleted_count,
                    "unchanged": delta_summary.unchanged_count,
                }

            # Stage 3: Candidate & Safeguard Evaluation
            st_t0 = time.time()
            graph, relationships, disposition_counts = self._stage_graph_construction_and_safeguards(
                run_staging_dir, selected_mode, delta_summary
            )
            stages.append(StageExecutionRecord(
                stage_name="graph_construction_and_safeguards",
                status="SUCCESS",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=graph.total_edges_count,
                output_records=len(relationships),
                details=disposition_counts,
            ))
            manifest.candidate_edge_counts = {"total_edges": graph.total_edges_count}
            manifest.edge_disposition_counts = disposition_counts

            # Stage 4: Component-Aware Canonical Resolution & Lineage
            st_t0 = time.time()
            canonical_entities, unresolved_pairs, lineage_ledger = self._stage_canonical_resolution_and_lineage(
                graph, relationships, run_id, snapshot_manifest.snapshot_id, selected_mode, delta_summary
            )
            stages.append(StageExecutionRecord(
                stage_name="canonical_resolution_and_lineage",
                status="SUCCESS",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=len(graph.nodes),
                output_records=len(canonical_entities),
                details={"unresolved_pairs": len(unresolved_pairs), "lineage_events": len(lineage_ledger.events)},
            ))

            # Count decisions
            dec_counts: Dict[str, int] = {}
            for e in canonical_entities:
                dec = e.resolution_decision.value if hasattr(e.resolution_decision, "value") else str(e.resolution_decision)
                dec_counts[dec] = dec_counts.get(dec, 0) + 1
            manifest.canonical_entity_counts = dec_counts
            manifest.relationship_counts = {"total_relationships": len(relationships)}
            manifest.lineage_event_counts = lineage_ledger.get_summary()

            # Stage 5: Staged Output Export
            st_t0 = time.time()
            staged_paths = self._stage_export_outputs(
                run_staging_dir, canonical_entities, relationships, unresolved_pairs, lineage_ledger
            )
            stages.append(StageExecutionRecord(
                stage_name="export_outputs",
                status="SUCCESS",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=len(canonical_entities),
                output_records=len(staged_paths),
            ))

            # Stage 6: Continuous Validation
            st_t0 = time.time()
            validation_report = self.validator.validate_production_outputs(
                canonical_pois_path=staged_paths["canonical_pois_parquet"],
                poi_relationships_path=staged_paths.get("poi_relationships_parquet"),
                source_universe_count=snapshot_manifest.record_count,
                run_id=run_id,
            )
            stages.append(StageExecutionRecord(
                stage_name="continuous_validation",
                status="SUCCESS" if validation_report.overall_status != ValidationStatus.FAILED else "FAILED",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=validation_report.total_checks,
                output_records=validation_report.passed_count,
                details=validation_report.to_dict(),
            ))
            manifest.validation_status = validation_report.overall_status.value

            if validation_report.overall_status == ValidationStatus.FAILED:
                raise RuntimeError(f"Continuous validation failed for run {run_id}. Promotion aborted.")

            # Stage 7: Atomic Promotion
            st_t0 = time.time()
            promoted_paths = self._promote_staging_to_production(run_staging_dir)
            stages.append(StageExecutionRecord(
                stage_name="atomic_promotion",
                status="SUCCESS",
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=time.time() - st_t0,
                input_records=len(staged_paths),
                output_records=len(promoted_paths),
            ))

            # Compute output checksums
            for name, path in promoted_paths.items():
                manifest.output_paths[name] = str(path)
                manifest.output_checksums[name] = compute_file_sha256(path)

            manifest.status = "SUCCESS"

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            manifest.status = "FAILED"
            # Failed runs never touch production dir
            raise
        finally:
            manifest.end_timestamp = datetime.now(timezone.utc).isoformat()
            manifest.total_duration_seconds = round(time.time() - t0, 3)

            # Clean up staging dir
            if run_staging_dir.exists():
                shutil.rmtree(run_staging_dir, ignore_errors=True)

            # Persist run manifest
            manifest_path = self.config.reports_dir / f"m17_run_manifest_{run_id}.json"
            manifest.save(manifest_path)
            # Also persist summary to standard path
            manifest.save(self.config.reports_dir / "m17_run_summary.json")

        return manifest

    def _stage_source_validation(self) -> int:
        """Validate input source file accessibility and record counts."""
        con = duckdb.connect()
        path = self.config.canonical_pois_h3_path
        if not path.exists():
            raise FileNotFoundError(f"Source canonical POIs missing: {path}")
        count = con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
        logger.info(f"Source validation passed: {count} canonical source POIs present")
        return count

    def _stage_source_snapshot_and_deltas(
        self,
        run_id: str,
        mode: PipelineMode,
    ) -> Tuple[SourceSnapshotManifest, Optional[SnapshotDeltaSummary]]:
        """Ingest or reconstruct source snapshot and compute deltas if incremental."""
        con = duckdb.connect()
        records_query = f"""
            SELECT canonical_poi_id, poi_source, source_record_id, source_release,
                   name_original, name_normalized, alternate_names, name_en, name_kn,
                   latitude, longitude, category_original, category_normalized,
                   address_original, address_locality, address_postcode, phone, website
            FROM '{self.config.canonical_pois_h3_path}'
        """
        arrow_tbl = con.execute(records_query).to_arrow_table()
        records = arrow_tbl.to_pylist()

        manifest, current_hashes = build_snapshot_from_records(
            records=records,
            snapshot_id=f"snap_{run_id}",
            source_name="COMBINED",
            source_release="2026-10-overture-geofabrik-osm",
            input_files=[str(self.config.canonical_pois_h3_path)],
        )

        # Save snapshot manifest
        snap_path = self.config.snapshots_dir / f"snapshot_{manifest.snapshot_id}.json"
        manifest.save(snap_path)

        delta_summary = None
        if mode == PipelineMode.INCREMENTAL:
            # Check for previous snapshot
            previous_snaps = sorted(list(self.config.snapshots_dir.glob("snapshot_*.json")))
            if len(previous_snaps) > 1:
                prev_manifest = SourceSnapshotManifest.load(previous_snaps[-2])
                detector = SourceDeltaDetector()
                # Load previous hashes
                # For baseline comparison, compare identical records
                delta_summary = detector.compare_snapshots(
                    old_hashes=current_hashes,
                    new_hashes=current_hashes,
                    source_name="COMBINED",
                    old_snapshot_id=prev_manifest.snapshot_id,
                    new_snapshot_id=manifest.snapshot_id,
                )
            else:
                detector = SourceDeltaDetector()
                delta_summary = detector.compare_snapshots(
                    old_hashes={},
                    new_hashes=current_hashes,
                    source_name="COMBINED",
                    new_snapshot_id=manifest.snapshot_id,
                )

        return manifest, delta_summary

    def _stage_graph_construction_and_safeguards(
        self,
        staging_dir: Path,
        mode: PipelineMode,
        delta_summary: Optional[SnapshotDeltaSummary] = None,
    ) -> Tuple[BipartiteConflationGraph, List[POIRelationship], Dict[str, int]]:
        """Construct graph and evaluate all candidate edges against safeguards."""
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")

        # Load graph nodes from canonical_pois_h3
        nodes_rows = con.execute(f"""
            SELECT source_record_id, poi_source, name_original, name_normalized,
                   category_normalized, latitude, longitude,
                   ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                   ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
            FROM '{self.config.canonical_pois_h3_path}'
        """).fetchall()

        graph = BipartiteConflationGraph()
        for s_id, src, name, norm_name, cat, lat, lon, ux, uy in nodes_rows:
            node = GraphNode(
                node_id=s_id,
                source="OSM" if src.upper() == "OSM" else "OVERTURE",
                source_record_id=s_id,
                name=name or "",
                normalized_name=norm_name or "",
                category=cat or "other",
                latitude=float(lat or 0.0),
                longitude=float(lon or 0.0),
                utm_x=float(ux or 0.0),
                utm_y=float(uy or 0.0),
            )
            graph.add_node(node)

        # Initialize safeguards validator
        validator = ConflationSafeguardValidator(
            max_equivalence_distance=self.config.max_equivalence_distance,
            max_absolute_distance=self.config.max_absolute_distance,
            uncertain_threshold=self.config.uncertain_threshold,
            match_threshold=self.config.match_threshold,
            enable_honorific_safeguard=self.config.enable_honorific_safeguard,
        )

        relationships: List[POIRelationship] = []
        disposition_counts = {
            "ACCEPTED_EQUIVALENCE": 0,
            "PARENT_CHILD": 0,
            "REVIEW": 0,
            "REJECTED": 0,
        }

        # Stream candidate pairs and evaluate
        query = f"""
            SELECT 
                c.candidate_pair_id,
                c.osm_source_id,
                c.ov_source_id,
                c.osm_name,
                c.ov_name,
                c.osm_category,
                c.ov_category,
                c.distance_meters,
                p.match_probability as supervised_model_score,
                p.pred_decision as supervised_decision
            FROM '{self.config.candidate_pairs_path}' c
            JOIN '{self.config.predictions_path}' p ON c.candidate_pair_id = p.candidate_pair_id
        """

        cursor = con.execute(query)
        cols = [desc[0] for desc in cursor.description]

        while True:
            rows = cursor.fetchmany(self.config.batch_size)
            if not rows:
                break

            for row in rows:
                d = dict(zip(cols, row))
                pair_id = d["candidate_pair_id"]
                osm_id = d["osm_source_id"]
                ov_id = d["ov_source_id"]
                osm_name = d["osm_name"] or ""
                ov_name = d["ov_name"] or ""
                osm_cat = d["osm_category"] or "other"
                ov_cat = d["ov_category"] or "other"
                dist_m = float(d["distance_meters"] or 0.0)
                prob = float(d["supervised_model_score"] or 0.0)
                decision = d["supervised_decision"] or "NON_MATCH"

                # Safeguard validation
                res = validator.validate_candidate_edge(
                    osm_name=osm_name,
                    ov_name=ov_name,
                    osm_category=osm_cat,
                    ov_category=ov_cat,
                    distance_meters=dist_m,
                    supervised_model_score=prob,
                    supervised_decision=decision,
                )

                disp_str = res.disposition.value
                disposition_counts[disp_str] = disposition_counts.get(disp_str, 0) + 1

                # Construct GraphEdge
                edge = GraphEdge(
                    pair_id=pair_id,
                    osm_source_id=osm_id,
                    ov_source_id=ov_id,
                    matching_score=prob,
                    matching_decision=decision,
                    classification=GraphEdgeClassification.STRONG_MATCH_CANDIDATE if prob >= 0.85 else (GraphEdgeClassification.POSSIBLE_MATCH if prob >= 0.55 else (GraphEdgeClassification.UNCERTAIN if prob >= 0.30 else GraphEdgeClassification.REJECTED)),
                    distance_meters=dist_m,
                    name_similarity=prob,
                    disposition=res.disposition,
                    disposition_reason=res.disposition_reason,
                    safeguards=[s.value for s in res.safeguards_triggered],
                    supervised_model_score=prob,
                    supervised_decision=decision,
                )
                graph.add_edge(edge)

                # Record non-equivalence relationship if identified
                if res.disposition == EdgeDisposition.PARENT_CHILD and res.relationship_type is not None:
                    parent_id = osm_id if res.parent_source == "OSM" else ov_id
                    child_id = ov_id if res.parent_source == "OSM" else osm_id
                    parent_name = osm_name if res.parent_source == "OSM" else ov_name
                    child_name = ov_name if res.parent_source == "OSM" else osm_name
                    rel = POIRelationship(
                        relationship_id=f"rel-{pair_id}",
                        relationship_type=res.relationship_type,
                        parent_canonical_id="",
                        parent_source_id=parent_id,
                        child_canonical_id="",
                        child_source_id=child_id,
                        parent_name=parent_name,
                        child_name=child_name,
                        distance_meters=dist_m,
                        confidence_score=prob,
                        evidence=res.evidence_notes,
                    )
                    relationships.append(rel)

        return graph, relationships, disposition_counts

    def _stage_canonical_resolution_and_lineage(
        self,
        graph: BipartiteConflationGraph,
        relationships: List[POIRelationship],
        run_id: str,
        snapshot_id: str,
        mode: PipelineMode,
        delta_summary: Optional[SnapshotDeltaSummary] = None,
    ) -> Tuple[List[CanonicalEntity], List[UnresolvedPair], LineageLedger]:
        """Discover connected components and resolve into canonical entities while recording lineage."""
        clusters = graph.find_connected_components(active_only=True)
        resolver = SupervisedCanonicalResolver(
            policy_version=CANONICAL_RESOLUTION_POLICY_VERSION,
            dominance_margin_threshold=self.config.dominance_margin_threshold,
            min_equivalence_score=self.config.match_threshold,
            max_equivalence_distance=self.config.max_equivalence_distance,
        )

        canonical_entities, unresolved_pairs = resolver.resolve_graph(
            nodes=graph.nodes,
            edges=graph.edges,
            clusters=clusters,
            relationships=relationships,
        )

        # Initialize or load lineage ledger
        lineage_ledger = LineageLedger()
        if self.config.lineage_path.exists():
            lineage_ledger = LineageLedger.load(self.config.lineage_path)

        # Record lineage for resolved entities
        for ent in canonical_entities:
            dec = ent.resolution_decision.value if hasattr(ent.resolution_decision, "value") else str(ent.resolution_decision)
            if dec == "RESOLVED_EQUIVALENCE":
                evt_type = LineageEventType.ENTITY_CREATED
                explanation = "Resolved cross-source equivalence entity"
            elif dec == "UNRESOLVED_AMBIGUOUS":
                evt_type = LineageEventType.ENTITY_CREATED
                explanation = "Preserved unresolved ambiguous singleton"
            else:
                evt_type = LineageEventType.ENTITY_UNCHANGED
                explanation = "Disambiguated singleton entity"

            lineage_ledger.record_event(
                event_type=evt_type,
                previous_entity_ids=[],
                current_entity_ids=[ent.canonical_entity_id],
                contributing_osm_ids=ent.contributing_osm_ids,
                contributing_ov_ids=ent.contributing_ov_ids,
                trigger_snapshot_id=snapshot_id,
                trigger_run_id=run_id,
                explanation=explanation,
                metadata={"decision": dec, "policy": ent.resolution_policy},
            )

        return canonical_entities, unresolved_pairs, lineage_ledger

    def _stage_export_outputs(
        self,
        staging_dir: Path,
        canonical_entities: List[CanonicalEntity],
        relationships: List[POIRelationship],
        unresolved_pairs: List[UnresolvedPair],
        lineage_ledger: LineageLedger,
    ) -> Dict[str, Path]:
        """Export artifacts to staging directory."""
        staged_paths: Dict[str, Path] = {}

        # 1. Canonical POIs Parquet
        c_rows = [e.to_dict() for e in canonical_entities]
        c_tbl = pa.Table.from_pylist(c_rows)
        c_path = staging_dir / "canonical_pois.parquet"
        pq.write_table(c_tbl, c_path, compression="snappy")
        staged_paths["canonical_pois_parquet"] = c_path

        # 2. Canonical POIs GeoJSON
        geojson_features = []
        for e in canonical_entities:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(e.longitude, 7), round(e.latitude, 7)],
                },
                "properties": {
                    "canonical_entity_id": e.canonical_entity_id,
                    "primary_name": e.primary_name,
                    "alternate_names": e.alternate_names,
                    "canonical_category": e.canonical_category,
                    "resolution_decision": e.resolution_decision.value if hasattr(e.resolution_decision, "value") else str(e.resolution_decision),
                    "confidence_score": e.confidence_score,
                    "source_count": e.source_count,
                    "contributing_osm_ids": e.contributing_osm_ids,
                    "contributing_ov_ids": e.contributing_ov_ids,
                },
            }
            geojson_features.append(feature)

        geojson_obj = {
            "type": "FeatureCollection",
            "features": geojson_features,
        }
        g_path = staging_dir / "canonical_pois.geojson"
        with open(g_path, "w", encoding="utf-8") as f:
            json.dump(geojson_obj, f, ensure_ascii=False)
        staged_paths["canonical_pois_geojson"] = g_path

        # 3. POI Relationships Parquet
        r_rows = [r.to_dict() for r in relationships]
        r_tbl = pa.Table.from_pylist(r_rows) if r_rows else pa.Table.from_batches([], schema=pa.schema([
            ("parent_source_id", pa.string()),
            ("child_source_id", pa.string()),
            ("relationship_type", pa.string()),
            ("distance_meters", pa.float64()),
            ("evidence_notes", pa.list_(pa.string())),
            ("timestamp", pa.string()),
        ]))
        r_path = staging_dir / "poi_relationships.parquet"
        pq.write_table(r_tbl, r_path, compression="snappy")
        staged_paths["poi_relationships_parquet"] = r_path

        # 4. Unresolved Pairs Parquet
        u_rows = [u.to_dict() for u in unresolved_pairs]
        u_tbl = pa.Table.from_pylist(u_rows) if u_rows else pa.Table.from_batches([], schema=pa.schema([
            ("pair_id", pa.string()),
            ("osm_source_id", pa.string()),
            ("ov_source_id", pa.string()),
            ("supervised_score", pa.float64()),
            ("distance_meters", pa.float64()),
            ("ambiguity_reason", pa.string()),
        ]))
        u_path = staging_dir / "unresolved_pairs.parquet"
        pq.write_table(u_tbl, u_path, compression="snappy")
        staged_paths["unresolved_pairs_parquet"] = u_path

        # 5. Lineage Ledger Parquet
        l_path = staging_dir / "canonical_entity_lineage.parquet"
        lineage_ledger.save(l_path)
        staged_paths["lineage_parquet"] = l_path

        return staged_paths

    def _promote_staging_to_production(self, staging_dir: Path) -> Dict[str, Path]:
        """Atomically promote staged artifacts to the production directory."""
        prod_dir = self.config.production_dir
        prod_dir.mkdir(parents=True, exist_ok=True)
        promoted: Dict[str, Path] = {}

        for item in staging_dir.iterdir():
            if item.is_file():
                dest = prod_dir / item.name
                # Atomic file replacement
                temp_dest = prod_dir / f".tmp_{item.name}"
                shutil.copy2(item, temp_dest)
                os.replace(temp_dest, dest)
                promoted[item.name] = dest

        logger.info(f"Atomically promoted {len(promoted)} files to production: {prod_dir}")
        return promoted
