# Project State: India-Specific POI Conflation

**Document Purpose:** Persistent state and decision log tracking repository progress, environment baselines, technical decisions, and planned milestones.

---

## 1. Current Milestone

- **Milestone:** Milestone 3 — Exploratory Data Analysis & Spatial Indexing Foundation
- **Status:** **Milestone 3 Complete** (Spatially Indexed Canonical Dataset, Cross-Source Proximity Profiling, and Naming Analysis Achieved)
- **Selected Target City:** **Bengaluru (Bruhat Bengaluru Mahanagara Palike — BBMP)**
  - *OSM Relation:* `7902476` (`admin_level=7`)
  - *Bounding Box:* `[77.4598797, 12.8334905, 77.7840639, 13.1426196]`
  - *BBMP Polygon Area:* **717.21 km²** (EPSG:32643 UTM 43N) / **716.37 km²** (WGS84 Spheroid)
  - *Total Canonical Records:* **246,856** (197,820 Overture + 49,036 OSM)
  - *Spatially Indexed Artifact:* `data/processed/canonical_pois_h3.parquet` (31.68 MB)
  - *H3 Unique Cells:* 996 (Res 8), 6,042 (Res 9), 29,902 (Res 10)
  - *Candidate Pairs within 50m:* **620,892 pairs** (reaching 87.57% of OSM POIs)
  - *Kannada Script Presence:* 6,223 in OSM (12.69%) vs 400 in Overture (0.20%)

---

## 2. Verified Environment & Hardware Baseline

All values recorded below are derived directly from system execution logs on 2026-11-17:

| Dimension | Parameter | Verified Value | Source / Verification Method |
| :--- | :--- | :--- | :--- |
| **System** | Platform / OS | macOS (Darwin 24.3.0) | Verified via `system_profiler` / `uname -m` |
| **Hardware** | Processor Chip | Apple M3 | `system_profiler SPHardwareDataType` |
| **Hardware** | Architecture | `arm64` | `uname -m` |
| **Hardware** | Physical Memory | 8 GB RAM | `system_profiler SPHardwareDataType` |
| **Storage** | Available Disk Space | ~155 GiB free (out of 460 GiB, 64% used) | `df -h ~` |
| **Tooling** | Python Virtual Env | Python 3.12.16 (`.venv`) | Created via `/opt/homebrew/bin/python3.12` |
| **Tooling** | DuckDB Python / CLI | DuckDB v2.0.0 | `duckdb --version` |
| **Tooling** | Geospatial Tooling | PyArrow 26.0.1, Shapely 2.2.0, PyOsmium 4.3.2, PyProj 3.8.0, osmium-tool 1.19.1, H3 4.2.1 | Pip / Homebrew inventory |
| **Tooling** | NLP / ML Tooling | RapidFuzz 3.12.2, Matplotlib 3.10.1 | Pip inventory |
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

### Completed Tasks (Milestones 1, 2, and 3)
- [x] Environment inspection and hardware profiling executed.
- [x] Git repository initialized with primary branch designated as `main`.
- [x] Remote tracking URL verified and linked to GitHub repository.
- [x] Existing Git committer identity (`Sushant Yadav`) verified and preserved.
- [x] Comprehensive `.gitignore` established for data engineering, Python, and geospatial workloads.
- [x] Foundational `README.md` authored detailing project goals, sources, licensing, and milestones.
- [x] Detailed project scoping document authored in `docs/project_scope.md`.
- [x] Initial commit created (`82aae69`).
- [x] Comparative data feasibility report authored in `docs/data_feasibility_report.md`.
- [x] Verified BBMP polygon area (717.21 km²) and true point-in-polygon containment (197,820 Overture records).
- [x] Acquired, validated, and normalized BBMP boundary relation (`7902476`) to `configs/bbmp_boundary.geojson`.
- [x] Ingested Overture Places (`data/raw/overture/bengaluru_overture_places.parquet`, 197,820 records).
- [x] Ingested OSM POIs (`data/raw/osm/bengaluru_osm_pois.parquet`, 49,036 records).
- [x] Transformed to Canonical POI Schema (`data/processed/canonical_pois.parquet`, 246,856 records).
- [x] **Milestone 3 Audit Resolutions:** Reconciled 10 canonical categories across code, data dictionary, and tests; corrected Indic Unicode normalization preserving Kannada characters and combining vowel signs; reconciled stage runtimes; updated licensing analysis.
- [x] Implemented independent dataset integrity audit (`scripts/audit_dataset_integrity.py` $\rightarrow$ `reports/dataset_integrity_audit.json`).
- [x] Implemented Uber H3 multi-resolution spatial indexing (Res 8, 9, 10) producing `data/processed/canonical_pois_h3.parquet` (31.68 MB) in 1.59s.
- [x] Assigned deterministic collision-free UUIDv5 canonical identifiers (`canonical_poi_id`).
- [x] Executed full Exploratory Data Analysis (`EDAAnalyzer`) producing source-level stats, category distribution, H3 hotspots, and attribute completeness matrix.
- [x] Implemented metric spatial proximity analyzer using 200m grid equi-joins in DuckDB, evaluating 10m, 25m, 50m, 100m, 200m candidate thresholds in under 2 seconds.
- [x] Executed Kannada naming and transliteration profiling (`NamingProfiler`), discovering 12.69% vernacular presence in OSM vs 0.20% in Overture, and benchmarking RapidFuzz baseline scores.
- [x] Rendered 6 publication-quality analytical visualizations in `reports/figures/`.
- [x] Authored comprehensive documentation (`docs/spatial_indexing.md`, `docs/eda_report.md`, `docs/name_and_transliteration_analysis.md`).
- [x] Built automated test suite covering H3 indexing, lexical similarity, and EDA consistency (26 passing tests).

