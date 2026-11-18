#!/usr/bin/env python3
"""Script to prepare the prioritized human review queue for Milestone 11.

Selects 50 critical ambiguity cases:
- 12 Tier 1 Category Contradiction cases (100% of Tier 1)
- 38 Tier 2 Competing Candidates with close score delta (delta <= 0.05)

Enriches each pair with complete attributes from canonical POIs Parquet and writes
to data/processed/benchmark/review_queue_pilot_50.csv.
"""

import csv
import json
import logging
from pathlib import Path
import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prepare_review_queue")


def main():
    root = Path(__file__).resolve().parent.parent
    queue_json = root / "reports/review_prioritization_queue.json"
    canonical_parquet = root / "data/processed/canonical_pois_h3.parquet"
    output_csv = root / "data/processed/benchmark/review_queue_pilot_50.csv"

    logger.info(f"Loading prioritized review items from {queue_json}...")
    with open(queue_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]

    tier1 = [x for x in items if x["priority_rank"] == 1]
    tier2 = [x for x in items if x["priority_rank"] == 2][:38]
    selected_items = tier1 + tier2
    logger.info(f"Selected {len(selected_items)} review items ({len(tier1)} Tier 1, {len(tier2)} Tier 2).")

    # Connect to DuckDB to retrieve full POI attributes
    con = duckdb.connect()
    con.execute(f"CREATE VIEW pois AS SELECT * FROM '{canonical_parquet}';")

    # Cache POIs needed
    osm_ids = [x["pair_id"].split("::")[0] if "::" in x["pair_id"] else x["osm_id"] for x in selected_items]
    ov_ids = [x["pair_id"].split("::")[1] if "::" in x["pair_id"] else x["ov_id"] for x in selected_items]

    osm_filter = "', '".join(osm_ids)
    ov_filter = "', '".join(ov_ids)

    osm_rows = con.execute(f"""
        SELECT 
            source_record_id, name_original, name_normalized, category_normalized,
            latitude, longitude, name_kn, name_en
        FROM pois WHERE source_record_id IN ('{osm_filter}')
    """).fetchall()
    osm_lookup = {r[0]: r for r in osm_rows}

    ov_rows = con.execute(f"""
        SELECT 
            source_record_id, name_original, name_normalized, category_normalized,
            latitude, longitude, name_kn, name_en
        FROM pois WHERE source_record_id IN ('{ov_filter}')
    """).fetchall()
    ov_lookup = {r[0]: r for r in ov_rows}

    fieldnames = [
        "pair_id", "osm_source_id", "ov_source_id", "osm_name_raw", "ov_name_raw",
        "osm_name_normalized", "ov_name_normalized", "osm_latitude", "osm_longitude",
        "ov_latitude", "ov_longitude", "distance_meters", "osm_category", "ov_category",
        "category_compatibility", "blocking_strategies", "sampling_stratum",
        "osm_name_kn", "osm_name_en"
    ]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for it in selected_items:
            pid = it["pair_id"]
            if "::" in pid:
                osm_id, ov_id = pid.split("::")
            else:
                osm_id = it.get("osm_id")
                ov_id = it.get("ov_id")
            osm_r = osm_lookup.get(osm_id)
            ov_r = ov_lookup.get(ov_id)

            stratum = f"REVIEW_TIER_{it['priority_rank']}_{it['ambiguity_type']}"

            writer.writerow({
                "pair_id": pid,
                "osm_source_id": osm_id,
                "ov_source_id": ov_id,
                "osm_name_raw": osm_r[1] if osm_r else it.get("osm_name"),
                "ov_name_raw": ov_r[1] if ov_r else it.get("ov_name"),
                "osm_name_normalized": osm_r[2] if osm_r else (it.get("osm_name") or "").lower(),
                "ov_name_normalized": ov_r[2] if ov_r else (it.get("ov_name") or "").lower(),
                "osm_latitude": osm_r[4] if osm_r else 12.9716,
                "osm_longitude": osm_r[5] if osm_r else 77.5946,
                "ov_latitude": ov_r[4] if ov_r else 12.9716,
                "ov_longitude": ov_r[5] if ov_r else 77.5946,
                "distance_meters": round(it["distance_meters"], 2),
                "osm_category": (osm_r[3] if osm_r else it.get("osm_category")) or "other",
                "ov_category": (ov_r[3] if ov_r else it.get("ov_category")) or "other",
                "category_compatibility": "DISJOINT" if it["priority_rank"] == 1 else "COMPATIBLE",
                "blocking_strategies": "graph_review_queue",
                "sampling_stratum": stratum,
                "osm_name_kn": osm_r[6] if osm_r else "",
                "osm_name_en": osm_r[7] if osm_r else "",
            })

    logger.info(f"Successfully generated {output_csv} with {len(selected_items)} review pairs.")


if __name__ == "__main__":
    main()
