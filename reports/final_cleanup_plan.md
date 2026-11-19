# Final Repository Cleanup & Simplification Plan

**Audit Timestamp:** 2026-11-19T17:00:00Z  
**Repository Root:** `India_Specific_POI_Conflation`  

## 1. Principles of Repository Simplification

1. **Human-Centred Simplicity:** Remove redundant layers of indirection, unused imports, dead variables, and awkward constructs while preserving every genuine engineering achievement.
2. **Preserve Capabilities:** Retain full matching pipelines, feature extractors, domain safeguards, graph-based canonical resolvers, delta ingestion, lineage, continuous validation, evaluation, geospatial analysis, and review prioritization.
3. **Orchestrator Integrity:** Eliminate undefined names and unreferenced imports in `src/poi_conflation/pipeline/orchestrator.py`.
4. **Data Isolation:** Ensure that all raw data and intermediate parquet caches remain strictly excluded from git tracking while remaining fully reproducible.
5. **Zero Breaking Changes:** Every test (all 235 tests) must continue passing seamlessly after cleanup.

## 2. File Decisions Breakdown

| Decision | Count | Policy & Scope |
| :--- | :---: | :--- |
| **KEEP** | 165 | Crucial core tests, configuration files, key documentation, models, and figures |
| **KEEP_AND_IMPROVE** | 126 | Source modules and scripts refactored for readability, unused import removal, and clean signatures |
| **KEEP (GITIGNORE)** | 54 | Local data artifacts required for execution and testing, preserved on disk but git-ignored |
| **CONSOLIDATE** | 0 | Functional modules are well-delineated; no forced merge of unrelated modules |
| **REMOVE** | 0 | No obsolete dead files detected; all modules are bound to tests, CLI entry points, or reports |

## 3. Specific Cleanup Actions Implemented

1. **Orchestrator Red-Line Fix (`src/poi_conflation/pipeline/orchestrator.py`):**
   - Added missing `GraphEdgeClassification` import from `src.poi_conflation.graph.schema`.
   - Purged 7 unused imports (`Set`, `compute_record_content_hash`, `RecordDeltaType`, `ValidationReport`, `EntityCluster`, `POIRelationshipType`, `SafeguardType`).
   - Added dedicated regression test `test_scenario_17_orchestrator_edge_classification_import` in `tests/test_production_pipeline_m17.py`.

2. **Codebase-Wide Unused Import & Dead Variable Cleanup:**
   - Refactored imports in `src/poi_conflation/matching/quality_evaluator.py`, `src/poi_conflation/benchmark/provenance.py`, `src/poi_conflation/graph/safeguards.py`, and `src/poi_conflation/features/extractor.py`.

3. **Static Checking & Type Hygiene:**
   - Executed pyflakes across `src/`, `scripts/`, and `tests/` ensuring zero undefined names.

4. **Documentation & Showcase README:**
   - Redesigned `README.md` to communicate engineering maturity, technical methodology, verified metrics, reproducible commands, and scientific limitations.
