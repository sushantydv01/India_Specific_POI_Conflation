# Exploratory Data Analysis Report: Bengaluru POI Conflation Benchmark

**Scope:** Bruhat Bengaluru Mahanagara Palike (BBMP), Karnataka, India ($717.21\text{ km}^2$)  
**Dataset:** `data/processed/canonical_pois_h3.parquet` (**246,856 total records**)  
**Artifacts Generated:** `reports/eda_summary.json`, `reports/spatial_proximity_summary.json`, `reports/figures/*.png`  
**Date:** 2026-11-17

---

## 1. Executive Summary

This exploratory data analysis establishes the empirical baselines required for entity resolution across **197,820 Overture Places** and **49,036 OpenStreetMap POIs** strictly contained within the official BBMP municipal boundary.

### Key Analytical Findings

1. **Volume and Density Imbalance:**
   - Overture provides **4.03× more total records** than OpenStreetMap across Bengaluru.
   - However, in dense historical commercial districts (e.g. Chickpet, Shivajinagar, Gandhi Nagar), OSM density rivals Overture, with high micro-spatial accuracy for civic institutions and local retail.
2. **Naming Completeness & Script Divergence:**
   - **Overture:** 100% of records carry a primary name, but **99.83% are in Latin/English script**. Only 400 records (0.20%) contain native Kannada script.
   - **OpenStreetMap:** 71.10% (34,865) of POIs have explicit names. Of these, **6,223 records (12.69%) contain Kannada script** (`name:kn`), with 6,190 being fully bilingual.
3. **The Spatial Proximity Reality (The "Near $\ne$ Same" Principle):**
   - At a 50-meter threshold, **42,941 OSM records (87.57%)** have at least one nearby Overture record, generating **620,892 candidate pairs** (average 14.46 candidates per matched OSM record).
   - Lexical similarity evaluation on candidate pairs within 50m reveals a **mean Jaccard token similarity of only 0.051**, and **93.87% of nearby pairs exhibit Jaccard similarity $< 0.30$**.
   - **Core Conclusion:** In dense Indian urban environments, physical proximity alone is an effective candidate generator (reducing 9.7 billion pairs to 620k), but is completely insufficient as an identity proof. High-density commercial clusters house dozens of distinct businesses within a 25m radius.

---

## 2. Source-Level Statistical Baseline

All figures reflect exact query outputs over `data/processed/canonical_pois_h3.parquet`:

| Metric | OpenStreetMap (OSM) | Overture Maps Foundation | Unified Benchmark |
| :--- | :---: | :---: | :---: |
| **Total Record Count** | **49,036** (19.86%) | **197,820** (80.14%) | **246,856** (100.0%) |
| **Named Records** | 34,865 (71.10%) | 197,820 (100.0%) | 232,685 (94.26%) |
| **Missing / Null Names** | 14,171 (28.90%) | 0 (0.00%) | 14,171 (5.74%) |
| **Unique Name Strings** | 22,965 | 149,437 | 169,321 |
| **Duplicate Name Ratio** | 34.13% | 24.31% | 27.23% |
| **Missing Coordinates** | **0** (0.00%) | **0** (0.00%) | **0** (0.00%) |
| **Address Text Completeness** | 24,785 (50.54%) | 183,565 (92.79%) | 208,350 (84.40%) |
| **Standardized 6-Digit PIN Code** | 7,651 (15.60%) | 175,702 (88.82%) | 183,353 (74.28%) |
| **Phone Number Availability** | 5,594 (11.41%) | 60,650 (30.66%) | 66,244 (26.84%) |
| **Website / Social URL** | 4,244 (8.65%) | 49,617 (25.08%) | 53,861 (21.82%) |
| **Confidence Metric Availability** | 1.0 (Curated Baseline) | Mean: 0.771, Median: 0.810 | Range: [0.10, 1.00] |

---

## 3. Canonical Category Distribution

Every POI was classified into one of ten standardized canonical categories:

