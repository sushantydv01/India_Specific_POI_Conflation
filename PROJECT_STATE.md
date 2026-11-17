# Project State: India-Specific POI Conflation

**Document Purpose:** Persistent state and decision log tracking repository progress, environment baselines, technical decisions, and planned milestones.

---

## 1. Current Milestone

- **Milestone:** Milestone 2 — Data Ingestion & Canonical Schema
- **Status:** **Milestone 2 Complete** (Bengaluru POI Ingestion, Boundary Extraction, and Canonical Harmonization Achieved)
- **Selected Target City:** **Bengaluru (Bruhat Bengaluru Mahanagara Palike — BBMP)**
  - *OSM Relation:* `7902476` (`admin_level=7`)
  - *Bounding Box:* `[77.4598797, 12.8334905, 77.7840639, 13.1426196]`
  - *BBMP Polygon Area:* **717.21 km²** (EPSG:32643 UTM 43N) / **716.37 km²** (WGS84 Spheroid)
  - *Envelope Area:* 1,204.25 km²
  - *Contained Overture POIs:* **197,820**
  - *Contained OSM POIs:* **49,036**
  - *Total Canonical POIs:* **246,856**

---

## 2. Verified Environment & Hardware Baseline

All values recorded below are derived directly from system execution logs on 2026-11-17:

| Dimension | Parameter | Verified Value | Source / Verification Method |
| :--- | :--- | :--- | :--- |
| **System** | Platform / OS | macOS (Darwin 24.3.0) | Verified via `system_profiler` / `uname -m` |
| **Hardware** | Processor Chip | Apple M3 | `system_profiler SPHardwareDataType` |
| **Hardware** | Architecture | `arm64` | `uname -m` |
| **Hardware** | Physical Memory | 8 GB RAM | `system_profiler SPHardwareDataType` |
| **Storage** | Available Disk Space | ~156 GiB free (out of 460 GiB, 64% used) | `df -h ~` |
| **Tooling** | Python Virtual Env | Python 3.12.16 (`.venv`) | Created via `/opt/homebrew/bin/python3.12` |
| **Tooling** | DuckDB Python / CLI | DuckDB v2.0.0 | `duckdb --version` |
| **Tooling** | Geospatial Tooling | PyArrow 26.0.1, Shapely 2.2.0, PyOsmium 4.3.2, PyProj 3.8.0, osmium-tool 1.19.1 | Pip / Homebrew inventory |
| **Tooling** | Git Version | git version 2.47.0 | `git --version` |
| **Repository** | Working Directory | `/Users/sushantydv01/Desktop/India_Specific_POI_Conflation` | `pwd` |
| **Repository** | Active Branch | `main` | `git branch --show-current` |
| **Repository** | Remote URL | `https://github.com/sushantydv01/India_Specific_POI_Conflation.git` | `git remote -v` |
| **Git Identity**| User Name | `Sushant Yadav` | `git config user.name` |
| **Git Identity**| User Email | `sushantyadav8168@gmail.com` | `git config user.email` |
| **Overture** | Places Release | `2026-10-21.0` | S3 remote GeoParquet query |
| **OSM Source** | Regional Extract | Geofabrik Southern Zone `2026-11-16T21:22:36Z` | PBF extract sliced by BBMP boundary |

---

## 3. Milestone Progress

### Completed Tasks (Milestone 1 & Milestone 2)
- [x] Environment inspection and hardware profiling executed.
- [x] Git repository initialized with primary branch designated as `main`.
- [x] Remote tracking URL verified and linked to GitHub repository.
- [x] Existing Git committer identity (`Sushant Yadav`) verified and preserved.
- [x] Comprehensive `.gitignore` established for data engineering, Python, and geospatial workloads.
- [x] Foundational `README.md` authored detailing project goals, sources, licensing, and milestones.
- [x] Detailed project scoping document authored in `docs/project_scope.md`.
- [x] Initial commit created (`82aae69`).
- [x] Overture Maps latest release (`2026-10-21.0`) queried over remote S3 using DuckDB across 4 candidate cities.
- [x] Empirical OpenStreetMap POI extraction conducted via official OSM API `v0.6` across standardized commercial cores.
- [x] Comparative data feasibility report authored in `docs/data_feasibility_report.md`.
- [x] Defensible, evidence-backed city selection determined (**Bengaluru**).
- [x] **Milestone 2 Pre-implementation audit:** Disproved 206k bounding-box polygon confusion; verified BBMP polygon area (717.21 km²) and true point-in-polygon containment (197,820 Overture records).
- [x] Dedicated Python 3.12 virtual environment established with DuckDB, PyArrow, Shapely, PyOsmium, PyProj, and Pytest.
- [x] Acquired, validated, and normalized BBMP boundary relation (`7902476`) to `configs/bbmp_boundary.geojson`.
- [x] Implemented Overture ingestion pipeline (`OvertureIngestor`) exporting `data/raw/overture/bengaluru_overture_places.parquet` (197,820 records, 19 MB).
- [x] Implemented OSM ingestion pipeline (`OSMIngestor`) with offline `osmium-tool` extraction exporting `data/raw/osm/bengaluru_osm_pois.parquet` (49,036 records, 4.03 MB).
- [x] Designed canonical analytical data model and PyArrow schema (`CanonicalPOI`).
- [x] Implemented canonical transformation pipeline (`CanonicalTransformer`) producing `data/processed/canonical_pois.parquet` (246,856 records, 25.79 MB).
- [x] Built comprehensive validation suite (`POIValidator`) and test suite (17 passing tests in `tests/`).
- [x] Authored data dictionary (`docs/data_dictionary.md`) and legal licensing architecture (`docs/licensing_and_attribution.md`).

