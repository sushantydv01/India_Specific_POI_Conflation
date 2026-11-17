# Licensing, Provenance, and Legal Attribution Architecture

This document formalizes the legal licensing frameworks, data provenance chains, and downstream derivative dataset obligations governing the **India-Specific POI Conflation** research project and its constituent data sources: **OpenStreetMap (OSM)** and **Overture Maps Foundation Places**.

---

## 1. Upstream Data Licenses

### 1.1 OpenStreetMap (OSM)
* **Governing License:** [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
* **Licensor:** OpenStreetMap Foundation (OSMF) and OpenStreetMap contributors
* **Attribution Notice:** `© OpenStreetMap contributors`
* **Core License Terms:**
  * **Attribution (Section 4.3):** Any public presentation, user-facing map, downstream dataset, or query interface containing OSM features must visibly attribute OpenStreetMap and make it explicit that the data is available under ODbL 1.0.
  * **Share-Alike (Section 4.4):** If a *Derivative Database* is created and publicly conveyed, it must be offered under the terms of ODbL 1.0 or a compatible license.
  * **Notice & Reverse Engineering (Section 4.2):** Redistributed databases must include a copy of the ODbL or an explicit machine-readable link, and cannot impose technological restrictions that prevent users from accessing the underlying database.

### 1.2 Overture Maps Foundation Places
* **Governing License:** [Community Data License Agreement – Permissive, Version 2.0 (CDLA-Permissive-2.0)](https://cdla.dev/permissive-2-0/)
* **Licensor:** Overture Maps Foundation (Linux Foundation Joint Venture)
* **Attribution Notice:** `Data provided by Overture Maps Foundation under CDLA-Permissive-2.0`
* **Core License Terms:**
  * **Permissive Grant:** Grants a worldwide, royalty-free, non-exclusive, sublicensable permission to use, reproduce, modify, display, distribute, and make available data without imposing downstream share-alike obligations.
  * **Attribution Requirement:** Requires preserving copyright and license notices when data is redistributed.
  * **Upstream Data Provenance in Overture Places:**
    * Overture's Places theme incorporates records contributed by foundational partners, primarily **Meta** (Facebook Graph places data), **Microsoft Bing** (places and point entities), **Esri**, and community open sources.
    * Each Overture record carries provenance metadata in `sources`, identifying the upstream contributor and timestamp of each ingested attribute.

---

## 2. Database Combination Considerations & Legal Interpretations

The intersection of ODbL 1.0 (a copyleft / share-alike database license) and CDLA-Permissive-2.0 (a permissive license) requires careful structural and legal distinction. In open geospatial data engineering, the legal impact depends heavily on how the datasets are organized, transformed, and distributed.

### 2.1 The Distinction: "Collective Database" vs. "Derivative Database"
According to Open Database Commons guidelines and OSMF Community Guidelines:

1. **Collective Database (Independent / Horizontal Linking):**
   * A Collective Database exists when independent databases are distributed together or linked externally, but each retains its separate identity and neither modifies the core contents of the other.
   * *Example in Conflation:* Maintaining an independent Overture dataset and an independent OSM dataset, and generating a standalone **Concordance Index / Linkage Table** (e.g., pairs of `(osm_id, overture_id, match_probability, spatial_distance)`).
   * *Share-Alike Implication:* Under OSMF Community Guidelines on "Horizontal Linking", publishing an external cross-reference table that references OSM identifiers without incorporating substantive OSM geometry or attribute text does **not** necessarily force the non-OSM source database (Overture) to become subject to ODbL Share-Alike.

2. **Derivative Database (Unified Harmonized Schema):**
   * A Derivative Database is created when OSM data is blended, aggregated, adapted, or enriched such that downstream records are produced using OSM attributes, coordinates, or topological adjustments.
   * *Example in Conflation:* Merging an OSM node with an Overture place into a single unified record where OSM tags (e.g., vernacular script `name:kn`) enrich Overture records, or where Overture coordinates are adjusted toward OSM centroids.
   * *Share-Alike Implication:* If this composite, enriched table is publicly distributed or conveyed, Section 4.4 of ODbL applies, requiring the composite derivative dataset to be made available under ODbL 1.0.

---

## 3. Potential Share-Alike Implications Across Pipeline Outputs

To provide clarity and prevent over-generalization, the potential licensing requirements for each project artifact are categorized below:

| Repository Artifact | Data Contents | Legal Classification | Governing / Compatible Terms |
| :--- | :--- | :--- | :--- |
| **Pipeline Source Code (`src/`, `scripts/`, `tests/`)** | Algorithmic code, models, schemas | Computer Software | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) (Permissive open source) |
| **Raw OSM Extracts (`data/raw/osm/`)** | Unaltered OSM nodes & ways | Source Database Extract | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| **Raw Overture Extracts (`data/raw/overture/`)** | Unaltered Overture GeoParquet | Source Database Extract | [CDLA-Permissive-2.0](https://cdla.dev/permissive-2-0/) |
| **Harmonized Canonical POIs (`canonical_pois.parquet`)** | Co-located unified schema holding records from both sources | Dual / Collective Staging | Dual attribution required; if published with OSM content, ODbL 1.0 applies |
| **Concordance Match Tables (`concordance_pairs.parquet`)** | Cross-source mapping `(osm_id, overture_id, score)` | Linkage Index / Collective Data | Can be distributed independently under ODbL 1.0 or permissive terms depending on whether OSM attribute text is embedded |
| **Enriched Composite Master POIs** | Blended records combining attributes from both sources | Derivative Database | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (Share-Alike triggered upon distribution) |

---

## 4. Attribution and Provenance Requirements for Downstream Consumers

Any consumer, publication, or downstream platform utilizing datasets or code produced by this project must include the following dual attribution statement:

```text
This dataset was produced by the India-Specific POI Conflation pipeline.
Contains information from:
1. OpenStreetMap, which is made available here under the Open Database License (ODbL) 1.0.
   © OpenStreetMap contributors. Available at: https://www.openstreetmap.org/copyright
2. Overture Maps Foundation Places, which is made available under the Community Data License 
   Agreement – Permissive, Version 2.0 (CDLA-Permissive-2.0).
   Data provided by Overture Maps Foundation (incorporating Meta, Microsoft Bing, and partners).
   Available at: https://overturemaps.org/
```

---

## 5. Unresolved Legal Uncertainties & Best Practices

The following open questions in international geospatial intellectual property law inform our engineering architecture:

1. **Extraction Substantiality:** ODbL Section 4.4 applies to extraction or re-utilization of "substantial" parts of the database. While extracting an entire metropolitan corporation (49,036 POIs) is substantial for that municipality, what constitutes a substantial extraction in relation to national or global OSM data remains subject to legal interpretation across jurisdictions.
2. **Concordance Index Status:** The legal status of foreign-key cross-reference indexes (concordance tables) without feature geometries is an evolving subject. OSMF guidelines generally favor allowing external linking without infecting unrelated third-party databases, provided the link table itself respects ODbL if derived through substantive OSM geometry analysis.
3. **Database Rights vs. Copyright:** In jurisdictions outside the European Union (such as India and the United States), *sui generis* database rights do not exist in the same statutory form; protection relies on copyright in the selection and arrangement of data. However, compliance with upstream license contracts (ODbL and CDLA) remains mandatory regardless of local database right statutes.
4. **Research Engineering Best Practice:** To maintain rigorous compliance, our pipeline:
   - Does not commit raw proprietary or upstream data to Git.
   - Preserves complete provenance fields (`source_record_id`, `poi_source`, `provenance_metadata`) on every record.
   - Formulates composite outputs under ODbL 1.0 whenever distributed, ensuring uninterrupted downstream compliance.
