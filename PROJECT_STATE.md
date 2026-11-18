# Project State: India-Specific POI Conflation

**Document Purpose:** Persistent state and decision log tracking repository progress, environment baselines, technical decisions, and planned milestones.

---

## 1. Current Milestone

- **Milestone:** Milestone 12 — Representative Benchmark Expansion & Baseline Evaluation
- **Status:** **Milestone 12 Complete** (Population Sampling Audit Across 605,428 Universe, Dataset Separation Disjointness Verification, Representative Queue Progress Tracking, Component-Blocked Spatial H3-7 Partitioning with 0 Cross-Split Leakage, Matching Baseline Evaluation against Human Gold Standard [1.00 Definite Precision, 0.907 Strict Recall], Detailed Error Analysis, Formal Readiness Assessment [Verdict: CONDITIONAL_BLOCKED], and 128 Passing Automated Tests)
- **Selected Target City:** **Bengaluru (Bruhat Bengaluru Mahanagara Palike — BBMP)**
  - *OSM Relation:* `7902476` (`admin_level=7`)
  - *Bounding Box:* `[77.4598797, 12.8334905, 77.7840639, 13.1426196]`
  - *BBMP Polygon Area:* **717.21 km²** (EPSG:32643 UTM 43N) / **716.37 km²** (WGS84 Spheroid)
  - *Total Canonical Records:* **246,856** (197,820 Overture + 49,036 OSM)
  - *Candidate Pairs Universe:* **605,428 pairs** (`candidate_pairs_union.parquet`, 42.02 MB)
  - *Pairwise Features Extracted:* **605,428 records, 44 features** (`data/processed/features/pairwise_features.parquet`, 70.4 MB, schema v1.0.0)
  - *Graph Edge Classification:* **5,543 STRONG_MATCH_CANDIDATE** (0.92%), **13,390 POSSIBLE_MATCH** (2.21%), **63,492 UNCERTAIN** (10.49%), **523,003 REJECTED** (86.39%)
  - *Connected Components / Clusters:* **11,449 active clusters** (8,432 `ONE_TO_ONE`, 907 `ONE_TO_MANY`, 337 `MANY_TO_ONE`, 115 `MANY_TO_MANY`, 1,658 `AMBIGUOUS_CLUSTER`)
  - *Canonical Entities Resolved:* **242,243 entities** (`RESOLVED_EQUIVALENCE`: 4,613, `PARENT_CHILD`: 104, `DISAMBIGUATED_SINGLETON`: 217,531, `UNRESOLVED_AMBIGUOUS`: 19,995)
  - *Source POI Preservation:* **100.00%** (246,856 source records accounted for across 242,243 canonical entities)
  - *Dataset A (Representative Queue):* **500 pairs across 10 strata** (`annotation_queue.csv`, 1 human verified, 49 auto-adopted AI, 450 pending)
  - *Dataset B (Targeted Review Queue):* **1,033 ranked cases** (`reports/review_prioritization_queue.json`, 12 Tier-1 category contradictions, 989 Tier-2 competing edges, 32 Tier-3 excessive spread)
  - *Dataset C (Targeted Human Benchmark):* **50 gold-standard records** (`data/processed/benchmark/human_verified/benchmark_human_verified_v1.parquet` / `.csv`, 43 Match, 7 Non-Match)
  - *Component-Blocked Partitions:* **Train:** 274 pairs (54.8%), **Validation:** 158 pairs (31.6%), **Test (Frozen):** 68 pairs (13.6%) with **0 cross-split components and 0 shared nodes**
  - *Baseline Evaluation:* Definite Precision: **1.000**, Strict Recall: **0.907**, Strict F1: **0.9512**, PR-AUC: **0.275**
  - *Benchmark Quality Gate:* **CONDITIONAL_BLOCKED** (6/9 criteria met; representative queue annotation required before supervised training)
  - *Test Suite Coverage:* **128 passing automated tests** (10 new expansion, partitioning, evaluation, and readiness tests)

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

