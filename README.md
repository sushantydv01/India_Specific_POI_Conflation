# India-Specific POI Conflation

A research-oriented data engineering project designed to build a reproducible, high-precision entity resolution pipeline that matches Point of Interest (POI) records across heterogeneous open geospatial datasets—specifically OpenStreetMap (OSM) and Overture Maps Foundation—within an Indian urban context.

---

## 1. Project Overview

Entity resolution (record linkage) in geospatial systems is the process of identifying records from disparate datasets that correspond to the identical real-world physical entity. This project focuses on conflating POIs located in an Indian city by addressing domain-specific challenges, including:

- Dense spatial clustering (e.g., commercial complexes, bazaars, and multi-tenant markets).
- Informal, colloquial, and highly variable address structures.
- Multilingual names, transliteration variations, phonetic drift, and localized abbreviations.
- Variable spatial accuracy and differing schema representations between data providers.

The outcome is an automated, auditable pipeline that classifies record pairs into deterministic matches, non-matches, or records requiring human review.

---

## 2. Problem Statement

Geospatial datasets from different open initiatives describe the same physical reality with divergent schemas, update cadences, and collection methodologies:

- **OpenStreetMap (OSM)** relies on crowd-sourced tagging conventions (`amenity`, `shop`, `tourism`, `name:en`, `name:hi`, etc.), resulting in rich semantic detail but variable completeness and geometry types (nodes vs. building polygons).
- **Overture Maps Foundation (Places Theme)** aggregates and standardizes global POI data into a structured schema with confidence scores, standardized categories, and normalized addresses.

Standard record linkage approaches fail in Indian environments due to two primary failure modes:
1. **Name Matching Failure:** String distance metrics (e.g., Levenshtein, Jaro-Winkler) without transliteration awareness fail when comparing names like "Laxmi General Store", "Lakshmi Provision Store", and "श्री लक्ष्मी जनरल स्टोर".
2. **Proximity Matching Failure:** In dense commercial hubs (e.g., Connaught Place in Delhi or Commercial Street in Bengaluru), tens of distinct businesses share coordinates within a 15-meter radius, rendering geographic distance alone insufficient to guarantee entity identity.

---

## 3. Primary Objectives

- **Ingestion & Normalization:** Ingest raw OSM extracts and Overture Places Parquet extracts into a unified intermediate canonical schema.
- **Candidate Generation (Blocking):** Implement high-recall spatial and attribute blocking (e.g., using Uber's H3 hierarchical spatial index) to reduce the $O(N \times M)$ pairwise comparison space to tractable candidate pairs.
- **Feature Engineering:** Build multi-dimensional similarity features capturing coordinate distance, phonetic and string similarity, token containment, category mapping alignment, and contextual parent/address tokens.
- **Probabilistic & Rule-Based Linkage:** Evaluate and calibrate decision boundaries to classify pairs into `MATCH`, `NON-MATCH`, and `REVIEW` states.
- **Ground Truth & Benchmark Evaluation:** Construct a curated, human-labeled evaluation dataset to objectively measure precision, recall, and F1 score.
- **Reproducibility & Provenance:** Ensure every processing step is deterministic, auditable, and capable of running on modest local computational resources.

---

## 4. Data Sources

| Data Source | Primary Entity Theme | Format | Primary License |
| :--- | :--- | :--- | :--- |
| **OpenStreetMap (OSM)** | Nodes & Polygons (`amenity`, `shop`, `office`, `leisure`, etc.) | `.osm.pbf` extracts | Open Database License (ODbL) 1.0 |
| **Overture Maps Foundation** | Places Theme | GeoParquet / Parquet | CDLA Permissive v2.0 (with ODbL attribution for OSM-derived components) |

---

## 5. Initial Technical Direction (Provisional)

The planned technical architecture emphasizes modern, local-first columnar analytical processing:

- **Analytical Engine:** DuckDB (zero-dependency, vectorized in-process SQL engine with spatial extension).
- **Storage & Interchange:** Apache Parquet / GeoParquet for columnar compression and partition pruning.
- **Spatial Indexing & Geometry:** H3 (hexagonal spatial indexing) and Shapely / GeoPandas for spatial operations and candidate blocking.
- **Text & Phonetic Analysis:** RapidFuzz (Levenshtein, token sort/set ratio) and phonetic transliteration modules tailored to Indian naming conventions.
- **Record Linkage Framework:** Splink (probabilistic linkage implementing the Fellegi-Sunter methodology) or custom calibrated classification models.

> **Note:** The above technologies are provisional and subject to empirical validation during the feasibility investigation. No software dependencies have been installed or finalized at this stage.

---

## 6. Planned Development Milestones

1. **Milestone 1 — Feasibility and Environment (Current):** Establish repository foundation, verify development hardware/tooling, define project scope, and set tracking baseline.
2. **Milestone 2 — City Selection & Data Acquisition Strategy:** Profile candidate Indian cities, evaluate data coverage across OSM and Overture, and define the study bounding box.
3. **Milestone 3 — Data Ingestion & Schema Normalization:** Extract, filter, and normalize raw extracts into a unified intermediate tabular representation.
4. **Milestone 4 — Spatial Indexing & Candidate Generation:** Design and evaluate spatial blocking strategies (H3 resolution tuning, bounding radius).
5. **Milestone 5 — Feature Engineering & Entity Linkage:** Compute similarity vectors across name, category, spatial proximity, and address attributes; calibrate matching thresholds.
6. **Milestone 6 — Benchmark Dataset & Evaluation:** Annotate a representative ground-truth sample; evaluate precision, recall, and false-positive characteristics.
7. **Milestone 7 — Pipeline Orchestration & Final Reporting:** Document findings, package reproducible execution workflows, and produce final technical report.

---

## 7. Current Project Status

- **Status:** Milestone 1 in progress.
- **Completed:** Repository initialized, git remote configured, directory tracking established, and foundational scoping documented.
- **Implemented Code:** None. No pipeline code, third-party libraries, or datasets have been pulled into the repository.
- **Planned vs. Implemented:** All technical components, data flows, and performance evaluations listed in this document reflect planned work.

---

## 8. Data Licensing & Attribution Considerations

This project processes data distributed under open data licenses:
- **OpenStreetMap Data:** Distributed under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/) (ODbL) by the OpenStreetMap Foundation (OSMF). Any derivative database or conflated output incorporating OSM data must comply with ODbL attribution (`© OpenStreetMap contributors`) and share-alike obligations.
- **Overture Maps Data:** Distributed under the [Community Data License Agreement – Permissive – Version 2.0](https://cdla.dev/permissive-2-0/) (CDLA Permissive v2.0). Portions derived from OSM carry underlying ODbL attribution.
- **Compliance Boundary:** Raw datasets will remain strictly outside source control (managed via `.gitignore`). Any publicly distributed benchmark annotations or evaluation artifacts will document upstream provenance and respect licensing boundaries.
