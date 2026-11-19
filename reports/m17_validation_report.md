# Milestone 17 — Continuous Validation & Verification Report

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** 2026-11-19  
**Author:** Sushant Yadav  
**Status:** **`PASSED`**  

---

## 1. Executive Summary

This report documents the verification results of the Milestone 17 production conflation pipeline, delta ingestion engine, and continuous validation layer. The pipeline was tested against:
1. The full production Bengaluru dataset (246,856 source POIs, 605,428 candidate edges, 238,083 canonical entities).
2. All 16 required synthetic test scenarios covering idempotency, additions, modifications, deletions, component merges, component splits, star dominance shifts, parent-child relationships, ATM safeguards, failure isolation, retries, and honorific prefix safeguards.

All 204 automated tests in the repository passed without failure.

---

## 2. Production Dataset Validation Gate Results

The automated continuous validation suite (`ContinuousConflationValidator`) was executed on the production exports in `data/processed/canonical/`:

| Check Name | Category | Status | Details / Verified Invariants |
| :--- | :---: | :---: | :--- |
| **`canonical_entity_null_checks`** | Canonical | **PASSED** | 238,083 entities; 0 null `canonical_entity_id`; 0 null `primary_name`. |
| **`canonical_id_uniqueness`** | Canonical | **PASSED** | 238,083 unique canonical IDs; **0 UUIDv5 collisions**. |
| **`source_inventory_accounting`** | Graph | **PASSED** | 49,036 OSM records (100.0%) and 197,820 Overture records (100.0%) accounted for; **0 lost records, 0 duplicate assignments**. |
| **`canonical_coordinate_bounds`** | Canonical | **PASSED** | Latitude: $[12.8351, 13.1390] \subset [12.8, 13.2]$; Longitude: $[77.4617, 77.7762] \subset [77.4, 77.8]$. |
| **`prohibited_atm_bank_merges`** | Graph | **PASSED** | **0 cross-entity ATM-to-bank merges** in `RESOLVED_EQUIVALENCE`. |
| **`relationship_integrity`** | Relationship | **PASSED** | 985 non-equivalence relationships (362 ATM, 420 Parent-Child, 203 Campus-Facility); **0 null endpoints**. |

**Overall Gate Status:** **`PASSED` (6/6 checks passed, 0 warnings, 0 failures)**

---

## 3. Synthetic Test Scenarios Verification (16 / 16 Passed)

The dedicated test suite in [tests/test_production_pipeline_m17.py](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/tests/test_production_pipeline_m17.py) verifies all required edge cases:

1. **Scenario 1 — Identical Snapshot Ingestion (Idempotency):**
   - Verified that ingesting the identical snapshot consecutively produces 0 added, 0 modified, and 0 deleted records (`has_changes == False`).
2. **Scenario 2 — One New POI Added:**
   - Verified that a new source POI (`node/104`) is classified as `ADDED` and emits an `ENTITY_CREATED` lineage event.
3. **Scenario 3 — One POI Name Modified:**
   - Verified that updating `name_normalized` flags the record as `MODIFIED` with `changed_fields == ['name']`.
4. **Scenario 4 — One POI Coordinate Modified:**
   - Verified that moving a POI's coordinates flags `MODIFIED` with `changed_fields == ['coordinates']`.
5. **Scenario 5 — One POI Category Modified:**
   - Verified that changing `category_normalized` flags `MODIFIED` with `changed_fields == ['category']`.
6. **Scenario 6 — One Source POI Deleted:**
   - Verified that removing a POI record is detected as `DELETED` and emits an `ENTITY_RETIRED` lineage event.
7. **Scenario 7 — Component Merge Event:**
   - Verified that when an accepted equivalence edge connects two previously separate entities, the resolver combines them and records an `ENTITY_MERGED` lineage event linking both parent IDs to the child ID.
8. **Scenario 8 — Component Split Event:**
   - Verified that when an equivalence edge is invalidated, the component separates and records an `ENTITY_SPLIT` lineage event linking the retired parent ID to the resulting singletons.
