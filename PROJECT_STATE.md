# Project State: India-Specific POI Conflation

**Document Purpose:** Persistent state and decision log tracking repository progress, environment baselines, technical decisions, and planned milestones.

---

## 1. Current Milestone

- **Milestone:** Milestone 1 — Feasibility and Environment
- **Status:** **Milestone 1 Complete** (Empirical Data Feasibility & Environment Verification Achieved)
- **Selected Target City:** **Bengaluru (Bruhat Bengaluru Mahanagara Palike — BBMP)**
  - *OSM Relation:* `7902476` (admin_level 7)
  - *Bounding Box:* `[12.8340, 77.4600, 13.1430, 77.7840]`
  - *Envelope Area:* ~1,200 km² (BBMP Municipal Area: ~709–741 km²)
  - *Primary Language:* Kannada (`kn`) alongside English (`en`)

---

## 2. Verified Environment & Hardware Baseline

All values recorded below are derived directly from system execution logs on 2026-11-17:

| Dimension | Parameter | Verified Value | Source / Verification Method |
| :--- | :--- | :--- | :--- |
| **System** | Platform / OS | macOS (Darwin) | Verified via `system_profiler` / `uname -m` |
| **Hardware** | Processor Chip | Apple M3 | `system_profiler SPHardwareDataType` |
| **Hardware** | Architecture | `arm64` | `uname -m` |
| **Hardware** | Physical Memory | 8 GB RAM | `system_profiler SPHardwareDataType` |
| **Storage** | Available Disk Space | ~157 GiB free (out of 460 GiB, 64% used) | `df -h ~` |
| **Tooling** | Python Version | Python 3.14.3 | `python3 --version` |
| **Tooling** | Python Binary Path | `/opt/homebrew/bin/python3` | `which python3` |
| **Tooling** | DuckDB CLI | DuckDB v2.0.0 (brew bottled) | `duckdb --version` |
| **Tooling** | Git Version | git version 2.47.0 | `git --version` |
| **Repository** | Working Directory | `/Users/sushantydv01/Desktop/India_Specific_POI_Conflation` | `pwd` |
| **Repository** | Active Branch | `main` | `git branch --show-current` |
| **Repository** | Remote URL | `https://github.com/sushantydv01/India_Specific_POI_Conflation.git` | `git remote -v` |
| **Git Identity**| User Name | `Sushant Yadav` | `git config user.name` |
| **Git Identity**| User Email | `sushantyadav8168@gmail.com` | `git config user.email` |
| **Overture** | Latest Places Release | `2026-10-21.0` | Verified via STAC `https://stac.overturemaps.org/` |

---

## 3. Milestone Progress

### Completed Tasks (Milestone 1)
- [x] Environment inspection and hardware profiling executed.
- [x] Git repository initialized with primary branch designated as `main`.
- [x] Remote tracking URL verified and linked to GitHub repository.
- [x] Existing Git committer identity (`Sushant Yadav`) verified and preserved.
- [x] Comprehensive `.gitignore` established for data engineering, Python, and geospatial workloads.
- [x] Foundational `README.md` authored detailing project goals, sources, licensing, and milestones.
- [x] Detailed project scoping document authored in `docs/project_scope.md`.
- [x] Initial commit created (`82aae69`).
- [x] Overture Maps latest release (`2026-10-21.0`) queried over remote S3 using DuckDB across 4 candidate cities (Bengaluru, Delhi, Pune, Hyderabad).
- [x] Empirical OpenStreetMap POI extraction conducted via official OSM API `v0.6` across standardized downtown commercial cores ($3.63\text{ km}^2$).
- [x] Public Overpass API evaluated; documented infrastructure limitations (HTTP 502/403/400 under heavy load).
- [x] Comparative data feasibility report authored in `docs/data_feasibility_report.md`.
- [x] Defensible, evidence-backed city selection determined (**Bengaluru**).

### Pending Tasks (Milestone 2 & 3 Roadmap)
- [ ] Determine Python virtual environment strategy (audit Python 3.12 vs 3.14 for binary C-extension packages like `pyarrow`, `shapely`, `geopandas`, `h3`).
- [ ] Milestone 2: Establish data acquisition pipeline for Bengaluru (Geofabrik Southern Zone OSM PBF + DuckDB Overture extraction).
- [ ] Milestone 3: Schema harmonization and canonical POI data model design.

---

## 4. Architecture Decisions Log (ADL)