| Canonical Category | Total Count | Overture Count | OSM Count | Overture % | OSM % | Overture / OSM Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `other` (Unclassified / General) | 105,128 | 97,949 | 7,179 | 49.51% | 14.64% | 13.64 |
| `retail` | 47,625 | 32,875 | 14,750 | 16.62% | 30.08% | 2.23 |
| `sustenance` | 23,460 | 16,929 | 6,531 | 8.56% | 13.32% | 2.59 |
| `commercial_services` | 21,920 | 18,217 | 3,703 | 9.21% | 7.55% | 4.92 |
| `financial` | 9,811 | 6,692 | 3,119 | 3.38% | 6.36% | 2.15 |
| `leisure_tourism` | 8,601 | 5,142 | 3,459 | 2.60% | 7.05% | 1.49 |
| `hospitality` | 8,014 | 6,368 | 1,646 | 3.22% | 3.36% | 3.87 |
| `healthcare` | 8,004 | 4,965 | 3,039 | 2.51% | 6.20% | 1.63 |
| `education` | 7,706 | 4,772 | 2,934 | 2.41% | 5.98% | 1.63 |
| `civic_religious` | 6,587 | 3,911 | 2,676 | 1.98% | 5.46% | 1.46 |
| **Total** | **246,856** | **197,820** | **49,036** | **100.0%** | **100.0%** | **4.03** |

![Category Distribution](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/figures/category_distribution_comparison.png)

---

## 4. Attribute Completeness Matrix

Field-by-field completeness across both providers:

| Attribute | OSM Completeness (%) | Overture Completeness (%) | Conflation Analytical Utility |
| :--- | :---: | :---: | :--- |
| `name_original` | 71.10% | 100.00% | Primary lexical linkage key. |
| `name_normalized` | 71.10% | 100.00% | Token-matching and index blocking key. |
| `alternate_names` | 13.23% | 16.63% | Secondary alias and translation matching. |
| `name_en` | 65.55% | 0.00% | Explicit English tag (present in OSM). |
| `name_kn` | 12.69% | 0.00% | Kannada native script matching. |
| `category_normalized` | 100.00% | 100.00% | Coarse semantic filtering and blocking. |
| `address_original` | 13.14% | 92.79% | Freeform text address similarity. |
| `address_locality` | 50.40% | 90.07% | Suburb / neighborhood blocking. |
| `address_postcode` | 15.60% | 88.82% | 6-digit postal code blocking. |
| `phone` | 11.41% | 30.66% | Deterministic high-precision exact match key. |
| `website` | 8.65% | 25.08% | Exact domain linkage key. |
| `confidence` | 100.00% (1.0 baseline) | 99.85% | Probabilistic match weighting feature. |
| `source_timestamp` | 100.00% | 0.00% | Temporal freshness ranking. |

![Attribute Completeness](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/figures/attribute_completeness_matrix.png)

---

## 5. Spatial Density Hotspots (H3 Resolution 8)

The top commercial and retail clusters in Bengaluru identified by POI density per H3 cell (~$0.74\text{ km}^2$):

| Rank | H3 Cell Res 8 | Est. Locality / Landmark | Total POIs | Overture POIs | OSM POIs | Ov / OSM Ratio |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | `8860145b49fffff` | Chickpet / Majestic / Gandhi Nagar | **3,198** | 2,341 | 857 | 2.73 |
| 2 | `8860145b43fffff` | Shivaji Nagar / Commercial Street | **2,864** | 2,189 | 675 | 3.24 |
| 3 | `8860145941fffff` | Koramangala 5th & 6th Blocks | **2,478** | 2,012 | 466 | 4.32 |
| 4 | `8860145a27fffff` | Indiranagar 100 Feet Rd & CMH Rd | **2,351** | 1,894 | 457 | 4.14 |
| 5 | `8860145b5bfffff` | Jayanagar 4th Block Complex | **2,190** | 1,745 | 445 | 3.92 |
| 6 | `8860145829fffff` | Whitefield / ITPL Main Rd | **1,985** | 1,672 | 313 | 5.34 |
| 7 | `8860145959fffff` | HSR Layout 27th Main | **1,942** | 1,620 | 322 | 5.03 |
| 8 | `8860145b03fffff` | Malleshwaram 8th Cross / Sampige Rd | **1,876** | 1,468 | 408 | 3.60 |
| 9 | `8860145837fffff` | Marathahalli Outer Ring Road | **1,784** | 1,510 | 274 | 5.51 |
| 10 | `8860145b69fffff` | JP Nagar 24th Main | **1,692** | 1,418 | 274 | 5.18 |

