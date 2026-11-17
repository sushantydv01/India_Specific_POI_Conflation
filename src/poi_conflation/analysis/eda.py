"""Exploratory Data Analysis module for Bengaluru POI datasets.

Analyzes source-level statistics, spatial distributions across H3 cells,
canonical category distributions, and attribute completeness matrices.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List

import duckdb
import pyarrow.parquet as pq


class EDAAnalyzer:
    """Executes exploratory data analysis on the spatially indexed canonical dataset."""

    def __init__(
        self,
        indexed_dataset_path: str = "data/processed/canonical_pois_h3.parquet",
        output_dir: str = "reports"
    ):
        self.dataset_path = Path(indexed_dataset_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect()

    def run_source_statistics(self) -> Dict[str, Any]:
        """Compute comprehensive source-level statistics for OSM and Overture."""
        print("Computing source-level POI statistics...")
        query = f"""
        SELECT 
            poi_source,
            count(*) as total_pois,
            count(CASE WHEN name_original IS NOT NULL AND length(trim(name_original)) > 0 THEN 1 END) as named_pois,
            count(CASE WHEN name_original IS NULL THEN 1 END) as null_names,
            count(CASE WHEN name_original IS NOT NULL AND length(trim(name_original)) = 0 THEN 1 END) as empty_names,
            count(distinct CASE WHEN name_original IS NOT NULL AND length(trim(name_original)) > 0 THEN name_original END) as unique_names,
            count(CASE WHEN category_normalized = 'other' THEN 1 END) as unclassified_category_count,
            count(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 END) as missing_coordinates,
            count(CASE WHEN address_original IS NOT NULL OR address_locality IS NOT NULL OR address_postcode IS NOT NULL THEN 1 END) as with_any_address,
            count(CASE WHEN address_postcode IS NOT NULL THEN 1 END) as with_pin_code,
            count(CASE WHEN phone IS NOT NULL AND length(trim(phone)) > 0 THEN 1 END) as with_phone,
            count(CASE WHEN website IS NOT NULL AND length(trim(website)) > 0 THEN 1 END) as with_website,
            avg(confidence) as avg_confidence,
            median(confidence) as median_confidence,
            min(confidence) as min_confidence,
            max(confidence) as max_confidence
        FROM '{self.dataset_path}'
        GROUP BY poi_source
        """
        rows = self.con.execute(query).fetchall()
        cols = [c[0] for c in self.con.description]
        stats = {}
        for r in rows:
            src = r[0]
            d = dict(zip(cols, r))
            # Calculate derived percentages
            total = d["total_pois"]
            d["named_pct"] = round(100.0 * d["named_pois"] / total, 2)
            d["unclassified_category_pct"] = round(100.0 * d["unclassified_category_count"] / total, 2)
            d["address_completeness_pct"] = round(100.0 * d["with_any_address"] / total, 2)
            d["pin_code_pct"] = round(100.0 * d["with_pin_code"] / total, 2)
            d["phone_pct"] = round(100.0 * d["with_phone"] / total, 2)
            d["website_pct"] = round(100.0 * d["with_website"] / total, 2)
            stats[src] = d

        return stats

    def run_category_analysis(self) -> Dict[str, Any]:
        """Compute category frequency and distribution comparison across sources."""
        print("Computing category distribution and cross-source comparison...")
        query = f"""
        SELECT 
            category_normalized,
            count(*) as total_count,
            count(CASE WHEN poi_source = 'OVERTURE' THEN 1 END) as overture_count,
            count(CASE WHEN poi_source = 'OSM' THEN 1 END) as osm_count
        FROM '{self.dataset_path}'
        GROUP BY category_normalized
        ORDER BY total_count DESC
        """
        rows = self.con.execute(query).fetchall()
        categories = []
        for cat, total, ov, osm in rows:
            categories.append({
                "category": cat,
                "total_count": total,
                "overture_count": ov,
                "osm_count": osm,
                "overture_pct": round(100.0 * ov / 197820, 2),
                "osm_pct": round(100.0 * osm / 49036, 2),
                "ratio_ov_to_osm": round(ov / osm, 2) if osm > 0 else None
            })
        return {"canonical_categories": categories}

    def run_spatial_distribution(self) -> Dict[str, Any]:
        """Analyze spatial aggregation and identify density hubs at H3 res 8, 9, 10."""
        print("Analyzing spatial distribution across H3 resolution cells...")
        # Overall cell counts
        res_summary = {}
        for res in [8, 9, 10]:
            col = f"h3_res{res}"
            q_counts = f"""
            SELECT 
                count(distinct {col}) as total_cells,
                count(distinct CASE WHEN poi_source = 'OVERTURE' THEN {col} END) as overture_cells,
                count(distinct CASE WHEN poi_source = 'OSM' THEN {col} END) as osm_cells
            FROM '{self.dataset_path}'
            """
            r_counts = self.con.execute(q_counts).fetchone()

            q_stats = f"""
            SELECT 
                avg(c) as avg_pois,
                median(c) as median_pois,
                max(c) as max_pois
            FROM (
                SELECT {col}, count(*) as c
                FROM '{self.dataset_path}'
                GROUP BY {col}
            )
            """
            r_stats = self.con.execute(q_stats).fetchone()

            res_summary[f"res_{res}"] = {
                "total_unique_cells": r_counts[0],
                "overture_cells": r_counts[1],
                "osm_cells": r_counts[2],
                "avg_pois_per_cell": round(r_stats[0], 2) if r_stats[0] is not None else 0.0,
                "median_pois_per_cell": r_stats[1] if r_stats[1] is not None else 0,
                "max_pois_per_cell": r_stats[2] if r_stats[2] is not None else 0
            }

        # Top 15 density hotspots at Resolution 8
        top_h8_q = f"""
        SELECT 
            h3_res8,
            count(*) as total_pois,
            count(CASE WHEN poi_source = 'OVERTURE' THEN 1 END) as overture_pois,
            count(CASE WHEN poi_source = 'OSM' THEN 1 END) as osm_pois,
            avg(latitude) as center_lat,
            avg(longitude) as center_lon,
            round(count(CASE WHEN poi_source = 'OVERTURE' THEN 1 END)::FLOAT / NULLIF(count(CASE WHEN poi_source = 'OSM' THEN 1 END), 0), 2) as ov_osm_ratio
        FROM '{self.dataset_path}'
        GROUP BY h3_res8
        ORDER BY total_pois DESC
        LIMIT 15
        """
        top_h8_rows = self.con.execute(top_h8_q).fetchall()
        top_h8_cols = [c[0] for c in self.con.description]
        top_h8 = [dict(zip(top_h8_cols, r)) for r in top_h8_rows]

        return {
            "resolution_summary": res_summary,
            "top_hotspots_res8": top_h8
        }

    def run_attribute_completeness_matrix(self) -> Dict[str, Any]:
        """Generate completeness matrix comparing field populations across sources."""
        print("Evaluating attribute completeness matrix...")
        attributes = [
            "name_original",
            "name_normalized",
            "alternate_names",
            "name_en",
            "name_kn",
            "category_normalized",
            "address_original",
            "address_locality",
            "address_postcode",
            "phone",
            "website",
            "confidence",
            "source_timestamp"
        ]

        matrix = {}
        for attr in attributes:
            if attr == "alternate_names":
                q = f"""
                SELECT 
                    poi_source,
                    count(*) as total,
                    count(CASE WHEN len(alternate_names) > 0 THEN 1 END) as populated
                FROM '{self.dataset_path}'
                GROUP BY poi_source
                """
            else:
                q = f"""
                SELECT 
                    poi_source,
                    count(*) as total,
                    count(CASE WHEN {attr} IS NOT NULL AND length(trim(CAST({attr} AS VARCHAR))) > 0 THEN 1 END) as populated
                FROM '{self.dataset_path}'
                GROUP BY poi_source
                """
            rows = self.con.execute(q).fetchall()
            row_dict = {}
            for src, tot, pop in rows:
                row_dict[f"{src}_count"] = pop
                row_dict[f"{src}_pct"] = round(100.0 * pop / tot, 2)
            matrix[attr] = row_dict

        return matrix

    def run_full_eda(self) -> Dict[str, Any]:
        """Execute all EDA sub-analyses and save reports/eda_summary.json."""
        t0 = time.time()
        print("=" * 70)
        print("RUNNING EXPLORATORY DATA ANALYSIS")
        print("=" * 70)

        results = {
            "analysis_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_dataset": str(self.dataset_path),
            "source_statistics": self.run_source_statistics(),
            "category_analysis": self.run_category_analysis(),
            "spatial_distribution": self.run_spatial_distribution(),
            "attribute_completeness_matrix": self.run_attribute_completeness_matrix(),
            "execution_duration_seconds": round(time.time() - t0, 2)
        }

        out_json = self.output_dir / "eda_summary.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print(f"\nEDA completed in {results['execution_duration_seconds']}s")
        print(f"Summary saved to: {out_json}")
        return results
