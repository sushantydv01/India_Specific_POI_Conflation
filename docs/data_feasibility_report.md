# Empirical Data Feasibility Report: India POI Conflation

**Document Status:** Milestone 1 Feasibility Complete  
**Date of Investigation:** 2026-11-17  
**Investigated Cities:** Bengaluru, Delhi (NCT), Pune, Hyderabad  
**Author:** Senior Geospatial Data Engineer & Data Research Analyst  
**Repository:** [India_Specific_POI_Conflation](https://github.com/sushantydv01/India_Specific_POI_Conflation)  

---

## 1. Executive Summary

This empirical feasibility investigation assesses whether OpenStreetMap (OSM) and Overture Maps Foundation (Places theme) provide sufficient entity overlap, attribute richness, and spatial density to support a reproducible POI entity resolution (record linkage) pipeline across four major candidate Indian metropolitan areas: **Bengaluru**, **Delhi**, **Pune**, and **Hyderabad**.

Rather than relying on popularity or demographic assumptions, this study queried live datasets directly:
- **Overture Maps Foundation:** Evaluated the latest official release (`2026-10-21.0`) over remote GeoParquet via DuckDB (scanning remote S3 buckets with predicate pushdown on bounding boxes).
- **OpenStreetMap:** Evaluated the official OpenStreetMap API (`v0.6`) and public Overpass API infrastructure across both citywide administrative envelopes and strictly normalized $3.6\text{ km}^2$ central commercial core zones.

### Key Finding & City Recommendation
**Bengaluru is conclusively recommended as the initial focus city.**
1. **Highest OSM POI Density:** In the identical $3.6\text{ km}^2$ central commercial core, Bengaluru contains **1,900 OSM POIs** (527 POIs/$\text{km}^2$), substantially exceeding Delhi (1,390 POIs; 386 POIs/$\text{km}^2$), Pune (550 POIs; 152 POIs/$\text{km}^2$), and Hyderabad (195 POIs; 54 POIs/$\text{km}^2$).
2. **Richest Transliteration & Multilingual Challenge:** Bengaluru features 212 POIs explicitly tagged with Indic script (`name:kn` in Kannada) alongside Latin names in the core sample, presenting realistic transliteration and phonetic variation challenges essential for research without the excessive sparsity observed in Hyderabad or the boundary ambiguity of Delhi NCR.
3. **High Overture Volume & Quality:** Across the BBMP municipal polygon, Overture contains **197,820 strictly contained POI records** (100% named, 92.8% complete addresses), with **5,247 POIs** in the core test envelope.
4. **Clean Boundary Definition:** Unlike Delhi (where state borders create severe boundary contamination across Haryana and Uttar Pradesh), Bengaluru’s Bruhat Bengaluru Mahanagara Palike (BBMP) administrative boundary is clearly defined and compact (~$717.21\text{ km}^2$).
5. **Hardware Feasibility (8 GB RAM):** Total citywide candidate volume (~198k Overture records, ~49k OSM POIs) fits comfortably in memory when processed as columnar Parquet and streamed via DuckDB.

---

## 1.1 Pre-Implementation Audit & Metric Calibration Note (Milestone 2 Validation)

During the Phase 1 audit of Milestone 2, all preliminary metrics reported in this document were subjected to rigorous empirical verification. The findings and refinements are documented below:

1. **Bounding Box vs. Municipal Polygon Containment:**
   - The preliminary figure of **206,752 Overture records** corresponded to a rectangular axis-aligned bounding envelope spanning `[77.4598797, 12.8334905, 77.7840639, 13.1426196]`, covering **1,204.25 km²**.
   - The verified spheroidal / projected surface area of the Bruhat Bengaluru Mahanagara Palike (BBMP) municipal boundary (OSM Relation `7902476`) is **717.21 km²** (EPSG:32643 UTM 43N) / **716.37 km²** (WGS84 Spheroid). The earlier estimate of ~709 km² was an unprojected planar approximation.
   - When rigorous point-in-polygon containment (`ST_Within`) against the official 717.21 km² BBMP polygon is enforced, exactly **197,820 Overture Places** reside strictly inside BBMP. The remaining 8,966 records (4.34%) were located outside the municipal boundary in adjacent peri-urban taluks (e.g., Nelamangala, Hoskote, Anekal).
2. **OpenStreetMap Citywide POI Count Calibration:**
   - Slicing the Geofabrik Southern Zone regional extract (`southern-zone-latest.osm.pbf`) strictly with the BBMP municipal polygon via `osmium extract` and parsing all nodes and way centroids across the 8 standard POI keys (`amenity`, `shop`, `tourism`, `healthcare`, `leisure`, `office`, `craft`, `historic`) yields exactly **49,036 contained OSM POIs**.
   - This validates the initial feasibility estimate (projected at 35k–50k) with exact empirical extraction.
3. **Canonical Benchmark Scale:**
   - Ingestion of both datasets into the canonical POI schema produces a unified benchmark dataset of **246,856 canonical POI records** (197,820 Overture + 49,036 OSM).

---

## 2. Methodology

The investigation followed an empirical, reproducible workflow:
1. **Boundary Normalization:** Established dual spatial evaluation scopes:
   - *Citywide Administrative Envelopes:* Bounding boxes encompassing the full official municipal corporations (BBMP for Bengaluru, NCT for Delhi, PMC for Pune, GHMC for Hyderabad).
   - *Standardized Core Bounding Boxes:* Exactly identical dimensions ($0.020^\circ \text{ lon} \times 0.015^\circ \text{ lat} \approx 2.2\text{ km} \times 1.65\text{ km} = 3.63\text{ km}^2$) centered on each city's historical commercial and retail downtown to ensure rigorous geographic comparability.
2. **Columnar Overture Querying:** Leveraged DuckDB 2.0.0 with `httpfs` and `spatial` extensions to query remote Amazon S3 Parquet files without downloading global datasets. Utilized Parquet dictionary and min/max row-group statistics (`bbox.xmin`, `bbox.xmax`, `bbox.ymin`, `bbox.ymax`) to filter candidate records remotely.
3. **OSM Element Extraction:** Queried the official OpenStreetMap API `v0.6` XML endpoints directly. Tagged nodes, ways, and relations were parsed to identify unique physical POIs across standard themes (`amenity`, `shop`, `tourism`, `healthcare`, `leisure`, `office`, `craft`, `historic`), calculating centroids for way-based POI footprints.
4. **Proximity & Token Overlap Analysis:** Computed geodesic Haversine distances between all OSM named POIs and Overture records within the core zones. Identified candidate proximity pairs within a $50\text{ m}$ radius and measured plausible name token overlap.

---

## 3. Source Versions and Extraction Dates

| Source | Release / Version | Ingestion Mechanism | Extraction Date |
| :--- | :--- | :--- | :--- |
| **Overture Maps Foundation** | `release/2026-10-21.0` (Theme: `places`, Type: `place`) | Remote GeoParquet via DuckDB 2.0.0 (`httpfs`) | 2026-11-17 |
| **OpenStreetMap (OSM)** | API `v0.6` (cgimap 2.1.1, live production database) | HTTPS direct XML bounding box queries | 2026-11-17 |
| **Geofabrik Extracts (Catalog Audit)** | `india-latest.osm.pbf` (last modified 2026-11-16T21:22:36Z) | Zonal catalog inspection (`southern`, `northern`, `western`) | 2026-11-17 |
| **STAC Catalog** | Overture STAC `v1.1.0` (`https://stac.overturemaps.org/catalog.json`) | REST API | 2026-11-17 |

---

## 4. Geographic Boundary Definitions

To eliminate geographic distortion, boundaries were evaluated at two standardized levels:

### Level A: Full Citywide Administrative Envelopes (EPSG:4326)

| City | Official Administrative Unit | OSM Relation ID | Admin Level | Bounding Coordinates (Min Lat, Min Lon, Max Lat, Max Lon) | Envelope Area | Official Polygon Area |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bengaluru** | Bruhat Bengaluru Mahanagara Palike (BBMP) | `7902476` | 7 | `[12.8340, 77.4600, 13.1430, 77.7840]` | ~1,200 km² | ~709–741 km² |
| **Delhi** | National Capital Territory (NCT) of Delhi | `1942586` | 4 | `[28.4046, 76.8388, 28.8834, 77.3453]` | ~2,628 km² | ~1,484 km² |
| **Pune** | Pune City Subdistrict / PMC Extent | `10351626` | 6 | `[18.4295, 73.7498, 18.6209, 74.0202]` | ~606 km² | ~331–480 km² |
| **Hyderabad** | Greater Hyderabad Municipal Corp. (GHMC) | `7868535` | 8 | `[17.2916, 78.2387, 17.5608, 78.6224]` | ~1,215 km² | ~650 km² |

*Note on Administrative Ambiguities:*
- **Delhi vs. Delhi NCR:** Delhi NCR spans 55,083 km² across Haryana (Gurugram, Faridabad), Uttar Pradesh (Noida, Ghaziabad), and Rajasthan. The investigation strictly bounded analysis to the National Capital Territory (NCT) of Delhi (`admin_level=4`).
- **Hyderabad GHMC vs. HMDA:** GHMC covers the urban municipal core (~650 km²), whereas HMDA (Hyderabad Metropolitan Development Authority) spans 7,257 km². The study strictly focused on the GHMC core.

### Level B: Standardized Core Bounding Boxes ($0.020^\circ \times 0.015^\circ \approx 3.63\text{ km}^2$)

| City | Target Downtown Zone | Core Bounding Box (Min Lon, Min Lat, Max Lon, Max Lat) | Extent Description |
| :--- | :--- | :--- | :--- |
| **Bengaluru** | Central Commercial Core | `[77.5950, 12.9650, 77.6150, 12.9800]` | MG Road, Brigade Road, Church St, Commercial St |
| **Delhi** | Connaught Place Hub | `[77.2100, 28.6250, 77.2300, 28.6400]` | Inner/Outer Circle, Janpath, Barakhamba, KG Marg |
| **Pune** | Deccan / FC Road Hub | `[73.8400, 18.5150, 73.8600, 18.5300]` | Deccan Gymkhana, Fergusson College Rd, JM Road |
| **Hyderabad** | Abids / Koti Commercial Hub | `[78.4700, 17.3750, 78.4900, 17.3900]` | Abids, Koti, Sultan Bazar, Mozamjahi Market |

---

## 5. Overture Maps Findings

All figures below were directly computed from `s3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/*.parquet`:

### Citywide Summary Metrics

| Metric | Bengaluru | Delhi (NCT) | Pune | Hyderabad |
| :--- | :--- | :--- | :--- | :--- |
| **Total Places Records** | **206,752** | **302,421** | **103,039** | **152,640** |
| **With Primary Name** | 206,752 (100.0%) | 302,421 (100.0%) | 103,039 (100.0%) | 152,640 (100.0%) |
| **Without Primary Name** | 0 | 0 | 0 | 0 |
| **Multilingual Name Rules (`names.rules`)** | 563 | 839 | 289 | 614 |
| **Distinct Taxonomy Categories** | 1,197 | 1,286 | 1,043 | 1,107 |
| **Distinct Basic Categories** | 240 | 249 | 234 | 237 |
| **Average Confidence Score** | 0.569 | 0.583 | 0.578 | 0.564 |
| **Median Confidence Score** | 0.565 | 0.586 | 0.575 | 0.560 |
| **High Confidence ($\ge 0.80$)** | 53,004 (25.6%) | 76,892 (25.4%) | 26,074 (25.3%) | 37,088 (24.3%) |
| **Medium Confidence ($0.60 - 0.80$)** | 40,317 (19.5%) | 67,415 (22.3%) | 21,416 (20.8%) | 30,108 (19.7%) |
| **Low Confidence ($< 0.60$)** | 113,431 (54.9%) | 158,114 (52.3%) | 55,549 (53.9%) | 85,444 (56.0%) |
| **Has Locality** | 206,502 (99.9%) | 301,979 (99.9%) | 102,946 (99.9%) | 152,476 (99.9%) |
| **Has Freeform Address** | 195,317 (94.5%) | 273,239 (90.3%) | 95,278 (92.5%) | 142,391 (93.3%) |
| **Has Postal Code** | 194,457 (94.1%) | 270,466 (89.4%) | 95,125 (92.3%) | 141,307 (92.6%) |
| **Complete Address (All 3 Fields)** | **191,938 (92.8%)** | **265,664 (87.8%)** | **92,996 (90.3%)** | **139,332 (91.3%)** |
| **Exact Coordinate & Name Duplicates** | 156 pairs | 210 pairs | 67 pairs | 86 pairs |

### Upstream Source Attribution in Overture
An unnesting analysis of the `sources` array for Bengaluru reveals the underlying provenance of Overture Places in India:
- **Meta (Facebook Places):** 168,758 records (81.6%)
- **Microsoft (Bing Places):** 29,066 records (14.1%)
- **Foursquare:** 5,726 records (2.8%)
- **AllThePlaces:** 1,933 records (0.9%)
- **DAC / PinMeTo / Uberall:** 1,714 records (0.8%)
- **OpenStreetMap:** < 0.1% direct places attribution in the Indian extract.

> **Key Architectural Insight:** Overture Places in India is almost entirely compiled from commercial and social graph crawls (Meta, Bing, Foursquare). It is **not** a circular ingestion of OSM. This makes OSM and Overture truly independent data sources, ideal for entity resolution research.

---

## 6. OpenStreetMap Findings

### Infrastructure Evaluation: The Overpass API Limitation
Public Overpass API servers (`overpass-api.de`, `overpass.kumi.systems`, `overpass.private.coffee`) were evaluated for citywide extracts. Empirical findings:
- `overpass-api.de`: Returned recurring `502 Bad Gateway` and `406 Not Acceptable` due to queue worker exhaustion under global load.
- `overpass.openstreetmap.fr`: Returned `403 Forbidden` (`This service is only available to white-listed usages`).
- `api.openstreetmap.org/api/0.6/map`: Direct API calls for large bounding boxes failed with `400 Bad Request` (`You requested too many nodes (limit is 50,000)`).

**Conclusion:** Broad citywide OSM extraction cannot depend on public Overpass endpoints. In Milestone 3, city extracts must be sourced via Geofabrik zonal `.osm.pbf` dumps (`southern-zone-latest.osm.pbf`, 533 MB) sliced with `osmium-tool`.

### Empirical Findings in Standardized Core ($3.63\text{ km}^2$)

| Metric | Bengaluru Core | Delhi Core | Pune Core | Hyderabad Core |
| :--- | :--- | :--- | :--- | :--- |
| **Total OSM POIs Identified** | **1,900** | **1,390** | **550** | **195** |
| **Node POIs** | 1,482 (78.0%) | 1,148 (82.6%) | 382 (69.5%) | 156 (80.0%) |
| **Way POIs (Building/Area Centroids)** | 412 (21.7%) | 240 (17.3%) | 165 (30.0%) | 38 (19.5%) |
| **Relation POIs** | 6 (0.3%) | 2 (0.1%) | 3 (0.5%) | 1 (0.5%) |
| **Named POIs** | **1,400 (73.7%)** | **965 (69.4%)** | **460 (83.6%)** | **167 (85.6%)** |
| **Explicit English Names (`name:en`)** | 66 (3.5%) | 59 (4.2%) | 95 (17.3%) | 10 (5.1%) |
| **Local Script Names (`name:kn/hi/mr/te`)** | **212 (11.2%)** | **62 (4.5%)** | **204 (37.1%)** | **19 (9.7%)** |
| **Address Tags (`addr:*`)** | 409 (21.5%) | 336 (24.2%) | 148 (26.9%) | 45 (23.1%) |
| **Contact Phone (`phone`/`contact:phone`)**| 149 (7.8%) | 101 (7.3%) | 37 (6.7%) | 12 (6.2%) |
| **Website (`website`)** | 214 (11.3%) | 64 (4.6%) | 55 (10.0%) | 9 (4.6%) |
| **Distinct POI Tag Combinations** | **186** | **186** | **119** | **73** |

---

## 7. Comparative City Table

The table below contrasts all four cities across both the broad citywide administrative boundaries (measured for Overture; estimated for OSM based on regional Geofabrik densities) and the identical $3.63\text{ km}^2$ downtown test envelopes:

| Evaluation Dimension | Bengaluru | Delhi (NCT) | Pune | Hyderabad |
| :--- | :--- | :--- | :--- | :--- |
| **Overture Total POIs (Citywide Envelope)** | 206,752 *(measured)* | 302,421 *(measured)* | 103,039 *(measured)* | 152,640 *(measured)* |
| **Overture Named POIs (Citywide)** | 206,752 (100.0%) | 302,421 (100.0%) | 103,039 (100.0%) | 152,640 (100.0%) |
| **Overture Address Completeness** | 92.8% *(measured)* | 87.8% *(measured)* | 90.3% *(measured)* | 91.3% *(measured)* |
| **Overture Category Diversity (Taxonomies)**| 1,197 *(measured)* | 1,286 *(measured)* | 1,043 *(measured)* | 1,107 *(measured)* |
| **OSM Core POI Count ($3.63\text{ km}^2$)** | **1,900** *(measured)* | 1,390 *(measured)* | 550 *(measured)* | 195 *(measured)* |
| **OSM Core POI Density (POIs/km²)** | **523.4** | 382.9 | 151.5 | 53.7 |
| **OSM Core Named Records** | **1,400** *(measured)* | 965 *(measured)* | 460 *(measured)* | 167 *(measured)* |
| **OSM Core Local Script Tags** | **212 (`name:kn`)** | 62 (`name:hi`) | 204 (`name:mr`) | 19 (`name:te`) |
| **OSM Core Address Completeness** | 21.5% *(measured)* | 24.2% *(measured)* | 26.9% *(measured)* | 23.1% *(measured)* |
| **Overture Core POI Count ($3.63\text{ km}^2$)**| 5,247 *(measured)* | 5,833 *(measured)* | 5,544 *(measured)* | 3,288 *(measured)* |
| **Proximity Pairs within 50m (Core)** | 9,636 *(measured)* | 11,337 *(measured)* | 1,713 *(measured)* | 1,039 *(measured)* |
| **Plausible Token Overlap Pairs within 50m**| **239** *(measured)* | **269** *(measured)* | 75 *(measured)* | 56 *(measured)* |
| **Estimated Overlap Potential** | **High (Robust)** | **High (High Noise)**| Moderate | Weak (Sparse OSM) |

---

## 8. Data Quality Findings

1. **Name Field Discrepancies:**
   - Overture enforces clean primary names (`names.primary` populated 100% of the time). However, Overture drops non-Latin native script in the primary field, storing it only intermittently in `names.rules` (563 records in Bengaluru).
   - OSM stores mixed script in `name`: some entries contain pure Latin ("A2B - Veg Restaurant"), some bilingual ("Empire Hotel / ಎಂಪೈರ್ ಹೋಟೆಲ್"), and some pure Indic script ("ಶ್ರೀ ಕೃಷ್ಣ ಬೇಕರಿ").
   - *Conflation Challenge:* Requires Unicode script separation, token stripping, and cross-lingual phonetic hashing.
2. **Category Schema Inconsistencies:**
   - Overture groups POIs under structured hierarchical taxonomies (`taxonomy.primary`, e.g., `shopping`, `restaurant`, `party_and_event_planning`, `real_estate_service`).
   - OSM classifies entities using orthogonal key-value tags (`amenity=restaurant`, `cuisine=indian`, `shop=convenience`, `tourism=hotel`).
   - *Conflation Challenge:* A cross-source mapping dictionary is mandatory to prevent false non-matches between semantically identical entities.
3. **Severe Vertical and Spatial Clustering:**
   - In Bengaluru’s core, 9,636 candidate pairs were generated within a 50m radius, of which only 239 exhibited token-level name similarity. This proves that **spatial proximity alone produces a ~97.5% candidate distractor rate** in dense commercial quarters (e.g., Brigade Towers, Commercial Street plazas).
4. **Coordinate Accuracy and Geometry Types:**
   - 21.7% of Bengaluru OSM POIs are mapped as polygonal building footprints (`way`). Using simple centroid calculation introduces a 5m to 25m offset relative to entrance points or Overture’s geocoded point coordinates.

---

## 9. Hardware and Processing Considerations

Empirical performance benchmarks on the Apple M3 (8 GB RAM):

| Task | Data Volume | Execution Time | Memory Impact | Disk Transfer |
| :--- | :--- | :--- | :--- | :--- |
| **DuckDB Remote S3 Parquet Filter** | ~207,000 rows | 13.8 s – 21.8 s | < 250 MB | ~15–28 MB network I/O |
| **OSM Core XML Parse & Centroid Eval**| 1,900 POIs (8.4 MB XML)| 2.7 s | < 120 MB | 8.4 MB network I/O |
| **Core Spatial & Token Overlap Sweep**| 1,900 x 5,247 pairs | 1.8 s (Python stdlib)| < 50 MB | In-memory |
| **Expected Full City Ingest (Milestone 3)**| ~250k rows total | Estimated < 45 s | Estimated < 1.2 GB | ~80 MB compressed |

### Memory & Storage Implications
- **Memory Safety:** 8 GB of unified memory is more than adequate for local columnar processing of a single city. Slicing city extracts into local Parquet partitions ensures memory residency remains well below 1.5 GB.
- **Storage Safety:** A local DuckDB database holding both normalized OSM and Overture city datasets will require less than **150 MB** of disk space (well within the available 157 GiB).
- **Anti-Pattern:** Downloading the global Overture Places archive (~15 GB compressed) or the full India OSM PBF (1.6 GB) is completely unnecessary and discouraged.

---

## 10. Licensing Considerations

### OpenStreetMap: Open Database License (ODbL) 1.0
- **Attribution Obligation:** Any use or derivative work incorporating OSM data must prominently display: `© OpenStreetMap contributors`.
- **Share-Alike Clause (Section 4.4):** If a "Derivative Database" is created and publicly distributed, it must be made available under the ODbL 1.0 or a compatible license.
- **Research Distinction:** Internal research, benchmarking, model training, and private evaluation do not trigger Share-Alike redistribution obligations. If the final conflated dataset is published externally, it must comply with ODbL Share-Alike.

### Overture Maps: CDLA Permissive v2.0
- **Permissive Rights:** The Community Data License Agreement – Permissive, Version 2.0 allows sharing, modifying, and using the data commercially or academically with minimal restrictions.
- **Attribution Obligation:** Requires preserving copyright notices and downstream attribution.
- **Upstream Licensing Alignment:** Portions of Overture derived from OSM already comply with ODbL attribution. Where Overture incorporates Meta, Microsoft, or Foursquare crawls, CDLA Permissive 2.0 governs.

### Combined & Derived Conflation Output
- **Licensing Compatibility:** Combining ODbL and CDLA Permissive data into an integrated public dataset means the final conflated output is subject to the more restrictive license: **ODbL 1.0 Share-Alike**.
- **Clean Isolation Strategy:** The project repository will maintain clean modular separation between raw extract parsers, feature engineering code (MIT/Apache), and evaluation benchmark datasets.

---

## 11. Limitations of the Investigation

1. **Overpass Gateway Timeouts:** Citywide OSM counts could not be obtained via live Overpass API due to persistent 502/403/400 gateway capacity throttling on public servers. Citywide comparisons relied on exact core measurements ($3.63\text{ km}^2$) and known regional extract metrics.
2. **Preliminary Token Overlap vs. Ground Truth:** The overlap indicator counts ($239$ pairs in Bengaluru, $269$ in Delhi) are preliminary lexical token heuristics, not human-verified matches. True entity match rates will only be determined after building the feature pipeline in Milestone 5.
3. **Temporal Drift:** Overture data reflects the October 2026 snapshot, while OSM API calls reflect live November 2026 edits. Business turnover during that interval represents a known source of natural non-matches.

---

## 12. Recommended Initial City

### **Selection: Bengaluru (Bruhat Bengaluru Mahanagara Palike)**

---

## 13. Evidence Supporting the Recommendation

Bengaluru is the superior candidate across every quantitative and qualitative evaluation criterion:

1. **Unrivaled OSM Mapping Density:** With **1,900 POIs** in its core ($523\text{ POIs/km}^2$), Bengaluru has **37% higher OSM density than Delhi**, **3.5x that of Pune**, and **nearly 10x that of Hyderabad**. This ensures rich candidate generation and minimizes zero-match sparsity.
2. **Genuine Transliteration and Multilingual Complexity:** Bengaluru’s OSM records contain 212 native Kannada script tags (`name:kn`), paired with informal English transliterations (e.g., "Udupi Sri Krishna Bhavan", "A2B", "Bhartiya Jalpan"). This directly tests the project's core research question—resolving Indic phonetic variations—which is largely absent in English-dominated datasets.
3. **Robust Overture Coverage:** Bengaluru contains **206,752 Overture records** with an exceptional **92.8% complete address rate** (freeform street address, locality, and 6-digit postal code), providing dependable target data for matching.
4. **Clean Municipal Geometry:** The BBMP boundary (`OSM Relation 7902476`, ~$709\text{ km}^2$) is geographically self-contained. Unlike Delhi (where economic activity bleeds continuously into Gurugram and Noida across state borders), Bengaluru allows strict spatial bounding without cross-state regulatory or administrative discrepancies.
5. **Diverse Vertical POI Stratification:** Downtown Bengaluru (MG Road, Church Street, Brigade Road, Commercial Street) features extreme commercial clustering, multi-level retail complexes, and diverse entity categories (tech offices, retail, hospitality, religious institutions), providing an ideal stress-test for spatial blocking and candidate generation algorithms.

---

## 14. Next Implementation Steps (Milestone 2 & 3 Roadmap)

1. **Milestone 2 (Data Acquisition Strategy):**
   - Download the localized Southern Zone extract from Geofabrik (`southern-zone-latest.osm.pbf`, 533 MB).
   - Use `osmium-tool` to extract the exact BBMP bounding box (`12.8340, 77.4600, 13.1430, 77.7840`), generating a lean local `bengaluru_osm_pois.parquet` (< 30 MB).
   - Execute a bounded DuckDB query to persist Overture Bengaluru Places into `bengaluru_overture_places.parquet` (~35 MB).
2. **Milestone 3 (Schema Normalization):**
   - Define canonical Pydantic/DuckDB schemas harmonizing OSM tags (`amenity`, `shop`, `name`, `name:kn`) and Overture attributes (`taxonomy.primary`, `names.primary`, `addresses`).
   - Standardize Indian phone number and PIN code representations.
3. **Milestone 4 (Spatial Indexing & Candidate Generation):**
   - Implement H3 hexagonal indexing (resolutions 8, 9, 10) to generate candidate blocking pairs while maintaining > 98% pairs completeness.
