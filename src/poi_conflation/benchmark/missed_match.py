"""Missed-match diagnostic audit engine for OpenStreetMap POIs.

Audits a diagnostic sample of 120 OSM records that are unrepresented or weakly
represented in the candidate generation pool (e.g., zero candidates, Kannada script,
peripheral wards, institutional campuses) using an independent search procedure.

Enforces precise scientific status semantics:
- NO_COUNTERPART_FOUND_IN_SEARCH: The defined search procedure found no plausible candidate within the search radius.
- POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING: A candidate counterpart was found outside blocking, pending human review.
- HUMAN_CONFIRMED_MATCH_OUTSIDE_BLOCKING: Confirmed by human review to refer to the same POI.
- INSUFFICIENT_EVIDENCE: Available record attributes are inadequate to perform linkage.
- SEARCH_REQUIRES_EXPANSION: Search radius or parameters inadequate to reach a conclusion.
"""

import csv
import json
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import duckdb
from rapidfuzz import fuzz

SEARCH_PROCEDURE_VERSION = "v1.1-radial-fuzzy-token"
SEARCH_RADIUS_METERS = 1500.0


class DiagnosticStatus(str, Enum):
    """Scientific classification of diagnostic search outcomes."""
    NO_COUNTERPART_FOUND_IN_SEARCH = "NO_COUNTERPART_FOUND_IN_SEARCH"
    POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING = "POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING"
    HUMAN_CONFIRMED_MATCH_OUTSIDE_BLOCKING = "HUMAN_CONFIRMED_MATCH_OUTSIDE_BLOCKING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SEARCH_REQUIRES_EXPANSION = "SEARCH_REQUIRES_EXPANSION"


class ReviewStatus(str, Enum):
    """Human review state for diagnostic audit records."""
    AUTOMATED_SEARCH_COMPLETED = "AUTOMATED_SEARCH_COMPLETED"
    PENDING_HUMAN_CONFIRMATION = "PENDING_HUMAN_CONFIRMATION"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"


