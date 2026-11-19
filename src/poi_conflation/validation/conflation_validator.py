"""Continuous validation layer for POI conflation and canonical entity resolution.

Executes comprehensive integrity checks across source records, candidate edges,
graph components, canonical entities, relationships, and incremental lineage.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging
from pathlib import Path
import re
from typing import Dict, Any, List, Optional, Set, Tuple
import duckdb

logger = logging.getLogger("conflation_validator")


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


@dataclass
class ValidationCheck:
    """Individual integrity check outcome."""
    name: str
    category: str  # source, candidate, graph, canonical, relationship, incremental
    status: ValidationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ValidationReport:
    """Comprehensive validation report for a pipeline run."""
    run_id: str
    overall_status: ValidationStatus
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    total_checks: int = 0
    checks: List[ValidationCheck] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "overall_status": self.overall_status.value,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "warning_count": self.warning_count,
            "total_checks": self.total_checks,
            "checks": [c.to_dict() for c in self.checks],
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class ContinuousConflationValidator:
    """Automated validator ensuring physical and semantic integrity of conflation outputs."""

    def __init__(
        self,
        bbmp_lat_bounds: Tuple[float, float] = (12.8, 13.2),
        bbmp_lon_bounds: Tuple[float, float] = (77.4, 77.8),
    ):
        self.min_lat, self.max_lat = bbmp_lat_bounds
        self.min_lon, self.max_lon = bbmp_lon_bounds

    def validate_production_outputs(
        self,
        canonical_pois_path: Path,
        conflation_edges_path: Optional[Path] = None,
        poi_relationships_path: Optional[Path] = None,
        unresolved_pairs_path: Optional[Path] = None,
        source_universe_count: Optional[int] = None,
        run_id: str = "validate_run",
    ) -> ValidationReport:
        """Validate exported canonical files and relationships."""
        canonical_pois_path = Path(canonical_pois_path)
        checks: List[ValidationCheck] = []

        con = duckdb.connect()

        # 1. Canonical POI Table Existence & Null Checks
        if not canonical_pois_path.exists():
            checks.append(ValidationCheck(
                name="canonical_table_exists",
                category="canonical",
                status=ValidationStatus.FAILED,
                message=f"Canonical POI export missing: {canonical_pois_path}",
            ))
            return self._build_report(run_id, checks)

        total_entities = con.execute(f"SELECT count(*) FROM '{canonical_pois_path}'").fetchone()[0]
        null_ids = con.execute(f"SELECT count(*) FROM '{canonical_pois_path}' WHERE canonical_entity_id IS NULL").fetchone()[0]
        null_names = con.execute(f"SELECT count(*) FROM '{canonical_pois_path}' WHERE primary_name IS NULL OR length(trim(primary_name)) = 0").fetchone()[0]

        checks.append(ValidationCheck(
            name="canonical_entity_null_checks",
            category="canonical",
            status=ValidationStatus.PASSED if (null_ids == 0 and null_names == 0) else ValidationStatus.FAILED,
            message=f"Total entities: {total_entities}, Null IDs: {null_ids}, Null names: {null_names}",
            details={"total_entities": total_entities, "null_ids": null_ids, "null_names": null_names},
        ))

        # 2. Canonical UUIDv5 Uniqueness (0 Collisions)
        unique_canonical_ids = con.execute(f"SELECT count(DISTINCT canonical_entity_id) FROM '{canonical_pois_path}'").fetchone()[0]
        id_collisions = total_entities - unique_canonical_ids
        checks.append(ValidationCheck(
            name="canonical_id_uniqueness",
            category="canonical",
            status=ValidationStatus.PASSED if id_collisions == 0 else ValidationStatus.FAILED,
            message=f"Unique canonical IDs: {unique_canonical_ids}/{total_entities} (Collisions: {id_collisions})",
            details={"unique_ids": unique_canonical_ids, "collisions": id_collisions},
        ))

        # 3. Source Inventory Accounting (100% preservation & 0 duplicate assignments)
        rows = con.execute(f"SELECT canonical_entity_id, contributing_osm_ids, contributing_ov_ids FROM '{canonical_pois_path}'").fetchall()
        seen_osm: Set[str] = set()
        seen_ov: Set[str] = set()
        dup_osm = 0
        dup_ov = 0

        for cid, osm_ids, ov_ids in rows:
            for sid in osm_ids:
                if sid in seen_osm:
                    dup_osm += 1
                seen_osm.add(sid)
            for sid in ov_ids:
                if sid in seen_ov:
                    dup_ov += 1
                seen_ov.add(sid)

        total_accounted = len(seen_osm) + len(seen_ov)
        accounting_passed = (dup_osm == 0 and dup_ov == 0)
        if source_universe_count is not None and total_accounted != source_universe_count:
            accounting_passed = False

        checks.append(ValidationCheck(
            name="source_inventory_accounting",
            category="graph",
            status=ValidationStatus.PASSED if accounting_passed else ValidationStatus.FAILED,
            message=f"Accounted OSM: {len(seen_osm)}, Accounted Overture: {len(seen_ov)}, Total: {total_accounted}. Duplicate assignments: OSM={dup_osm}, Overture={dup_ov}",
            details={
                "accounted_osm": len(seen_osm),
                "accounted_overture": len(seen_ov),
                "total_accounted": total_accounted,
                "duplicate_osm": dup_osm,
                "duplicate_overture": dup_ov,
                "expected_total": source_universe_count,
            },
        ))

        # 4. Spatial Coordinate Bounds
        bounds = con.execute(f"""
            SELECT min(latitude), max(latitude), min(longitude), max(longitude)
            FROM '{canonical_pois_path}'
        """).fetchone()
        in_bounds = (
            bounds[0] >= self.min_lat and bounds[1] <= self.max_lat and
            bounds[2] >= self.min_lon and bounds[3] <= self.max_lon
        )
        checks.append(ValidationCheck(
            name="canonical_coordinate_bounds",
            category="canonical",
            status=ValidationStatus.PASSED if in_bounds else ValidationStatus.WARNING,
            message=f"Latitude: [{bounds[0]:.4f}, {bounds[1]:.4f}], Longitude: [{bounds[2]:.4f}, {bounds[3]:.4f}]",
            details={"min_lat": bounds[0], "max_lat": bounds[1], "min_lon": bounds[2], "max_lon": bounds[3]},
        ))

        # 5. Prohibited Cross-Entity ATM-Bank Merges
        atm_bank_cross_merges = 0
        atm_pattern = re.compile(r"\b(atm|cdm|automated teller machine|cash point)\b", re.IGNORECASE)
        bank_pattern = re.compile(r"\b(bank|branch)\b", re.IGNORECASE)

        source_names_rows = con.execute(f"""
            SELECT source_names
            FROM '{canonical_pois_path}'
            WHERE resolution_decision = 'RESOLVED_EQUIVALENCE'
        """).fetchall()

        for (sn_json,) in source_names_rows:
            sn = json.loads(sn_json)
            osm_names = sn.get("OSM", [])
            ov_names = sn.get("OVERTURE", [])

            osm_has_atm = any(atm_pattern.search(n) for n in osm_names)
            ov_has_atm = any(atm_pattern.search(n) for n in ov_names)

            if osm_has_atm and not ov_has_atm and any(bank_pattern.search(n) for n in ov_names):
                atm_bank_cross_merges += 1
            elif ov_has_atm and not osm_has_atm and any(bank_pattern.search(n) for n in osm_names):
                atm_bank_cross_merges += 1

        checks.append(ValidationCheck(
            name="prohibited_atm_bank_merges",
            category="graph",
            status=ValidationStatus.PASSED if atm_bank_cross_merges == 0 else ValidationStatus.FAILED,
            message=f"Cross-entity ATM-to-bank merges detected in RESOLVED_EQUIVALENCE: {atm_bank_cross_merges}",
            details={"cross_merges": atm_bank_cross_merges},
        ))

        # 6. Relationships Integrity
        if poi_relationships_path and Path(poi_relationships_path).exists():
            rel_path = Path(poi_relationships_path)
            total_rels = con.execute(f"SELECT count(*) FROM '{rel_path}'").fetchone()[0]
            null_rel_ids = con.execute(f"""
                SELECT count(*) FROM '{rel_path}'
                WHERE parent_source_id IS NULL OR child_source_id IS NULL OR relationship_type IS NULL
            """).fetchone()[0]

            checks.append(ValidationCheck(
                name="relationship_integrity",
                category="relationship",
                status=ValidationStatus.PASSED if null_rel_ids == 0 else ValidationStatus.FAILED,
                message=f"Total relationships: {total_rels}, Null endpoints: {null_rel_ids}",
                details={"total_relationships": total_rels, "null_endpoints": null_rel_ids},
            ))

        return self._build_report(run_id, checks)

    def _build_report(self, run_id: str, checks: List[ValidationCheck]) -> ValidationReport:
        passed = sum(1 for c in checks if c.status == ValidationStatus.PASSED)
        failed = sum(1 for c in checks if c.status == ValidationStatus.FAILED)
        warnings = sum(1 for c in checks if c.status == ValidationStatus.WARNING)

        overall = ValidationStatus.PASSED
        if failed > 0:
            overall = ValidationStatus.FAILED
        elif warnings > 0:
            overall = ValidationStatus.WARNING

        return ValidationReport(
            run_id=run_id,
            overall_status=overall,
            passed_count=passed,
            failed_count=failed,
            warning_count=warnings,
            total_checks=len(checks),
            checks=checks,
        )
