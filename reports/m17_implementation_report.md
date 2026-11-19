# Milestone 17 — Production Conflation Pipeline, Delta Ingestion & Continuous Validation Implementation Report

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** 2026-11-19  
**Author:** Sushant Yadav  
**Status:** **`M17_COMPLETE`**  

---

## 1. Executive Summary

Milestone 17 successfully establishes an automated, production-oriented conflation workflow for the India-Specific POI Conflation system. The project moves beyond one-off milestone scripts into a robust, configurable data engineering pipeline capable of running full rebuilds and incremental snapshot ingestion.

The implementation introduces:
1. **Unified Pipeline Orchestrator & CLI:** Controlled single-entry execution via `python -m src.poi_conflation.pipeline run --mode [full|incremental]` and `python -m src.poi_conflation.pipeline validate`.
2. **Deterministic Source Snapshot & Delta Engine:** SHA-256 normalized content hashing over conflation-relevant attributes, detecting `ADDED`, `MODIFIED`, `DELETED`, and `UNCHANGED` source records.
3. **Component-Aware Graph Resolution:** Safe handling of graph component merges and splits while guaranteeing 100% canonical ID stability for unaffected entities.
4. **Persistent Lineage Ledger:** Comprehensive historical audit tracking of entity lifecycle transitions (`ENTITY_CREATED`, `ENTITY_UPDATED`, `ENTITY_MERGED`, `ENTITY_SPLIT`, `ENTITY_RETIRED`, `ENTITY_UNCHANGED`).
5. **Continuous Validation Layer:** Automated post-execution integrity verification executing checks across source records, candidate edges, graph topology, canonical entities, non-equivalence relationships, and incremental consistency.
6. **Failure Isolation & Atomic Promotion:** Staged output directory structure with atomic promotion, guaranteeing that failed pipeline executions never corrupt active production outputs.
7. **Mitigation of Shared-Honorific False Equivalences:** Implementation of the `SHARED_HONORIFIC_DISJOINT_BRAND` safeguard intercepting candidate pairs with shared prefixes (*Sri*, *The*, *Dr.*) but disjoint brand cores.

---

## 2. Reused Architecture vs. New Modules

### Reused from Milestone 16 / 16.1:
- `src/poi_conflation/graph/schema.py`: Canonical data models, edge classifications, dispositions, relationship types, and cluster patterns.
- `src/poi_conflation/graph/bipartite_graph.py`: Bipartite graph data structures, edge indexing, and BFS connected-component discovery.
- `src/poi_conflation/graph/supervised_resolver.py`: Star dominance resolution ($\Delta s \ge 0.15$), canonical attribute selection, and UUIDv5 canonical ID generation.
- `src/poi_conflation/graph/safeguards.py`: Baseline domain safeguards (`ATM_VS_BANK_FACILITY_DISTINCTION`, `PARENT_CHILD_CONTAINER`, `SAME_BRAND_DIFFERENT_BRANCH`, `GENERIC_NAME_COLLISION`, `EXCESSIVE_SPATIAL_SEPARATION`).
- `src/poi_conflation/blocking/category.py`: 4-tier category compatibility matrix.
- `models/supervised_poi_matcher_v1.joblib`: Frozen LightGBM supervised matching model.

### New Modules Created in Milestone 17:
- `src/poi_conflation/pipeline/config.py`: Configuration models and parameter defaults (`PipelineConfig`, `PipelineMode`).
- `src/poi_conflation/pipeline/orchestrator.py`: End-to-end pipeline orchestrator managing stage lifecycles, atomic promotion, and manifests.
- `src/poi_conflation/pipeline/__main__.py`: Production CLI entry point supporting `run` and `validate` subcommands.
- `src/poi_conflation/delta/snapshot.py`: Source snapshot manifest generation and normalized attribute content fingerprinting.
- `src/poi_conflation/delta/detector.py`: Source delta detector classifying records into `ADDED`, `MODIFIED`, `DELETED`, and `UNCHANGED`.
- `src/poi_conflation/lineage/ledger.py`: Persistent entity lineage ledger and lifecycle transition tracking.
- `src/poi_conflation/validation/conflation_validator.py`: Automated continuous validation suite checking physical and semantic invariants.
- `tests/test_production_pipeline_m17.py`: Comprehensive test suite verifying all 16 required incremental and recovery scenarios.

---

## 3. Pipeline Stages & Execution Architecture

The production pipeline is structured into seven discrete, independently testable stages:

```
[1. Source Validation] 
         │ (Verify schema, row counts, accessibility)
         ▼
[2. Source Snapshot & Delta Detection]
         │ (Compute content hashes; detect ADDED / MODIFIED / DELETED)
         ▼
[3. Graph Construction & Safeguards]
         │ (Stream candidates, apply safeguards, extract relationships)
         ▼
[4. Canonical Resolution & Lineage]
         │ (Component-aware resolution, dominance checks, record lineage)
         ▼
[5. Staged Output Export]
         │ (Write Parquet, GeoJSON, relationships to temporary staging)
         ▼
[6. Continuous Validation Gate]
         │ (Verify nulls, bounds, accounting, ATM cross-merges, endpoints)
         ├── [FAILED] ──> Abort & Clean Staging (Production Untouched)
         └── [PASSED] ──> [7. Atomic Promotion] (Promote staging to production)
                                 │
                                 ▼
                     [Run Manifest Generation]
```

---

## 4. Delta Ingestion & Normalized Content Hashing

