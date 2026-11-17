# H3 Spatial Indexing Architecture

This document describes the spatial indexing foundation implemented for the **India-Specific POI Conflation** pipeline using Uber's [H3 Discrete Global Grid System](https://h3geo.org/).

---

## 1. Architectural Objectives & Motivation

In naive entity resolution across heterogeneous geospatial providers, candidate pair evaluation scales quadratically:

$$\text{Cross-Source Pair Space} = N_{\text{OSM}} \times N_{\text{OVERTURE}} = 49{,}036 \times 197{,}820 \approx 9.70 \times 10^9 \text{ pairs}$$

Materializing or scanning 9.7 billion pairs is computationally prohibitive and memory-intensive on local workstation hardware (Apple M3, 8 GB RAM).

To achieve sub-second spatial filtering and scalable candidate blocking, the pipeline utilizes:
1. **Multi-Scale Discrete Hexagonal Partitioning (Uber H3):** Indexing every POI into discrete hierarchical hexagonal cells at multiple spatial scales.
2. **Equi-Join Spatial Bins:** Translating spatial distance threshold queries into equi-joins over discrete grid cells, reducing candidate evaluation time from over 60 seconds to **90 milliseconds**.

---

## 2. Selected H3 Resolutions

The canonical dataset is indexed simultaneously across three hierarchical H3 resolutions:

| H3 Resolution | Avg Hexagon Area ($\text{km}^2$) | Avg Hexagon Edge Length ($m$) | Spatial Semantics & POI Blocking Role |
| :---: | :---: | :---: | :---: |
| **Resolution 8** | $\approx 0.737\text{ km}^2$ | $\approx 461\text{ m}$ | **Macro-Neighborhood Scale:** Captures entire commercial sectors (e.g., Indiranagar 100ft Road corridor, Koramangala 5th Block, MG Road commercial core). Used for high-level spatial density profiling and macro-blocking. |
| **Resolution 9** | $\approx 0.105\text{ km}^2$ | $\approx 174\text{ m}$ | **Block / Street-Segment Scale:** Encompasses contiguous street blocks and commercial crossroads. Serves as primary candidate generation boundary ($k=1$ disk radius covers $\le 200\text{m}$). |
| **Resolution 10** | $\approx 0.015\text{ km}^2$ | $\approx 66\text{ m}$ | **Micro-Parcel / Co-location Scale:** Encompasses shopping arcades, medical compounds, and immediate physical adjacencies ($\le 50\text{m}$). High probability of co-located identity candidates. |

---

## 3. Spatially Indexed Dataset Specification

* **Output Artifact:** `data/processed/canonical_pois_h3.parquet`
* **File Size:** **31.68 MB** (Zstandard compression)
* **Row Count:** **246,856 records** (197,820 Overture + 49,036 OSM)
* **Metadata Manifest:** `data/processed/canonical_pois_h3_metadata.json`

### Schema Additions

The indexed analytical dataset extends the canonical schema with four primary fields:

```text
canonical_poi_id  : string (UUIDv5 derived from source and source_record_id)
... [All 21 original canonical fields preserved] ...
h3_res8           : string (15-character hexadecimal H3 identifier, e.g. "8860145b49fffff")
h3_res9           : string (15-character hexadecimal H3 identifier, e.g. "8960145b483ffff")
h3_res10          : string (15-character hexadecimal H3 identifier, e.g. "8a60145b4807fff")
```

### Cell Uniqueness & Coverage Metrics in BBMP (717.21 km²)

| Resolution | Unique Cells in BBMP | Mean POIs / Cell | Median POIs / Cell | Max POIs / Cell (Peak Hotspot) | Null Cell Count |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Res 8** | **996** | 247.85 | 114 | **3,198** (Central Commercial Core) | **0** |
| **Res 9** | **6,042** | 40.86 | 17 | **1,023** (Chickpet / City Market) | **0** |
| **Res 10** | **29,902** | 8.26 | 4 | **341** (Commercial Arcade Hub) | **0** |

---

## 4. Deterministic Canonical Identifier Strategy

To prevent identifier drift across pipeline executions and eliminate cross-source key collision risks:
1. **Algorithm:** UUIDv5 (RFC 4122 namespace-based SHA-1 hashing).
2. **Namespace URI:** `https://poi.conflation.in` (using `uuid.NAMESPACE_URL`).
3. **Format:** `uuid5(NAMESPACE_URL, f"https://poi.conflation.in/{source.lower()}/{source_record_id}")`
4. **Properties:**
   - **Deterministic:** Repeated execution on identical source records produces byte-for-byte identical UUID strings.
   - **Cross-Source Separation:** If both OSM and Overture share an identical numeric ID (e.g. `12345`), the source prefix guarantees strictly distinct UUIDs.
   - **Lossless Traceability:** The original `poi_source` and `source_record_id` remain explicit first-class columns.

---

## 5. Performance and Resource Metrics

Spatial indexing execution benchmarks on Apple M3 (8 GB RAM):

| Processing Phase | Method | Execution Duration | Throughput |
| :--- | :--- | :--- | :--- |
| **Parquet Ingestion** | PyArrow Columnar Read | 0.16 s | 1,540,000 rows/s |
| **UUIDv5 + H3 Res 8/9/10 Indexing** | Python 3.12 + `h3-py` C-extension | 0.99 s | 249,300 rows/s |
| **Table Construction & Verification** | PyArrow Array Zero-Copy Assembly | 0.06 s | 4,110,000 rows/s |
| **Parquet ZSTD Export** | PyArrow Parquet Writer | 0.38 s | 650,000 rows/s |
| **Total End-to-End Indexing** | Master Runner Pipeline | **1.59 s** | **155,200 rows/s** |