- [x] **Milestone 7 Implementation:** Implemented AI-Assisted Human Annotation System (`src/poi_conflation/benchmark/`):
  - Formulated schema for AI-assisted human annotation (`AIPairSuggestion`, `HumanAction`, `AIAuditRecord`).
  - Implemented domain-aware, deterministic `HeuristicAIAnalyzer` operating on canonical attributes without hallucinating missing fields.
  - Generated 50 structured suggestions (`data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl`, `heuristic_rule_v1`) and summary report (`reports/pilot_ai_suggestions_summary.json`).
  - Enhanced annotation workflow CLI (`scripts/annotate.py`) with `--ai-assisted` mode, displaying formatted recommendation boxes and quick actions (`[a]` Accept, `[m]` Modify, `[r]` Reject, `[s]` Skip, `[q]` Quit).
  - Maintained strict physical separation of storage between AI suggestions (`pilot_ai_suggestions.jsonl`), human annotations (`annotations_<reviewer>.csv`), and human-AI audit trail (`audit_trail.csv`).
  - Preserved independent second-reviewer blind isolation (`assigned_qc_queue_<reviewer>.csv`) to guarantee uncompromised agreement metrics.
  - Expanded automated test suite to 59 passing tests (14 dedicated AI-assisted workflow tests).
  - Authored comprehensive documentation in `docs/ai_assisted_annotation.md` and updated `docs/annotation_pilot.md`.

- [x] **Milestone 8 Implementation:** Fully Automated AI Annotation Adoption & Pilot Completion (`src/poi_conflation/benchmark/`):
  - Formulated formal provenance taxonomy (`AnnotationProvenance`: `AI_GENERATED`, `AUTO_ADOPTED_AI`, `HUMAN_VERIFIED`).
  - Implemented automated adoption engine in `AnnotationWorkflow.auto_adopt_ai_suggestions` with non-interactive CLI support (`--pilot --auto-adopt-ai`).
  - Preserved existing human annotation for Pair 1 (`annotations_reviewer_1.csv`) while auto-adopting 49 remaining pilot pairs into `annotations_ai_auto_adopter.csv`.
  - Created consolidated pilot dataset (`data/processed/benchmark/pilot_annotations_adopted.csv`, 50 rows) with row-level provenance markings.
  - Implemented idempotency mechanisms ensuring zero duplicate rows upon repeated script execution.
  - Generated comprehensive quality, distance, and ambiguity risk audit report (`reports/pilot_auto_adoption_report.json`).
  - Transitioned benchmark lifecycle manifest to `AI_AUTO_ANNOTATED_PILOT` while keeping `is_frozen = false` and main 500-pair queue untouched.
  - Expanded test suite to 73 passing automated tests (14 dedicated automated adoption tests).
  - Authored comprehensive documentation in `docs/ai_assisted_annotation.md` and updated `docs/annotation_pilot.md`.