### Fingerprint Formulation
Source delta detection operates on normalized content rather than file timestamps or non-conflation metadata:
$$\text{Hash} = \text{SHA-256}\Big(\text{JSON}_{\text{sorted}}\big(\text{source}, \text{id}, \text{norm\_name}, \text{orig\_name}, \text{alt\_names}, \text{lat}_{7\text{dec}}, \text{lon}_{7\text{dec}}, \text{norm\_cat}, \text{locality}, \text{postcode}, \text{phone}, \text{website}\big)\Big)$$

### Properties & Invariants:
1. **Idempotency:** Re-ingesting an identical source snapshot produces 0 added, 0 modified, and 0 deleted records.
2. **Coordinate Sensitivity:** A displacement $\ge 0.0000001^{\circ}$ (~1.1 cm) changes the coordinate representation and flags the record as `MODIFIED` (`changed_fields = ['coordinates']`).
3. **Name Sensitivity:** Normalization or spelling adjustments change the hash and flag `MODIFIED` (`changed_fields = ['name']`).
4. **Category Sensitivity:** Taxonomy adjustments flag `MODIFIED` (`changed_fields = ['category']`).
5. **Metadata Invariance:** Ingestion timestamps, source extract timestamps, and row positions do not alter the content hash, preventing artificial delta cascades.

---

## 5. Component Merge & Split Handling

### Component Merge (Bridging Edge Addition)
When a newly accepted equivalence edge connects two previously isolated nodes or components:
1. The affected components are unified into a single active connected component.
2. The unified component is re-evaluated by the `SupervisedCanonicalResolver`.
3. If clean 1:1 or dominant star conditions are satisfied, a new equivalence entity is formed.
4. The `LineageLedger` emits an `ENTITY_MERGED` event referencing both previous canonical IDs as ancestors and the new canonical ID as child.

### Component Split (Edge Invalidation or Deletion)
When a previously accepted edge is rejected, removed, or invalidated:
1. The affected connected component is partitioned into disconnected subcomponents.
2. Each subcomponent is independently resolved (reverting to singletons or sub-equivalences).
3. The previous merged canonical ID is retired, and each child entity receives its deterministic canonical ID.
4. The `LineageLedger` emits an `ENTITY_SPLIT` event linking the retired ID to the resulting children.

### Canonical ID Stability Invariant
For any entity whose constituent source records have not experienced additions, removals, or merges, its canonical identifier is generated deterministically from:
$$\text{canonical\_id} = \text{UUIDv5}\Big(\text{NAMESPACE}, \text{osm:}\langle\text{sorted OSM IDs}\rangle \mid \text{ov:}\langle\text{sorted Overture IDs}\rangle\Big)$$
Because this mapping is a pure cryptographic function over sorted constituent source keys, unaffected entities retain 100% stable canonical identifiers across all pipeline runs.

---

## 6. Shared-Honorific Error Archetype Investigation

### Diagnostic Findings
Milestone 16.1 flagged approximately 242 candidate pairs with shared honorific prefixes (*Sri*, *The*, *Hotel*, *Dr.*) but disjoint business brands.
- **Root Cause:** Gradient-boosted trees rely heavily on Jaro-Winkler string similarity and spatial proximity. Jaro-Winkler grants a substantial bonus to common prefix tokens ("Sri" == "Sri", "The" == "The"). When two distinct businesses operate within 30–50 meters on the same commercial street, close proximity combined with a Jaro-Winkler score $> 0.70$ caused the model to predict match probability $> 0.55$.
- **Empirical Quantification:**
  - 737 candidate pairs in the accepted equivalence set share an honorific prefix.
  - Of these, 57 pairs exhibited completely disjoint brand cores (e.g., *The Kabab Company* vs. *The Himalayan Inn*, *Sri Swamy Medicals* vs. *Sri Lakshmi Jewels*, *Sri Kanteshwara Swamy Temple* vs. *Sri Venkateshwara Garments*).

### Safeguard Implementation: `SHARED_HONORIFIC_DISJOINT_BRAND`
The safeguard is integrated into `src/poi_conflation/graph/safeguards.py`:
1. Detects matching prefixes from `HONORIFIC_PREFIX_PATTERN`:
   `r"^(sri|shree|shri|sree|the|dr\.?|saint|st\.?|hotel|m/s|smt)\b"`
2. Strips the shared prefix and isolates the distinctive core strings.
3. Checks for shared significant brand tokens ($\ge 3$ characters) and substring containment.
4. If brand words are completely disjoint and `token_set_ratio < 65.0`, intercepts the pair, sets disposition to `REVIEW`, and records diagnostic evidence.
5. Preserves legitimate brand matches (e.g., *Dr. Batra's* vs. *Dr Batra's Homeopathy*, *The Raymond Shop* vs. *The Raymond Shop*, *Sri Guru Sweet Mart* vs. *Sri Guru Sweets Mart*).

---

## 7. Atomic Promotion & Failure Recovery

To prevent corrupt or partial production datasets:
1. **Staged Output Generation:** All outputs (`canonical_pois.parquet`, `canonical_pois.geojson`, `poi_relationships.parquet`, `unresolved_pairs.parquet`, `canonical_entity_lineage.parquet`) are written to an isolated directory:
   `data/processed/staging/<run_id>/`
2. **Continuous Validation Pre-Gate:** The validation suite inspects the staged files. If any critical check fails (e.g., null primary IDs, UUID collisions, inventory accounting mismatch, cross-entity ATM-bank merge), the orchestrator raises an exception and halts.
3. **Atomic File Promotion:** Only upon complete validation success are staged files copied into `data/processed/canonical/` via atomic `os.replace`.
4. **Cleanup:** Staging directories are cleaned up upon completion or failure. Existing production files remain intact if a run aborts halfway through.