### Pending Tasks (Milestone 4 Roadmap)
- [ ] Milestone 4: Candidate Generation & Multi-Attribute Blocking (H3 k-ring cell blocking, metric spatial proximity filtering, phonetic double-metaphone blocking, and category compatibility pruning).
- [ ] Milestone 5: Pairwise Feature Engineering & Classification Pipeline.

---

## 4. Architecture Decisions Log (ADL)

| ID | Topic | Decision | Status | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | Git Initialization & Remote | Initialize git with default branch `main` and set `origin`. | **Approved** | Standard hygiene. |
| **ADR-002** | Data Separation | Enforce strict exclusion of raw data, intermediates, and databases from version control via `.gitignore`. | **Approved** | Geospatial datasets exceed Git capacity and must be fetched/reproduced programmatically. |
| **ADR-003** | Python 3.12 Virtual Environment | Use Python 3.12 (`/opt/homebrew/bin/python3.12`) in `.venv` rather than system Python 3.14. | **Approved** | Python 3.14 lacks pre-built binary wheels for compiled C/C++ extensions (`pyosmium`, `pyarrow`, `shapely`, `pyproj`, `h3`). |
| **ADR-004** | Target City Selection | Select **Bengaluru (BBMP)** as the initial study city. | **Approved** | Highest OSM POI density, richest Indic transliteration tags, self-contained administrative geometry, and high Overture completeness. |
| **ADR-005** | OSM Extraction Strategy | Reject public Overpass for citywide extraction; use Geofabrik Southern Zone PBF + polygon extraction via `osmium extract` CLI + PyOsmium parsing. | **Approved** | Public Overpass servers fail with HTTP 502/403 on large spatial envelopes. Offline PBF extraction provides deterministic, fast (3.5s) slicing. |
| **ADR-006** | Overture Remote Ingestion | Use DuckDB `httpfs` + `read_parquet` predicate pushdown on bounding box + `ST_Within` against BBMP polygon directly against Overture S3 GeoParquet. | **Approved** | Streams only target records in ~25s without downloading 15+ GB global dumps. |
| **ADR-007** | Coordinate Axis Ordering | Explicitly configure `SET geometry_always_xy = true;` in DuckDB spatial sessions. | **Approved** | Prevents latitude/longitude axis order inversion in WKT and GeoParquet geometries. |
| **ADR-008** | Canonical Schema Definition | Unify POI sources into a flat, strongly typed PyArrow table with 10 canonical categories and structured provenance dictionaries. | **Approved** | High-performance analytical columnar format, ZSTD compression, zero-copy querying in DuckDB, and lossless traceability to upstream sources. |
| **ADR-009** | H3 Spatial Indexing | Index all canonical POIs simultaneously at H3 resolutions 8 (~461m), 9 (~174m), and 10 (~66m) in `canonical_pois_h3.parquet`. | **Approved** | Multi-scale discrete global grid partitions enable hierarchical blocking: macro-neighborhoods (Res 8), commercial blocks (Res 9), and immediate parcel adjacencies (Res 10). |
| **ADR-010** | Spatial Grid Equi-Join | Implement spatial proximity candidate generation via metric grid cell binning ($200\text{m} \times 200\text{m}$) and 9-neighbor offset equi-joins in DuckDB. | **Approved** | Reduces spatial proximity pair search from 63.2s quadratic bounding-box scan down to 0.09s hash equi-join, processing 5.49 million candidate pairs in under 1 second. |
| **ADR-011** | Indic Unicode Normalization | Implement Unicode category filtering (`unicodedata.category` matching `L*`, `M*`, `N*`) rather than ASCII/alphanumeric regex `\w`. | **Approved** | Preserves Indic vowel matras (Mn/Mc), halant/virama (0x0CCD), and numerals without transliteration or character mangling. |