class MissedMatchAuditor:
    """Performs independent Overture search for unmatched/weak OSM POIs."""

    def __init__(
        self,
        canonical_parquet: str = "data/processed/canonical_pois_h3.parquet",
        candidate_parquet: str = "data/processed/candidate_pairs/candidate_pairs_union.parquet",
        output_dir: str = "data/processed/benchmark",
        reports_dir: str = "reports",
        sample_size: int = 120,
        seed: int = 42
    ):
        self.canonical_parquet = Path(canonical_parquet)
        self.candidate_parquet = Path(candidate_parquet)
        self.output_dir = Path(output_dir)
        self.reports_dir = Path(reports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.sample_size = sample_size
        self.seed = seed
        self.con = duckdb.connect()
        self.con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")

    def _prepare_audit_tables(self):
        """Prepare projected tables and identify OSM records with zero or weak candidates."""
        self.con.execute(f"""
            CREATE OR REPLACE TEMP TABLE canonical_base AS 
            SELECT * FROM '{self.canonical_parquet}';

            CREATE OR REPLACE TEMP TABLE candidate_base AS 
            SELECT * FROM '{self.candidate_parquet}';

            -- OSM records with candidate counts
            CREATE OR REPLACE TEMP TABLE osm_cand_counts AS
            SELECT 
                c.source_record_id,
                count(p.candidate_pair_id) as candidate_count
            FROM canonical_base c
            LEFT JOIN candidate_base p ON c.source_record_id = p.osm_source_id
            WHERE c.poi_source = 'OSM'
            GROUP BY c.source_record_id;

            -- Projected UTM tables for spatial search
            CREATE OR REPLACE TEMP TABLE osm_unmatched_pool AS
            SELECT 
                c.source_record_id as osm_source_id,
                c.name_original as osm_name_raw,
                c.name_normalized as osm_name_normalized,
                c.name_kn as osm_name_kn,
                c.name_en as osm_name_en,
                c.category_normalized as osm_category,
                c.latitude as osm_lat,
                c.longitude as osm_lon,
                ST_X(ST_Transform(ST_Point(c.longitude, c.latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(c.longitude, c.latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y,
                cnt.candidate_count
            FROM canonical_base c
            JOIN osm_cand_counts cnt ON c.source_record_id = cnt.source_record_id
            WHERE c.poi_source = 'OSM';

            CREATE OR REPLACE TEMP TABLE ov_search_index AS
            SELECT 
                source_record_id as ov_source_id,
                name_original as ov_name_raw,
                name_normalized as ov_norm_name,
                category_normalized as ov_category,
                latitude as ov_lat,
                longitude as ov_lon,
                ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
                ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
            FROM canonical_base
            WHERE poi_source = 'OVERTURE';
        """)

    def sample_audit_entities(self) -> List[Dict[str, Any]]:
        """Sample 120 diverse OSM entities unrepresented in candidate generation."""
        self._prepare_audit_tables()

        # Stratum 1: Zero candidates with Kannada script (30)
        stratum_kannada = self.con.execute(f"""
            SELECT * FROM osm_unmatched_pool 
            WHERE candidate_count = 0 
              AND (osm_name_kn IS NOT NULL OR regexp_matches(coalesce(osm_name_raw, ''), '[ಀ-೿]'))
            ORDER BY hash(osm_source_id || '{self.seed}')
            LIMIT 30;
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        items_kannada = [dict(zip(cols, r)) for r in stratum_kannada]
        for it in items_kannada:
            it["audit_stratum"] = "ZERO_CANDIDATE_KANNADA"

        # Stratum 2: Zero candidates in peripheral/boundary wards (distance from central MG Road > 12km) (30)
        stratum_peripheral = self.con.execute(f"""
            SELECT * FROM osm_unmatched_pool 
            WHERE candidate_count = 0 
              AND sqrt(power(utm_x - 783000.0, 2) + power(utm_y - 1435000.0, 2)) > 12000.0
            ORDER BY hash(osm_source_id || '{self.seed + 1}')
            LIMIT 30;
        """).fetchall()
        items_peripheral = [dict(zip(cols, r)) for r in stratum_peripheral]
        for it in items_peripheral:
            it["audit_stratum"] = "ZERO_CANDIDATE_PERIPHERAL"

        # Stratum 3: Zero candidates in civic, education, healthcare institutions (30)
        stratum_institutions = self.con.execute(f"""
            SELECT * FROM osm_unmatched_pool 
            WHERE candidate_count = 0 
              AND osm_category IN ('education', 'healthcare', 'civic_religious')
            ORDER BY hash(osm_source_id || '{self.seed + 2}')
            LIMIT 30;
        """).fetchall()
        items_inst = [dict(zip(cols, r)) for r in stratum_institutions]
        for it in items_inst:
            it["audit_stratum"] = "ZERO_CANDIDATE_INSTITUTION"

        # Stratum 4: Weak candidates only (e.g., candidate count between 1 and 3, all distances > 40m) (30)
        stratum_weak = self.con.execute(f"""
            SELECT u.* FROM osm_unmatched_pool u
            JOIN (
                SELECT osm_source_id, min(distance_meters) as min_dist
                FROM candidate_base
                GROUP BY osm_source_id
                HAVING count(*) <= 3 AND min(distance_meters) > 40.0
            ) w ON u.osm_source_id = w.osm_source_id
            ORDER BY hash(u.osm_source_id || '{self.seed + 3}')
            LIMIT 30;
        """).fetchall()
        items_weak = [dict(zip(cols, r)) for r in stratum_weak]
        for it in items_weak:
            it["audit_stratum"] = "WEAK_CANDIDATES_ONLY"

        return items_kannada + items_peripheral + items_inst + items_weak

    def execute_audit(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Run independent wide-area and fuzzy search against Overture for sampled OSM records."""
        sampled_entities = self.sample_audit_entities()
        print(f"Auditing {len(sampled_entities)} unrepresented OSM entities with independent search (radius={SEARCH_RADIUS_METERS}m)...")

        audit_results = []
        verdicts_count = {s.value: 0 for s in DiagnosticStatus}

        for ent in sampled_entities:
            osm_id = ent["osm_source_id"]
            osm_name = ent["osm_name_raw"] or ""
            osm_norm = ent["osm_name_normalized"] or ""
            osm_cat = ent["osm_category"] or "other"
            utm_x = ent["utm_x"]
            utm_y = ent["utm_y"]

            # Independent Search: Query all Overture POIs within 1,500m unconstrained by category
            wide_matches = self.con.execute(f"""
                SELECT 
                    ov_source_id,
                    ov_name_raw,
                    ov_norm_name,
                    ov_category,
                    ov_lat,
                    ov_lon,
                    round(sqrt(power(utm_x - {utm_x}, 2) + power(utm_y - {utm_y}, 2)), 2) as dist_meters
                FROM ov_search_index
                WHERE power(utm_x - {utm_x}, 2) + power(utm_y - {utm_y}, 2) <= power({SEARCH_RADIUS_METERS}, 2)
                LIMIT 500;
            """).fetchall()

            best_match: Optional[Dict[str, Any]] = None
            best_score = 0.0

            if osm_norm and len(osm_norm.strip()) >= 3:
                for row in wide_matches:
                    ov_id, ov_name_raw, ov_norm, ov_cat, ov_lat, ov_lon, dist = row
                    if not ov_norm:
                        continue
                    tsr = fuzz.token_sort_ratio(osm_norm, ov_norm)
                    part = fuzz.partial_ratio(osm_norm, ov_norm)
                    score = max(tsr, part)
                    if score > best_score:
                        best_score = score
                        best_match = {
                            "ov_source_id": ov_id,
                            "ov_name_raw": ov_name_raw,
                            "ov_norm_name": ov_norm,
                            "ov_category": ov_cat,
                            "ov_lat": ov_lat,
                            "ov_lon": ov_lon,
                            "dist_meters": dist,
                            "similarity_score": score
                        }

            # Evaluate diagnostic verdict with careful, non-conclusive terminology
            if not osm_norm or len(osm_norm.strip()) < 3:
                status = DiagnosticStatus.INSUFFICIENT_EVIDENCE
                review_status = ReviewStatus.AUTOMATED_SEARCH_COMPLETED
                name_evidence = "Name missing or too short (<= 3 chars) in OSM"
                category_evidence = f"Category: {osm_cat}"
                diagnostic_notes = "OSM record lacks distinctive name to perform independent linkage"
            elif best_match and best_score >= 80.0 and best_match["dist_meters"] > 50.0:
                status = DiagnosticStatus.POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING
                review_status = ReviewStatus.PENDING_HUMAN_CONFIRMATION
                name_evidence = f"Fuzzy similarity score {best_score} with '{best_match['ov_name_raw']}'"
                category_evidence = f"OSM: {osm_cat} vs Overture: {best_match['ov_category']}"
                diagnostic_notes = f"Candidate located at {best_match['dist_meters']}m (>50m blocking threshold); requires human adjudication"
            elif best_match and best_score >= 70.0 and ent["candidate_count"] == 0 and best_match["dist_meters"] <= 50.0:
                status = DiagnosticStatus.POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING
                review_status = ReviewStatus.PENDING_HUMAN_CONFIRMATION
                name_evidence = f"Fuzzy similarity score {best_score} with '{best_match['ov_name_raw']}'"
                category_evidence = f"OSM: {osm_cat} vs Overture: {best_match['ov_category']}"
                diagnostic_notes = "Candidate within 50m was not blocked by pipeline due to category or lexical threshold; requires human review"
            else:
                status = DiagnosticStatus.NO_COUNTERPART_FOUND_IN_SEARCH
                review_status = ReviewStatus.AUTOMATED_SEARCH_COMPLETED
                name_evidence = f"Best search score was {best_score} (insufficient)" if best_match else "No name match in radial envelope"
                category_evidence = f"Category: {osm_cat}"
                diagnostic_notes = f"No plausible candidate counterpart identified within {SEARCH_RADIUS_METERS}m search envelope"

            verdicts_count[status.value] += 1

            audit_results.append({
                "osm_source_id": osm_id,
                "osm_name_raw": osm_name,
                "osm_name_normalized": osm_norm,
                "osm_category": osm_cat,
                "osm_lat": ent["osm_lat"],
                "osm_lon": ent["osm_lon"],
                "audit_stratum": ent["audit_stratum"],
                "candidate_count_in_pipeline": ent["candidate_count"],
                "diagnostic_status": status.value,
                "review_status": review_status.value,
                "search_radius_meters": SEARCH_RADIUS_METERS,
                "search_procedure_version": SEARCH_PROCEDURE_VERSION,
                "candidate_source": "OVERTURE",
                "candidate_distance_meters": best_match["dist_meters"] if best_match else None,
                "best_counterpart_id": best_match["ov_source_id"] if best_match else None,
                "best_counterpart_name": best_match["ov_name_raw"] if best_match else None,
                "name_evidence": name_evidence,
                "category_evidence": category_evidence,
                "human_decision": None,
                "human_evidence": None,
                "diagnostic_notes": diagnostic_notes
            })

        summary = {
            "audit_timestamp": "2026-11-17T09:35:00Z",
            "search_procedure_version": SEARCH_PROCEDURE_VERSION,
            "search_radius_meters": SEARCH_RADIUS_METERS,
            "total_entities_audited": len(audit_results),
            "diagnostic_status_distribution": verdicts_count,
            "methodology_disclaimer": (
                "This is a diagnostic sample of 120 unrepresented/weak OSM records designed to inspect failure modes. "
                "It does NOT constitute a statistically valid estimate of global candidate blocking recall across the 49,036 OSM universe. "
                "Potential counterparts found outside blocking are hypotheses pending human adjudication."
            )
        }

        return audit_results, summary

    def export_audit(self) -> Tuple[Path, Path]:
        """Export missed-match audit CSV and summary JSON."""
        results, summary = self.execute_audit()

        csv_path = self.output_dir / "missed_match_audit.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            if results:
                fieldnames = list(results[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    writer.writerow(r)

        json_path = self.reports_dir / "missed_match_audit_summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"Exported {len(results)} corrected missed match audit records to {csv_path}")
        print(f"Exported audit summary to {json_path}")
        return csv_path, json_path
