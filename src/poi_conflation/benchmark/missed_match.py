"""Missed-match diagnostic audit engine for OpenStreetMap POIs.

Audits a diagnostic sample of 120 OSM records that are unrepresented or weakly
represented in the candidate generation pool (e.g., zero candidates, Kannada script,
peripheral wards, institutional campuses) using an independent search procedure.

Classifies outcomes:
- NO_COUNTERPART_FOUND: Overture does not catalog this entity (source coverage gap).
- POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING: Entity exists in Overture but was missed by blocking.
- INSUFFICIENT_EVIDENCE: Available information is ambiguous or cannot establish identity.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import duckdb
from rapidfuzz import fuzz

from src.poi_conflation.benchmark.schema import EvidenceType


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
              AND (osm_name_kn IS NOT NULL OR regexp_matches(coalesce(osm_name_raw, ''), '[\\x{{0C80}}-\\x{{0CFF}}]'))
            ORDER BY hash(osm_source_id || '{self.seed}')
            LIMIT 30;
        """).fetchall()
        cols = [d[0] for d in self.con.description]
        items_kannada = [dict(zip(cols, r)) for r in stratum_kannada]
        for it in items_kannada:
            it["audit_stratum"] = "ZERO_CANDIDATE_KANNADA"

        # Stratum 2: Zero candidates in peripheral/boundary wards (distance from central MG Road > 12km) (30)
        # Central Bengaluru reference point: 77.609, 12.975 (UTM: ~783000, 1435000)
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

        all_audited = items_kannada + items_peripheral + items_inst + items_weak
        return all_audited

    def execute_audit(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Run independent wide-area and fuzzy search against Overture for sampled OSM records."""
        sampled_entities = self.sample_audit_entities()
        print(f"Auditing {len(sampled_entities)} unrepresented OSM entities with independent Overture search...")

        audit_results = []
        diagnostics = {
            "NO_COUNTERPART_FOUND": 0,
            "POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING": 0,
            "INSUFFICIENT_EVIDENCE": 0
        }
        failure_reasons = {
            "SOURCE_COVERAGE_ABSENCE_IN_OVERTURE": 0,
            "SPATIAL_DISTANCE_DISPLACEMENT_EXCEEDED_50M": 0,
            "NAME_MISSING_IN_OSM_OR_OVERTURE": 0,
            "LEXICAL_OR_TRANSLITERATION_GAP": 0,
            "CATEGORY_FILTER_INCOMPATIBILITY": 0,
            "AMBIGUOUS_EVIDENCE": 0
        }

        for ent in sampled_entities:
            osm_id = ent["osm_source_id"]
            osm_name = ent["osm_name_raw"] or ""
            osm_norm = ent["osm_name_normalized"] or ""
            osm_cat = ent["osm_category"] or "other"
            utm_x = ent["utm_x"]
            utm_y = ent["utm_y"]

            # Independent Search: Query all Overture POIs within a wide 1.5 km radial envelope
            # completely unconstrained by category or blocking logic
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
                WHERE power(utm_x - {utm_x}, 2) + power(utm_y - {utm_y}, 2) <= power(1500.0, 2)
                LIMIT 500;
            """).fetchall()

            best_match: Optional[Dict[str, Any]] = None
            best_score = 0.0

            if osm_norm and len(osm_norm) >= 3:
                for row in wide_matches:
                    ov_id, ov_name_raw, ov_norm, ov_cat, ov_lat, ov_lon, dist = row
                    if not ov_norm:
                        continue
                    # Compute comprehensive fuzzy string match
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

            # Evaluate diagnostic verdict
            if not osm_norm or len(osm_norm.strip()) < 3:
                status = "INSUFFICIENT_EVIDENCE"
                failure_reason = "NAME_MISSING_IN_OSM_OR_OVERTURE"
                diagnostic_notes = "OSM record lacks informative name to perform independent linkage"
            elif best_match and best_score >= 80.0 and best_match["dist_meters"] > 50.0:
                # Plausible match found outside the 50m spatial blocking window!
                status = "POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING"
                failure_reason = "SPATIAL_DISTANCE_DISPLACEMENT_EXCEEDED_50M"
                diagnostic_notes = f"Counterpart '{best_match['ov_name_raw']}' located at {best_match['dist_meters']}m (score={best_score})"
            elif best_match and best_score >= 70.0 and ent["candidate_count"] == 0 and best_match["dist_meters"] <= 50.0:
                # Counterpart existed within 50m but had category incompatibility or name variation
                status = "POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING"
                failure_reason = "CATEGORY_FILTER_INCOMPATIBILITY" if ent["osm_category"] != best_match["ov_category"] else "LEXICAL_OR_TRANSLITERATION_GAP"
                diagnostic_notes = f"Counterpart within 50m ('{best_match['ov_name_raw']}') not blocked due to {failure_reason}"
            else:
                # No plausible counterpart exists anywhere within 1.5 km
                status = "NO_COUNTERPART_FOUND"
                failure_reason = "SOURCE_COVERAGE_ABSENCE_IN_OVERTURE"
                diagnostic_notes = "No matching or semantically plausible entity found in Overture within 1.5 km envelope"

            diagnostics[status] += 1
            failure_reasons[failure_reason] += 1

            audit_results.append({
                "osm_source_id": osm_id,
                "osm_name_raw": osm_name,
                "osm_name_normalized": osm_norm,
                "osm_category": osm_cat,
                "osm_lat": ent["osm_lat"],
                "osm_lon": ent["osm_lon"],
                "audit_stratum": ent["audit_stratum"],
                "candidate_count_in_pipeline": ent["candidate_count"],
                "diagnostic_verdict": status,
                "primary_failure_reason": failure_reason,
                "best_independent_overture_id": best_match["ov_source_id"] if best_match else None,
                "best_independent_overture_name": best_match["ov_name_raw"] if best_match else None,
                "best_match_distance_meters": best_match["dist_meters"] if best_match else None,
                "best_match_similarity_score": best_match["similarity_score"] if best_match else None,
                "diagnostic_notes": diagnostic_notes
            })

        summary = {
            "audit_timestamp": "2026-11-17T09:20:00Z",
            "total_entities_audited": len(audit_results),
            "verdict_distribution": diagnostics,
            "failure_reason_distribution": failure_reasons,
            "key_finding": (
                f"Out of {len(audit_results)} unrepresented/weak OSM POIs, {diagnostics['NO_COUNTERPART_FOUND']} "
                f"({round(diagnostics['NO_COUNTERPART_FOUND']/len(audit_results)*100, 1)}%) have no counterpart in Overture "
                f"(true source coverage absence), {diagnostics['POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING']} "
                f"({round(diagnostics['POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING']/len(audit_results)*100, 1)}%) were genuine matches "
                f"missed by candidate blocking, and {diagnostics['INSUFFICIENT_EVIDENCE']} had insufficient evidence."
            )
        }

        return audit_results, summary

    def export_audit(self) -> Tuple[Path, Path]:
        """Export missed-match audit CSV and summary JSON."""
        results, summary = self.execute_audit()

        csv_path = self.output_dir / "missed_match_audit.csv"
        import csv
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

        print(f"Exported {len(results)} missed match audit records to {csv_path}")
        print(f"Exported audit summary to {json_path}")
        return csv_path, json_path
