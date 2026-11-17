# Project State: India-Specific POI Conflation

**Document Purpose:** Persistent state and decision log tracking repository progress, environment baselines, technical decisions, and planned milestones.

---

## 1. Current Milestone

- **Milestone:** Milestone 6 — Benchmark Integrity, Annotation Pilot & Blocking-Loss Verification
- **Status:** **Milestone 6 Complete** (Mutually Exclusive Stratified Partition, 50-Pair Pilot Batch, Scientific Diagnostic Semantics, Quality-Control Evaluator, Category Pruning Audit Sample, and v1.1.0 Manifest Achieved)
- **Selected Target City:** **Bengaluru (Bruhat Bengaluru Mahanagara Palike — BBMP)**
  - *OSM Relation:* `7902476` (`admin_level=7`)
  - *Bounding Box:* `[77.4598797, 12.8334905, 77.7840639, 13.1426196]`
  - *BBMP Polygon Area:* **717.21 km²** (EPSG:32643 UTM 43N) / **716.37 km²** (WGS84 Spheroid)
  - *Total Canonical Records:* **246,856** (197,820 Overture + 49,036 OSM)
  - *Candidate Pairs Universe:* **605,428 pairs** (`candidate_pairs_union.parquet`, 42.02 MB)
  - *Mutually Exclusive Stratified Partition:* 10 non-overlapping diagnostic strata summing to 605,428 pairs
  - *Main Benchmark Queue:* **500 pairs** (50 pairs per stratum, `annotation_queue.csv`)
  - *Annotation Pilot Batch:* **50 pairs** (5 pairs per stratum, `pilot_batch_50.csv`)
  - *Sampling Seed:* `42` (deterministic mutually exclusive pseudo-random sampling)
  - *Missed-Match Diagnostic Audit:* **120 unrepresented/weak OSM records** (`missed_match_audit.csv`, 47 `NO_COUNTERPART_FOUND_IN_SEARCH`, 24 `POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING`, 49 `INSUFFICIENT_EVIDENCE`)
  - *Category Pruning Audit:* **100-pair review sample** across 11 incompatible rules (`reports/category_pruned_sample.csv`)
  - *Benchmark Manifest Version:* `1.1.0` (Lifecycle: `QUEUE_GENERATED`, `is_frozen = false`)
  - *Test Suite Coverage:* **45 passing automated tests**

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

### Completed Tasks (Milestones 1, 2, 3, 4, 5, and 6)
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
- [x] **Milestone 4 Implementation:** Implemented multi-strategy candidate generation engine (`src/poi_conflation/blocking/`):
  - Spatial proximity grid blocking ($\le 50$m via UTM Zone 43N metric grid bins).
  - Exact normalized name blocking (excluding generic national banking chains).
  - Distinctive token containment blocking ($\le 100$m, stripping Indian urban stopwords).
  - Multilingual Kannada-to-Latin transliteration via `indic-transliteration` Sanscript and Indian English phonetic normalization.
- [x] Implemented 4-tier Category Compatibility Matrix (`CategoryCompatibilityClassifier`), pruning 23,155 strictly incompatible pairs while retaining potential adjacencies.
- [x] Generated deterministic candidate union dataset (`data/processed/candidate_pairs/candidate_pairs_union.parquet`, 605,428 pairs, 42.02 MB) with reduction ratio of **99.99376%**.
- [x] Produced stratified review sample (`reports/candidate_review_sample.csv`, 300 pairs across 6 strata) and machine-readable comparison artifacts (`reports/blocking_strategy_comparison.json`, `reports/candidate_generation_summary.json`).
- [x] Expanded test suite with 7 dedicated candidate blocking tests (33 total passing tests).
- [x] Authored comprehensive blocking documentation (`docs/candidate_generation.md`, `docs/blocking_strategy_evaluation.md`, `docs/multilingual_blocking.md`).
- [x] **Milestone 5 Implementation:** Designed and established human-labelled ground truth benchmark framework (`src/poi_conflation/benchmark/`):
  - Formulated formal annotation schema with 4 label classes (`MATCH`, `NON_MATCH`, `UNCERTAIN`, `NEEDS_ADJUDICATION`), 3 confidence levels, and 10 structured evidence categories.
  - Built reproducible stratified sampling pipeline (`BenchmarkSampler`) generating a balanced 500-pair review queue across 10 difficulty strata (`data/processed/benchmark/annotation_queue.csv`).
  - Implemented local terminal-based review CLI (`scripts/annotate.py`) and workflow engine with atomic persistence and resume capabilities.
  - Implemented quality control and inter-annotator agreement engine (`AgreementEvaluator`) calculating observed agreement, expected agreement, Cohen's Kappa ($\kappa$), and automated conflict routing to `adjudication_queue.csv`.
  - Conducted independent missed-match diagnostic audit (`MissedMatchAuditor`) across 120 unrepresented/weak OSM records, identifying that 39.2% of unrepresented records are truly absent from Overture, 20.0% represent spatial displacement beyond 50m, and 40.8% lack names.
  - Created versioned benchmark manifest v1.0.0 (`benchmark_metadata.json`).
  - Added 7 dedicated unit and integration tests (40 total passing tests).
  - Authored comprehensive documentation (`docs/ground_truth_benchmark.md`, `docs/annotation_workflow.md`, `docs/missed_match_audit.md`).