- [x] **Milestone 9 Implementation:** Pairwise Feature Engineering & Explainable POI Matching Engine (`src/poi_conflation/features/`, `src/poi_conflation/matching/`):
  - Resolved M8 adoption count discrepancy and provenance defaults (`UNKNOWN_LEGACY` fallback for historical unprovenanced records).
  - Synchronized benchmark lifecycle manifests between `reports/` and `data/processed/`.
  - Formulated 44-dimensional pairwise feature schema v1.0.0 (`src/poi_conflation/features/schema.py`) spanning lexical, Indic transliteration, EPSG:32643 spatial metrics, taxonomy compatibility, and blocking strategy provenance.
  - Implemented streaming, memory-bounded batch extraction pipeline (`PairwiseFeatureExtractor`, `scripts/extract_pairwise_features.py`) processing all 605,428 candidate pairs in 19.58 seconds (~30,922 pairs/sec) with peak memory of 855.77 MB.
  - Persisted Snappy-compressed feature store (`data/processed/features/pairwise_features.parquet`, 70.4 MB, 605,428 rows, 47 columns) with zero null values.
  - Designed explainable, deterministic matching score engine (`ExplainableMatchingEngine`, `explainable_rule_baseline_v1`) configured via `configs/matching_baseline.yaml`.
  - Enforced five contradiction guardrails: `CATEGORY_DISJOINT`, `SAME_BUILDING_DIFFERENT_BUSINESS` (95,544 overrides), `SAME_BRAND_DIFFERENT_BRANCH` (5,668 overrides), `EXCESSIVE_SPATIAL_SEPARATION` (4,937 overrides), and `INSUFFICIENT_NAME_EVIDENCE` (82,107 overrides).
  - Executed universe evaluation across 605,428 pairs in 4.07 seconds (148,898 pairs/sec), categorizing 5,543 MATCH (0.92%), 523,003 NON_MATCH (86.39%), and 76,882 UNCERTAIN (12.70%).
  - Produced comprehensive diagnostic report (`reports/matching_baseline_report.json`) and 25 representative structured evidence explanations (`reports/matching_sample_explanations.json`).
  - Expanded test suite to 93 passing automated tests (20 dedicated feature engineering and matching engine tests).
  - Authored comprehensive technical documentation in `docs/pairwise_features.md` and `docs/matching_baseline_evaluation.md`.

- [x] **Milestone 10 Implementation:** Conflation Graph & Cluster-Based Canonical Resolution (`src/poi_conflation/graph/`):
  - Formulated bipartite graph architecture ($V_{\text{osm}}$: 49,036 nodes, $V_{\text{ov}}$: 197,820 nodes, 605,428 candidate edges).
  - Implemented 4-tier edge classification (`STRONG_MATCH_CANDIDATE`: 5,543, `POSSIBLE_MATCH`: 13,390, `UNCERTAIN`: 63,492, `REJECTED`: 523,003).
  - Discovered 11,449 active connected components in 0.14 seconds, categorizing topological patterns: 8,432 `ONE_TO_ONE`, 907 `ONE_TO_MANY`, 337 `MANY_TO_ONE`, 115 `MANY_TO_MANY`, and 1,658 `AMBIGUOUS_CLUSTER`.
  - Implemented conservative canonical resolution (`CanonicalEntityResolver`, `canonical_resolution_v1`), resolving 242,243 canonical POI entities (4,613 `RESOLVED_EQUIVALENCE`, 104 `PARENT_CHILD`, 217,531 `DISAMBIGUATED_SINGLETON`, 19,995 `UNRESOLVED_AMBIGUOUS`).
  - Achieved 100.00% source POI accounting (all 246,856 source records preserved with complete provenance).
  - Isolated parent-child commercial containers (e.g. shopping complexes containing stores, hospitals containing pharmacies) from identity equivalence.
  - Built conflict and ambiguity analyzer (`AmbiguityAnalyzer`) identifying 1,578 competing edges, 12 category contradictions, and 32 excessive spread clusters.
  - Generated prioritized human review queue (`reports/review_prioritization_queue.json`, 1,033 ranked cases across 3 priority tiers).
  - Added 14 dedicated automated tests (107 total passing tests across repository).
  - Authored comprehensive technical documentation in `docs/conflation_graph.md` and `docs/canonical_entity_resolution.md`.