### Pending Tasks (Milestone 3 Roadmap)
- [ ] Milestone 3: Exploratory Data Analysis & Spatial Indexing Foundation (H3 discrete global grid assignment, category mapping validation, and lexical distribution profiling).
- [ ] Milestone 4: Candidate Generation & Blocking (Spatial proximity radius + H3 cell adjacency + phonetic blocking).

---

## 4. Architecture Decisions Log (ADL)

| ID | Topic | Decision | Status | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | Git Initialization & Remote | Initialize git with default branch `main` and set `origin` to https://github.com/sushantydv01/India_Specific_POI_Conflation.git | **Approved** | Standard git hygiene; preserves user identity. |
| **ADR-002** | Data Separation | Enforce strict exclusion of raw data, intermediates, and databases from version control via `.gitignore`. | **Approved** | Geospatial datasets exceed Git capacity and must be fetched/reproduced programmatically. |
| **ADR-003** | Python 3.12 Virtual Environment | Use Python 3.12 (`/opt/homebrew/bin/python3.12`) in `.venv` rather than system Python 3.14. | **Approved** | Python 3.14 lacks pre-built binary wheels for compiled C/C++ extensions (`pyosmium`, `pyarrow`, `shapely`, `pyproj`). Python 3.12 provides stable ARM64 wheels. |
| **ADR-004** | Target City Selection | Select **Bengaluru (BBMP)** as the initial study city. | **Approved** | Bengaluru exhibits highest OSM POI density (523.4 POIs/km²), richest Indic transliteration tags, self-contained administrative geometry, and high Overture completeness. |
| **ADR-005** | OSM Extraction Strategy | Reject public Overpass for citywide extraction; use Geofabrik Southern Zone PBF (`southern-zone-latest.osm.pbf`) + polygon extraction via `osmium extract` CLI + PyOsmium parsing. | **Approved** | Public Overpass servers fail with HTTP 502/403 on large spatial envelopes. Offline PBF extraction provides deterministic, fast (3.5s) slicing. |
| **ADR-006** | Overture Remote Ingestion | Use DuckDB `httpfs` + `read_parquet` predicate pushdown on bounding box + `ST_Within` against BBMP polygon directly against Overture S3 GeoParquet. | **Approved** | Streams only target records in ~25s without downloading 15+ GB global dumps. |
| **ADR-007** | Coordinate Axis Ordering | Explicitly configure `SET geometry_always_xy = true;` in DuckDB spatial sessions. | **Approved** | Prevents latitude/longitude axis order inversion in WKT and GeoParquet geometries. |
| **ADR-008** | Canonical Schema Definition | Unify POI sources into a flat, strongly typed PyArrow table with 10 canonical categories and structured provenance dictionaries. | **Approved** | High-performance analytical columnar format, ZSTD compression, zero-copy querying in DuckDB, and lossless traceability to upstream sources. |

---

## 5. Summary of Verified City Feasibility Findings

All figures below reflect actual measured outputs obtained during the 2026-11-17 investigation:

| Metric | Bengaluru (BBMP) | Delhi (NCT) | Pune (PMC Extent) | Hyderabad (GHMC) |
| :--- | :--- | :--- | :--- | :--- |
| **Overture Total Records** | **197,820** (206,752 bbox) | 302,421 | 103,039 | 152,640 |
| **Overture Complete Addresses** | 183,500+ (92.8%) | 265,664 (87.8%) | 92,996 (90.3%) | 139,332 (91.3%) |
| **Overture Core Records ($3.63\text{ km}^2$)** | 5,247 | 5,833 | 5,544 | 3,288 |
| **OSM Citywide Contained POIs** | **49,036** | ~35,000 (est) | ~15,000 (est) | ~8,000 (est) |
| **OSM Core POI Count ($3.63\text{ km}^2$)** | **1,900** | 1,390 | 550 | 195 |
| **OSM Core Density (POIs/km²)** | **523.4** | 382.9 | 151.5 | 53.7 |
| **OSM Core Named POIs** | 1,400 (73.7%) | 965 (69.4%) | 460 (83.6%) | 167 (85.6%) |
| **OSM Core Local Script Tags** | **212 (`name:kn`)** | 62 (`name:hi`) | 204 (`name:mr`) | 19 (`name:te`) |
| **Proximity Pairs within 50m (Core)** | 9,636 | 11,337 | 1,713 | 1,039 |
| **Plausible Token Overlap Pairs (<50m)** | **239** | **269** | 75 | 56 |
| **Administrative Boundary Clarity** | **High (BBMP)** | Low (NCR ambiguity)| Moderate (PMC vs PMRDA)| Moderate (GHMC vs HMDA) |

---

## 6. Known Uncertainties & Risks

1. **Category Mapping Granularity:** Cross-source alignment between Overture taxonomy levels and OSM tag keys (`amenity`, `shop`, etc.) leaves a fraction of unclassified or broad classifications. Milestone 3 will quantify classification entropy.
2. **Vernacular Script Imbalance:** While Bengaluru has the highest number of Indic Kannada tags (`name:kn`), English remains dominant in Overture. Conflation requires robust transliteration models (e.g., Indic NLP library or rule-based soundex/double-metaphone variants).
3. **Centroid vs. Polygon Footprints:** Large commercial entities (malls, tech parks, hospitals) represented as ways in OSM collapse to centroids, potentially shifting their coordinates by 50–200 meters from Overture point markers.
