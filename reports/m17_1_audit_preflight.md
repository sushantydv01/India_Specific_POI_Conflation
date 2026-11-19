# Milestone 17.1 — Audit Preflight Report

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** 2026-11-19  
**Auditor:** Sushant Yadav  
**Audit Target:** Milestone 17 Production Conflation Pipeline & Incremental Correctness  

---

## 1. Git Repository & Working Tree State

- **Branch:** `main` (tracked to `origin/main`, clean working tree)
- **HEAD Commit:** [`ad42433`](https://github.com/sushantydv01/India_Specific_POI_Conflation/commit/ad42433) (`feat: implement production conflation pipeline, delta ingestion and continuous validation`)
- **Parent Commit:** [`c4ef986`](https://github.com/sushantydv01/India_Specific_POI_Conflation/commit/c4ef986) (`audit: validate canonical POI conflation integrity`)
- **Prior Baseline Commits:**
  - `3a3e7a8` — Milestone 16 (Graph Conflation Integration & Canonical POI Export)
  - `9749174` — Milestone 15.1 (Independent Evaluation Audit & Model Validation)
  - `960ca65` — Milestone 15 (Supervised POI Matcher & Streaming Inference)

---

## 2. In-Scope Files & Architectural Modules

The audit covers the following modules, scripts, and reports:

### A. Pipeline Orchestration & CLI
- `src/poi_conflation/pipeline/config.py`: `PipelineConfig`, `PipelineMode` defaults.
- `src/poi_conflation/pipeline/orchestrator.py`: `ProductionPipelineOrchestrator`, stage management, staging directory creation, and atomic promotion.
- `src/poi_conflation/pipeline/__main__.py`: CLI entry points for `run` and `validate`.

### B. Delta Ingestion & Fingerprinting
- `src/poi_conflation/delta/snapshot.py`: `SourceSnapshotManifest`, `compute_record_content_hash`.
- `src/poi_conflation/delta/detector.py`: `SourceDeltaDetector`, `SourceRecordDelta`, `SnapshotDeltaSummary`.

### C. Graph Conflation & Safeguards
- `src/poi_conflation/graph/safeguards.py`: `ConflationSafeguardValidator`, `_detect_shared_honorific_disjoint_brand`, `_check_brand_sharing`, `_detect_parent_child`.
- `src/poi_conflation/graph/schema.py`: `SafeguardType.SHARED_HONORIFIC_DISJOINT_BRAND`, `EdgeDisposition`, `POIRelationshipType`.
- `src/poi_conflation/graph/supervised_resolver.py`: `SupervisedCanonicalResolver`, star dominance, UUIDv5 canonical identity.
- `src/poi_conflation/graph/bipartite_graph.py`: Bipartite graph data structures and connected component extraction.

### D. Persistent Lineage Ledger
- `src/poi_conflation/lineage/ledger.py`: `LineageLedger`, `LineageEvent`, `LineageEventType`.

### E. Continuous Validation
- `src/poi_conflation/validation/conflation_validator.py`: `ContinuousConflationValidator`, `ValidationReport`.
- `configs/bbmp_boundary.geojson`: Ground-truth municipal boundary polygon (Relation ID 7902476).

### F. Reports & Deliverables
- `reports/m17_architecture_assessment.md`
- `reports/m17_implementation_report.md`
- `reports/m17_validation_report.md`
- `reports/m17_run_summary.json`
- `PROJECT_STATE.md` (ADR-035)

---

## 3. Physical State of Production Exports on Disk

Inspection of `data/processed/canonical/`:
| File Name | File Size | Modification Timestamp | Record Count |
| :--- | :---: | :---: | :---: |
| `canonical_pois.parquet` | 24,498,781 bytes | 2026-11-19 15:29:43 | 238,083 entities |
| `canonical_pois.geojson` | 89,891,681 bytes | 2026-11-19 15:29:43 | 238,083 features |
| `conflation_edges.parquet` | 32,627,185 bytes | 2026-11-19 15:29:43 | 605,428 edges |
| `poi_relationships.parquet` | 140,388 bytes | 2026-11-19 15:29:43 | 985 relationships |
| `unresolved_pairs.parquet` | 224,726 bytes | 2026-11-19 15:29:43 | 2,842 review pairs |

**Key Preflight Observation:** The file timestamps in `data/processed/canonical/` date to `15:29:43` (Milestone 16 creation), whereas M17 was committed later (`ad42433`). This confirms that the production exports currently stored in `data/processed/canonical/` do not yet embody the runtime execution of `SHARED_HONORIFIC_DISJOINT_BRAND`.

---

## 4. Test Suite Baseline

- **Automated Test Suite:** 204 passed in 5.07 seconds.
- **Coverage:** Spans boundary ingestion, candidate blocking, canonical schemas, H3 indexing, baseline matching, human adjudication, supervised LightGBM modeling, TreeSHAP explainability, bipartite graph resolution, M16.1 audit regressions, and M17 production pipeline scenarios.

Preflight inspection is complete. Proceeding to Phase 1: Shared-Honorific Safeguard Audit.