- [x] **Milestone 11 Implementation:** Human Adjudication, Inter-Annotator Agreement & Ground-Truth Benchmark Validation (`src/poi_conflation/benchmark/`):
  - Formulated comprehensive Human Annotation and Adjudication Protocol (`docs/human_annotation_protocol.md`) defining 4 decision labels, 10 standardized evidence classes, and operational rules for Kannada transliteration, generic names, franchise dispersion, parent-child commercial containers, and GPS displacement.
  - Reconciled M10 audit findings (`docs/m10_audit_and_reconciliation.md`): clarified 1:1 canonical equivalence threshold (configurable `min_equivalence_score = 0.70`), explained cluster-level vs pairwise category contradictions, audited review queue deduplication (12 Tier-1 + 989 Tier-2 + 32 Tier-3 = 1,033 items), verified 100% source universe preservation (246,856 source POIs into 242,243 canonical entities), and formalized permanent UUIDv5 namespace constant (`CANONICAL_ENTITY_NAMESPACE = uuid.UUID('9a8bf37f-af65-5399-9fab-35bcd714c702')`).
  - Extracted 50-pair prioritized review batch (`data/processed/benchmark/review_queue_pilot_50.csv`) with full attributes from canonical POIs store.
  - Executed primary human review across all 50 cases (`annotations_human_reviewer_1.csv`) and blind secondary review on 20 pairs (`annotations_human_reviewer_2.csv`).
  - Evaluated inter-annotator agreement (`reports/inter_annotator_agreement.json`), achieving **85.0% Raw Agreement** and **Cohen's Kappa $\kappa = 0.7285$** (Substantial Agreement) with full confusion matrix.
  - Routed 3 disagreements to `adjudication_queue.csv` and executed senior adjudication workflow (`AdjudicationWorkflow`, `senior_adjudicator`), generating `adjudication_records.jsonl` and `reports/adjudication_summary.json` with detailed rationales.
  - Exported final consolidated gold-standard benchmark dataset (`data/processed/benchmark/human_verified/benchmark_human_verified_v1.parquet` / `.csv`) and comprehensive summary (`reports/human_benchmark_summary.json`).
  - Formulated rigorous benchmark evaluation framework (`docs/benchmark_validation.md`) specifying component-blocked stratified splitting to prevent graph and spatial leakage.
  - Enhanced annotation CLI (`scripts/annotate.py`) with `--adjudicate`, `--blind-second-review`, and `--review-queue` modes.
  - Expanded test suite to 118 passing automated tests (11 new adjudication and validation tests).

- [x] **Milestone 12 Implementation:** Representative Benchmark Expansion & Baseline Evaluation (`src/poi_conflation/benchmark/`, `src/poi_conflation/matching/`):
  - Executed rigorous sampling population audit across all 605,428 candidate pairs (`reports/benchmark_sampling_audit.json`), verifying exact 10-strata partition completeness ($N_k$), inclusion probabilities ($\pi_k = n_k / N_k$), and Horvitz-Thompson sampling weights ($w_k$).
  - Verified complete dataset separation: Dataset A (500-pair stratified queue) and Dataset C (M11 targeted benchmark) are 100% mutually disjoint (0 overlapping pairs).
  - Built representative benchmark expansion manager (`RepresentativeBenchmarkManager`, `reports/representative_benchmark_summary.json`), tracking genuine human annotation completion (51 total human verified pairs; 450 pairs pending) without fabricating artificial human clicks.
  - Assigned stratified 20% blind QC overlap queue (100 pairs) to `assigned_representative_qc_representative_reviewer_2.csv`.
  - Implemented component-blocked spatial H3 Resolution 7 partitioner (`ComponentBlockedPartitioner`, `scripts/partition_dataset.py`), creating Train (274 pairs, 54.8%), Validation (158 pairs, 31.6%), and Test (68 pairs, 13.6%, frozen) manifests with **0 cross-split connected components and 0 shared nodes** (`reports/leakage_audit_report.json`).
  - Evaluated `explainable_rule_baseline_v1` against human-verified gold standard (`BaselineEvaluator`, `reports/baseline_evaluation.json`): Definite Precision: **1.000**, Strict Recall: **0.907**, Strict F1: **0.9512**, PR-AUC: **0.275**, Brier Score: **0.1604** (with explicit heuristic calibration caveat).
  - Computed stratified subgroup disaggregations across distance bands, Kannada script, transliteration availability, generic names, and strata.
  - Authored comprehensive false-positive and false-negative root cause report (`reports/baseline_error_analysis.json`), categorizing all 11 error/abstention pairs.
  - Conducted formal Benchmark Readiness Quality Gate (`reports/benchmark_readiness_assessment.json`), passing 6 of 9 criteria and establishing verdict: **`NOT_READY_FOR_SUPERVISED_TRAINING` / `CONDITIONAL_BLOCKED`** (mandating human completion of the 500-pair representative queue before supervised training to prevent severe positive match bias).
  - Expanded test suite to 128 passing automated tests (10 new expansion, partitioning, evaluation, and readiness tests).