| ID | Topic | Decision | Status | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | Git Initialization & Remote | Initialize git with default branch `main` and set `origin` to https://github.com/sushantydv01/India_Specific_POI_Conflation.git | **Approved** | Standard git hygiene; preserves user identity. |
| **ADR-002** | Data Separation | Enforce strict exclusion of raw data, intermediates, and databases from version control via `.gitignore`. | **Approved** | Geospatial datasets exceed Git capacity and must be fetched/reproduced programmatically. |
| **ADR-003** | Provisional Tech Stack | Propose DuckDB + Parquet + H3 + GeoPandas + RapidFuzz + Splink for local-first execution. | **Provisional** | Subject to environment validation and Python 3.14 wheel availability testing. |
| **ADR-004** | Target City Selection | Select **Bengaluru (BBMP)** as the initial study city. | **Approved** | Bengaluru exhibits highest OSM POI density (523.4 POIs/km²), richest Indic transliteration tags (212 `name:kn`), self-contained administrative geometry, and proven Overture completeness (206,752 records, 92.8% full addresses). |
| **ADR-005** | OSM Extraction Strategy | Reject public Overpass for citywide extraction; use Geofabrik Southern Zone PBF (`southern-zone-latest.osm.pbf`, 533 MB) + bounding box extraction via `osmium`. | **Approved** | Public Overpass servers return recurring 502/403/400 gateway capacity failures for large Indian bounding boxes. Zonal PBFs provide deterministic, offline reproducibility. |
| **ADR-006** | Overture Remote Ingestion | Use DuckDB `httpfs` + `read_parquet` predicate pushdown on `bbox` attributes directly against Overture S3 GeoParquet. | **Approved** | Eliminates downloading 15+ GB global dumps; streams only target bounding boxes in < 25s with < 250 MB memory. |

---

## 5. Summary of Verified City Feasibility Findings

All figures below reflect actual measured outputs obtained during the 2026-11-17 investigation:

| Metric | Bengaluru (BBMP) | Delhi (NCT) | Pune (PMC Extent) | Hyderabad (GHMC) |
| :--- | :--- | :--- | :--- | :--- |
| **Overture Total Records** | **206,752** | 302,421 | 103,039 | 152,640 |
| **Overture Complete Addresses** | 191,938 (92.8%) | 265,664 (87.8%) | 92,996 (90.3%) | 139,332 (91.3%) |
| **Overture Core Records ($3.63\text{ km}^2$)** | 5,247 | 5,833 | 5,544 | 3,288 |
| **OSM Core POI Count ($3.63\text{ km}^2$)** | **1,900** | 1,390 | 550 | 195 |
| **OSM Core Density (POIs/km²)** | **523.4** | 382.9 | 151.5 | 53.7 |
| **OSM Core Named POIs** | 1,400 (73.7%) | 965 (69.4%) | 460 (83.6%) | 167 (85.6%) |
| **OSM Core Local Script Tags** | **212 (`name:kn`)** | 62 (`name:hi`) | 204 (`name:mr`) | 19 (`name:te`) |
| **Proximity Pairs within 50m (Core)** | 9,636 | 11,337 | 1,713 | 1,039 |
| **Plausible Token Overlap Pairs (<50m)** | **239** | **269** | 75 | 56 |
| **Administrative Boundary Clarity** | **High (BBMP)** | Low (NCR ambiguity)| Moderate (PMC vs PMRDA)| Moderate (GHMC vs HMDA) |

---

## 6. Known Uncertainties & Risks

1. **Python 3.14 Binary Wheel Availability:** Key geospatial packages (such as `shapely`, `geopandas`, `pyarrow`, `h3`, `rapidfuzz`) are being actively tested on macOS `arm64` under Python 3.14.3. If stable binary wheels are missing, a dedicated Python 3.12 virtual environment (`python@3.12` installed via Homebrew) will serve as the sanctioned fallback.
2. **Commercial Vertical Clustering:** The $97.5\%$ distractor rate within 50m in Bengaluru's commercial core (Commercial St, Brigade Rd) proves that candidate blocking must incorporate category and token filtering, not just spatial radius.
3. **Data Licensing Boundary:** While Overture is CDLA Permissive v2.0, OSM data is governed by ODbL 1.0 Share-Alike. Conflated artifacts published externally must be licensed under ODbL with `© OpenStreetMap contributors` attribution.

---

## 7. Next Actions

1. Review and verify [data_feasibility_report.md](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/docs/data_feasibility_report.md) and [PROJECT_STATE.md](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/PROJECT_STATE.md).
2. Commit changes locally with suggested message `docs: add India POI data feasibility assessment`.
3. Provide final technical synthesis report to the user.