9. **Scenario 9 — Star Dominance Shift:**
   - Verified that in a 1:N star component, when the top candidate exceeds the runner-up by $\Delta s \ge 0.15$, the dominant winner is resolved to equivalence and the subordinate candidate is safely preserved as a singleton.
10. **Scenario 10 — Parent-Child Relationship Change:**
    - Verified that internal tenants in commercial containers (*Phoenix Marketcity* vs. *Zara*) are assigned `PARENT_CHILD` relationships rather than merged.
11. **Scenario 11 — ATM-Bank Safeguard Prevention:**
    - Verified that standalone ATM kiosks and bank branches (*HDFC Bank ATM* vs. *HDFC Bank*) are intercepted by `ATM_VS_BANK_FACILITY_DISTINCTION` and classified into `FACILITY_ATM` relationships.
12. **Scenario 12 — Failure Isolation & Atomic Protection:**
    - Verified that a simulated mid-pipeline failure leaves the production directory untouched and staging cleaned up.
13. **Scenario 13 — Failed Run Retry:**
    - Verified that subsequent retries after failure execute cleanly to `SUCCESS`.
14. **Scenario 14 — Full Rebuild vs. Incremental Equivalence:**
    - Verified that full rebuild and incremental execution produce identical canonical IDs and constituent memberships.
15. **Scenario 15 — Unaffected Canonical ID Stability:**
    - Verified that unaffected entities retain deterministic UUIDv5 canonical identifiers across repeated executions.
16. **Scenario 16 — Shared-Honorific Safeguard:**
    - Verified that pairs sharing honorific prefixes (*Sri*, *The*) but having disjoint brand words are intercepted by `SHARED_HONORIFIC_DISJOINT_BRAND` and routed to `REVIEW`.

---

## 4. Full Rebuild vs. Incremental Equivalence

To establish mathematical equivalence:
- **Theoretical Basis:** Connected components in the conflation graph form mutually disjoint equivalence partitions. For any component $C$ where no constituent node and no incident edge has changed, the local graph topology is identical between $G_{t-1}$ and $G_t$.
- **Empirical Check:** In Scenario 14, full rebuild resolution and incremental resolution on a test cluster produced identical UUIDv5 canonical identifiers (`entities_full[0].canonical_entity_id == entities_incr[0].canonical_entity_id`) and identical source node sets.
- **Lineage Consistency:** Unaffected entities generate `ENTITY_UNCHANGED` records, while affected entities generate explicit transitions (`ENTITY_UPDATED`, `ENTITY_MERGED`, `ENTITY_SPLIT`).

---

## 5. Performance and Resource Measurements

Measurements taken on Apple Silicon MacBook Pro M3 (8 GB unified memory):
- **Full Source Validation & Fingerprinting (246,856 POIs):** 1.42 seconds
- **Candidate Streaming & Safeguards (605,428 edges):** 14.85 seconds (~40,769 edges/sec)
- **Graph Component Discovery & Canonical Resolution (238,083 entities):** 1.88 seconds
- **Continuous Validation Suite (6 comprehensive checks):** 0.48 seconds
- **End-to-End Pipeline Duration:** **28.45 seconds**
- **Peak Resident Set Size (RSS):** **512.4 MB** (well within 8 GB RAM budget)

---

## 6. Known Limitations and Future Work

1. **Spatial Grid Partitioning for Very Large Deltas:** If an upstream snapshot modifies >50% of the entire urban inventory simultaneously, an incremental run gracefully falls back to a full rebuild.
2. **Kannada Honorific Prefix Expansion:** Currently, `HONORIFIC_PREFIX_PATTERN` matches Latin transliterated variants (*Sri*, *Shree*, *Sree*). Milestone 18 can expand vernacular Kannada script prefixes (`ಶ್ರೀ`, `ಶ್ರೀಮತಿ`).
3. **Active Learning Review Queue Integration:** The 956 review edges and 2,842 unresolved pairs are exported to Parquet and can be ingested directly into human annotation queues for iterative benchmark expansion.
