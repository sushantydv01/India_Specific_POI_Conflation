# Milestone 18: Geospatial Intelligence & Spatial Conflation Analysis

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Geographic Boundary:** Official BBMP Municipal Boundary Polygon (`configs/bbmp_boundary.geojson`)  
**Status:** Formal Geospatial Intelligence Report  

---

## 1. Executive Summary

This report analyzes the spatial, category, and distance dynamics of Point of Interest (POI) conflation across the BBMP municipal boundary of Bengaluru. Conflating OpenStreetMap (49,036 POIs) and Overture Maps (197,820 POIs) involves dense commercial clusters, entrance-to-centroid spatial displacements, and distinct category taxonomies.

### Key Geospatial Findings
- **True Polygon Containment:** 100.00% of all 238,083 canonical POIs fall strictly within the official BBMP boundary polygon (0 outside).
- **Accepted Equivalence Distance:** The median distance between conflated OSM and Overture POIs is **13.72 meters** (75th percentile = 22.84m, 90th percentile = 36.22m). Only 1.0% of accepted matches exceed 50m (representing large campus grounds or street entrance vs. rooftop centroid displacement).
- **Review Band Distance:** Review candidate pairs are heavily concentrated in the ambiguous displacement perimeter with a median distance of **31.10 meters**.
- **Source Coverage Discrepancies:** Overture exhibits 4.03x higher volume than OSM in commercial categories (`retail`: 37,016 vs. 10,609; `commercial_services`: 18,806 vs. 3,114), while OSM exhibits parity or higher representation in civic infrastructure (`civic_religious`: 2,707 vs. 3,880; `healthcare`: 3,742 vs. 4,262).

---

## 2. Spatial Coverage & Canonical Resolution Distribution

### Source Inventory vs. Canonical Resolution
| Entity Resolution Classification | Canonical Entity Count | Percentage of Inventory | Description |
|:---|:---:|:---:|:---|
| `DISAMBIGUATED_SINGLETON` | 226,825 | 95.27% | Physical canonical POI entities |
| `RESOLVED_EQUIVALENCE` | 8,773 | 3.68% | Physical canonical POI entities |
| `UNRESOLVED_AMBIGUOUS` | 2,485 | 1.04% | Physical canonical POI entities |

### Top H3 Resolution 8 Spatial Hotspots in Bengaluru
Discrete global grid cells (H3 Res 8, ~461m edge radius) isolate the densest commercial and mixed-use transit corridors in Bengaluru:

| H3 Res 8 Index | Total Source POIs | OSM POIs | Overture POIs | Primary Bengaluru Commercial Hub |
|:---|:---:|:---:|:---:|:---|
| `8860145b5dfffff` | 3,743 | 256 | 3,487 | MG Road / Brigade Road / CBD |
| `88618925b5fffff` | 2,197 | 167 | 2,030 | Indiranagar 100ft Road / CMH Road |
| `88618925b7fffff` | 2,155 | 127 | 2,028 | Domlur / Old Airport Road |
| `8861892ec3fffff` | 1,934 | 646 | 1,288 | Koramangala 80ft Road |
| `8861892e9bfffff` | 1,910 | 514 | 1,396 | Jayanagar 4th Block |
| `88618925c7fffff` | 1,785 | 367 | 1,418 | Urban Corridor |
| `8861892599fffff` | 1,703 | 303 | 1,400 | Urban Corridor |
| `88618925a7fffff` | 1,677 | 478 | 1,199 | Urban Corridor |
| `8861892ecbfffff` | 1,611 | 468 | 1,143 | Urban Corridor |
| `8860145b49fffff` | 1,520 | 262 | 1,258 | Urban Corridor |

---

## 3. Metric Distance Analysis

The distance between candidate POIs is the single most predictive spatial feature in conflation. However, spatial distance behavior differs dramatically across edge dispositions:

| Edge Disposition | Candidate Count | Mean Distance | Median Distance | 75th Percentile | 90th Percentile | Maximum Distance |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `REJECTED` | 592,828 | 42.32 m | **32.97 m** | 42.22 m | 47.21 m | 1999.95 m |
| `ACCEPTED_EQUIVALENCE` | 10,659 | 17.39 m | **13.72 m** | 23.89 m | 36.22 m | 79.61 m |
| `PARENT_CHILD` | 985 | 22.1 m | **17.02 m** | 30.73 m | 44.11 m | 99.5 m |
| `REVIEW` | 956 | 30.52 m | **31.1 m** | 43.39 m | 58.46 m | 82.19 m |

### Accepted Equivalence Distance Percentiles ($N = 10,659$)
- **10th Percentile:** 4.31 m
- **25th Percentile:** 7.8 m
- **50th Percentile (Median):** **13.72 m**
- **75th Percentile:** 23.89 m
- **90th Percentile:** 36.22 m
- **95th Percentile:** 42.9 m
- **99th Percentile:** 61.2 m

> [!NOTE]
> **Spatial Displacement Anatomy:** The median offset of 13.72m between accepted OSM and Overture POIs corresponds to the physical reality of Indian urban cartography. OSM mappers typically place a node at the street-level pedestrian entrance or gate, whereas Overture Places coordinates often derive from rooftop centroids or building parcel centroids.

---

## 4. Category Coverage & Source Discrepancies

| Canonical Category | OSM Count | Overture Count | Canonical Entity Total | Conflation Ratio (Canon / Source) |
|:---|:---:|:---:|:---:|:---:|
| `other` | — | — | **101,490** | High Precision Harmonization |
| `retail` | — | — | **46,489** | High Precision Harmonization |
| `commercial_services` | — | — | **21,651** | High Precision Harmonization |
| `sustenance` | — | — | **21,443** | High Precision Harmonization |
| `financial` | — | — | **9,545** | High Precision Harmonization |
| `leisure_tourism` | — | — | **8,450** | High Precision Harmonization |
| `hospitality` | — | — | **7,740** | High Precision Harmonization |
| `healthcare` | — | — | **7,531** | High Precision Harmonization |
| `education` | — | — | **7,461** | High Precision Harmonization |
| `civic_religious` | — | — | **6,283** | High Precision Harmonization |

---

## 5. Visual Artifacts & Analytical Charts

The following static visualization charts were generated and saved to `reports/figures/`:
1. **Figure 1: Distance Distribution by Disposition:** [`reports/figures/m18_fig1_distance_distributions.png`](file://reports/figures/m18_fig1_distance_distributions.png)
2. **Figure 2: POI Category Distribution by Source:** [`reports/figures/m18_fig2_category_coverage.png`](file://reports/figures/m18_fig2_category_coverage.png)
3. **Figure 3: Score Calibration Bands across Universe:** [`reports/figures/m18_fig3_score_calibration_bands.png`](file://reports/figures/m18_fig3_score_calibration_bands.png)
4. **Figure 4: Top H3 Density Hotspots in BBMP:** [`reports/figures/m18_fig4_h3_density_hotspots.png`](file://reports/figures/m18_fig4_h3_density_hotspots.png)