![Density Hotspots](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/figures/h3_res8_density_hotspots.png)

---

## 6. Cross-Source Spatial Proximity Analysis

To measure spatial candidate coverage without materializing the 9.7 billion cross-product, projected metric distances in UTM 43N (EPSG:32643) were evaluated across five standard candidate radii:

| Radius Threshold | Total Candidate Pairs | OSM Records with $\ge 1$ Candidate | OSM Reachability (%) | Overture Records with $\ge 1$ Candidate | Overture Reachability (%) | Avg Candidates / Matched OSM | Median Candidates | Max Candidates (Peak Cluster) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$\le 10\text{ m}$** | 46,568 | 19,902 | 40.59% | 29,848 | 15.09% | 2.34 | 2.0 | 41 |
| **$\le 25\text{ m}$** | 201,891 | 34,304 | 69.96% | 71,998 | 36.40% | 5.89 | 4.0 | 957 |
| **$\le 50\text{ m}$** | **620,892** | **42,941** | **87.57%** | **114,821** | **58.04%** | **14.46** | **9.0** | **969** |
| **$\le 100\text{ m}$** | 1,816,159 | 47,437 | 96.74% | 157,831 | 79.79% | 38.29 | 25.0 | 1,337 |
| **$\le 200\text{ m}$** | 5,492,994 | 48,819 | 99.56% | 186,638 | 94.35% | 112.52 | 83.0 | 1,533 |

![Proximity Distribution](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/figures/cross_source_proximity_candidate_distribution.png)
![Distance Histogram](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/figures/distance_distribution_nearby_pairs.png)

### Distance Distribution within 200m Window
- Minimum Distance: $0.0\text{ m}$
- 10th Percentile ($p_{10}$): $46.31\text{ m}$
- 25th Percentile ($p_{25}$): $83.47\text{ m}$
- **50th Percentile (Median):** **$130.29\text{ m}$**
- 75th Percentile ($p_{75}$): $167.77\text{ m}$
- 90th Percentile ($p_{90}$): $187.61\text{ m}$
- Mean Distance: $123.18\text{ m}$ (Standard Deviation: $51.76\text{ m}$)

### Why Spatial Proximity Alone Fails as Identity Proof
Inspection of real candidate pairs within a $50\text{m}$ radius demonstrates the high prevalence of **spatial noise** (distinct independent businesses operating in immediate physical proximity):

| OSM Feature | Overture Candidate | Metric Distance | Token Set Ratio | Physical Reality |
| :--- | :--- | :---: | :---: | :--- |
| `Udupi Grand` | `Sobha PalmCourt` | $42.95\text{ m}$ | 0.15 | Restaurant situated across from an apartment entrance. Distinct entities. |
| `Motherhood Whitefield` | `Cafezinho` | $41.82\text{ m}$ | 0.20 | Hospital located adjacent to a cafe. Distinct entities. |
| `Karnataka State Ag. Corp` | `ACO India` | $48.77\text{ m}$ | 0.18 | Government office and private engineering office in same commercial park. |

Conversely, true positive matches often exhibit minor coordinate displacements ($10\text{m}–35\text{m}$) due to building centroids versus entrance markers:
* `Christ the King Public School` $\leftrightarrow$ `Christ The King Public School` ($9.67\text{ m}$, ratio 1.0)
* `Apollo Cradle` $\leftrightarrow$ `Apollo Cradle Hospital` ($24.52\text{ m}$, ratio 1.0)
* `Udupi Grand` $\leftrightarrow$ `Udapi grand` ($24.87\text{ m}$, ratio 0.91, phonetic variant).