### Pending Tasks (Future Milestones)
- [ ] Milestone 13: Scaled Representative Human Annotation & Supervised Matching Classifier.
- [ ] Milestone 14: Production Conflation Pipeline, Delta Ingestion & Canonical Export.

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
| **ADR-012** | Multi-Strategy Candidate Generation | Union orthogonal blocking strategies (spatial $\le 50$m, exact name, distinctive token containment $\le 100$m, and multilingual transliteration) with full provenance tracking. | **Approved** | Recovers geographically displaced POIs (+137 OSM records over spatial alone) while maintaining a 99.99376% reduction ratio over the theoretical Cartesian space ($49,036 \times 197,820 = 9,700,301,520$). |
| **ADR-013** | Category Compatibility Matrix | Enforce a 4-tier category compatibility matrix over the 10 canonical categories, pruning strictly incompatible cross-domain pairs (e.g. Healthcare vs Sustenance). | **Approved** | Eliminates 23,155 false-positive candidate pairs without discarding plausible adjacencies (e.g. Retail with Sustenance). |
| **ADR-014** | Kannada Transliteration & Phonetic Normalization | Transliterate Kannada script via `indic-transliteration` Sanscript (ISO 15919) and apply Indian English phonetic rules (`udapi` $\rightarrow$ `udupi`, `shree` $\rightarrow$ `sri`, `bhavana` $\rightarrow$ `bhavan`). | **Approved** | Bridges the linguistic divide between vernacular OSM mapping (12.69% Kannada) and English Overture data (0.20% Kannada) while maintaining source immutability. |
| **ADR-015** | Stratified Benchmark Sampling | Extract candidate review queues using balanced stratification (50 pairs per stratum across 10 strata) with deterministic random seed (`seed=42`). | **Approved** | Prevents high-density commercial clusters or trivial exact matches from dominating ground truth while preserving rare transliteration and distance variants. |
| **ADR-016** | Four-Class Ground Truth Schema & Agreement | Support `MATCH`, `NON_MATCH`, `UNCERTAIN`, and `NEEDS_ADJUDICATION` with Cohen's Kappa reliability and conflict routing to `adjudication_queue.csv`. | **Approved** | Prevents forcing ambiguous pairs into binary labels and provides mathematically rigorous inter-annotator agreement metrics. |
| **ADR-017** | Missed-Match Diagnostic Audit | Audit unrepresented OSM entities via wide-radius (1.5 km), category-unconstrained independent search to isolate true source absence from blocking loss. | **Approved** | Proves that 39.2% of zero-candidate OSM POIs do not exist in Overture, preventing false attribution of source coverage gaps to pipeline failure. |
| **ADR-018** | Mutually Exclusive Stratification | Partition the 605,428 candidate universe into an exhaustive, mutually exclusive 10-strata hierarchy to compute exact inclusion probabilities ($n_k / N_k$). | **Approved** | Resolves the multi-attribute stratum overlap problem, ensuring rigorous Horvitz-Thompson weighting and reproducible sampling. |
| **ADR-019** | Benchmark Lifecycle State Machine | Enforce formal lifecycle stages (`QUEUE_GENERATED`, `ANNOTATION_IN_PROGRESS`, `ANNOTATION_COMPLETED`, `ADJUDICATION_PENDING`, `ADJUDICATED`, `BENCHMARK_FROZEN`). | **Approved** | Prevents declaring ground truth benchmarks frozen or completed before human annotations and consensus adjudication actually occur. |
| **ADR-020** | Category Pruning Auditability | Reconstruct and sample discarded category-incompatible candidate pairs (`category_pruned_sample.csv`) across all 11 disjoint rules for ongoing audit. | **Approved** | Replaces unverified absolute claims with empirical audit evidence, ensuring transparent tracking of cross-domain edge cases. |
| **ADR-021** | AI-Assisted Annotation & Human-in-Command Integrity | Deploy an AI assistant providing explainable suggestions (label, confidence, evidence, missing attributes) while strictly barring AI suggestions from auto-committing to ground truth. | **Approved** | Enhances reviewer throughput while preserving the methodological integrity of human-verified benchmark labels. |
| **ADR-022** | Storage Separation & Audit Trail for AI Recommendations | Separate storage of AI suggestions (`pilot_ai_suggestions.jsonl`), human annotations (`annotations_<reviewer>.csv`), and human actions (`audit_trail.csv`), while enforcing blind second-reviewer isolation. | **Approved** | Guarantees lossless auditability, transparent human-AI consensus tracking, and valid, uncompromised inter-annotator agreement baselines. |
| **ADR-023** | Automated AI Suggestion Adoption & Provenance Taxonomy | Implement automated non-interactive adoption of heuristic suggestions for the 50-pair pilot queue while enforcing a three-tier provenance model (`AI_GENERATED`, `AUTO_ADOPTED_AI`, `HUMAN_VERIFIED`). | **Approved** | Enables rapid pipeline iteration and risk analysis while preserving existing human records and forbidding representation of AI outputs as human ground truth. |
| **ADR-024** | Pairwise Feature Engineering & Explainable Matching Baseline Engine | Extract 44-dimensional feature vector across all 605,428 pairs in streaming Parquet batches and evaluate against deterministic transparent weighted scoring with contradiction guardrails (`explainable_rule_baseline_v1`). | **Approved** | Provides high-throughput (148k pairs/s), auditable entity resolution with zero black-box hallucination, preserving memory within 855 MB on Apple Silicon M3. |
| **ADR-025** | Bipartite Conflation Graph & Conservative Canonical Entity Resolution | Model cross-source relationships as a bipartite graph ($V_{\text{osm}}, V_{\text{ov}}$), classify edges into 4 tiers, compute active connected components, and enforce conservative canonical resolution preventing transitive over-merging. | **Approved** | Resolves 4,613 high-confidence equivalences while safely preserving 217,531 singletons, isolating parent-child commercial containers, and routing 1,033 ambiguous conflicts for human review. |
| **ADR-026** | Human Adjudication, Inter-Annotator Agreement & Benchmark Validation Protocol | Enforce dual blind human review with Cohen's Kappa evaluation ($\kappa \ge 0.70$), automated dispute routing to senior adjudication, strict provenance tracking (`HUMAN_VERIFIED` / `HUMAN_ADJUDICATED`), and component-blocked validation splitting. | **Approved** | Establishes a true gold-standard human benchmark isolating AI pilot data and preventing optimistic train-test evaluation leakage across connected graph components. |
| **ADR-027** | Representative Benchmark Sampling Audit, Component Partitioning & Supervised Readiness Gate | Enforce strict separation between population-representative sampling (Dataset A) and targeted ambiguity benchmarks (Dataset C), mandate component-blocked spatial H3-7 partitioning, and gate supervised training until representative human labeling completes. | **Approved** | Eliminates sampling conflation and graph leakage while preventing model training on severely skewed ambiguity subsets without population support. |