- [x] **Milestone 6 Implementation:** Strengthened benchmark methodological integrity, sampling partition, and annotation pilot:
  - Eliminated stratum overlap by formulating an exhaustive, mutually exclusive 10-strata partition over the 605,428 candidate universe with exact inclusion probabilities ($\pi_k = n_k / N_k$).
  - Prepared and extracted a 50-pair pilot review batch (`data/processed/benchmark/pilot_batch_50.csv`, exactly 5 pairs per stratum).
  - Enhanced annotation workflow CLI (`scripts/annotate.py`) with `--pilot` mode, resume capability, and atomic progress tracking.
  - Corrected missed-match audit terminology and status semantics (`NO_COUNTERPART_FOUND_IN_SEARCH`, `POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING`, `INSUFFICIENT_EVIDENCE`), refraining from claiming global recall or unverified matches.
  - Implemented category pruning audit engine (`CategoryPruneAuditor`) reconstructing 23,119 pruned pairs and exporting a 100-pair review sample across 11 incompatible rules (`reports/category_pruned_sample.csv`).
  - Formalized benchmark lifecycle state machine (`QUEUE_GENERATED`, `ANNOTATION_IN_PROGRESS`, `ANNOTATION_COMPLETED`, `ADJUDICATION_PENDING`, `ADJUDICATED`, `BENCHMARK_FROZEN`) and updated manifest to v1.1.0 (`is_frozen = false`).
  - Added inter-annotator quality control safeguards, second-reviewer assignment workflow, and deduplication of repeated submissions.
  - Expanded test suite to 45 passing automated tests (12 dedicated benchmark/audit/QC tests).
  - Authored comprehensive documentation (`docs/benchmark_sampling_methodology.md`, `docs/annotation_pilot.md`, `docs/benchmark_lifecycle.md`).

### Pending Tasks (Milestone 7 Roadmap)
- [ ] Milestone 7: Human Annotation Pilot Execution, Inter-Annotator Agreement, and Consensus Adjudication.
- [ ] Milestone 8: Pairwise Feature Engineering & Supervised Classification (Jaro-Winkler, Levenshtein, displacement vectors, category similarity matrix).
- [ ] Milestone 9: Conflation Graph & Cluster-Based Canonical Resolution.

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
| **ADR-012** | Multi-Strategy Candidate Generation | Union orthogonal blocking strategies (spatial $\le 50$m, exact name, distinctive token containment $\le 100$m, and multilingual transliteration) with full provenance tracking. | **Approved** | Recovers geographically displaced POIs (+137 OSM records over spatial alone) while maintaining a 99.99376% reduction ratio. |
| **ADR-013** | Category Compatibility Matrix | Enforce a 4-tier category compatibility matrix over the 10 canonical categories, pruning strictly incompatible cross-domain pairs (e.g. Healthcare vs Sustenance). | **Approved** | Eliminates 23,155 false-positive candidate pairs without discarding plausible adjacencies (e.g. Retail with Sustenance). |
| **ADR-014** | Kannada Transliteration & Phonetic Normalization | Transliterate Kannada script via `indic-transliteration` Sanscript (ISO 15919) and apply Indian English phonetic rules (`udapi` $\rightarrow$ `udupi`, `shree` $\rightarrow$ `sri`, `bhavana` $\rightarrow$ `bhavan`). | **Approved** | Bridges the linguistic divide between vernacular OSM mapping (12.69% Kannada) and English Overture data (0.20% Kannada) while maintaining source immutability. |
| **ADR-015** | Stratified Benchmark Sampling | Extract candidate review queues using balanced stratification (50 pairs per stratum across 10 strata) with deterministic random seed (`seed=42`). | **Approved** | Prevents high-density commercial clusters or trivial exact matches from dominating ground truth while preserving rare transliteration and distance variants. |
| **ADR-016** | Four-Class Ground Truth Schema & Agreement | Support `MATCH`, `NON_MATCH`, `UNCERTAIN`, and `NEEDS_ADJUDICATION` with Cohen's Kappa reliability and conflict routing to `adjudication_queue.csv`. | **Approved** | Prevents forcing ambiguous pairs into binary labels and provides mathematically rigorous inter-annotator agreement metrics. |
| **ADR-017** | Missed-Match Diagnostic Audit | Audit unrepresented OSM entities via wide-radius (1.5 km), category-unconstrained independent search to isolate true source absence from blocking loss. | **Approved** | Proves that 39.2% of zero-candidate OSM POIs do not exist in Overture, preventing false attribution of source coverage gaps to pipeline failure. |
| **ADR-018** | Mutually Exclusive Stratification | Partition the 605,428 candidate universe into an exhaustive, mutually exclusive 10-strata hierarchy to compute exact inclusion probabilities ($n_k / N_k$). | **Approved** | Resolves the multi-attribute stratum overlap problem, ensuring rigorous Horvitz-Thompson weighting and reproducible sampling. |
| **ADR-019** | Benchmark Lifecycle State Machine | Enforce formal lifecycle stages (`QUEUE_GENERATED`, `ANNOTATION_IN_PROGRESS`, `ANNOTATION_COMPLETED`, `ADJUDICATION_PENDING`, `ADJUDICATED`, `BENCHMARK_FROZEN`). | **Approved** | Prevents declaring ground truth benchmarks frozen or completed before human annotations and consensus adjudication actually occur. |
| **ADR-020** | Category Pruning Auditability | Reconstruct and sample discarded category-incompatible candidate pairs (`category_pruned_sample.csv`) across all 11 disjoint rules for ongoing audit. | **Approved** | Replaces unverified absolute claims with empirical audit evidence, ensuring transparent tracking of cross-domain edge cases. |
