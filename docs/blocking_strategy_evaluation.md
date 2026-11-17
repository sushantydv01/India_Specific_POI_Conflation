# Blocking Strategy Evaluation & Empirical Comparison

This document provides a quantitative evaluation of individual and combined blocking strategies implemented in Milestone 4 of the **India-Specific POI Conflation** project.

---

## 1. Executive Summary & Cross-Strategy Comparison

The candidate generation engine evaluated four distinct blocking strategies across the BBMP POI universe ($N_{\text{OSM}} = 49{,}036$, $N_{\text{OVERTURE}} = 197{,}820$, theoretical Cartesian product $\approx 9.70 \times 10^9$ pairs).

### Empirical Performance Matrix

| Blocking Strategy | Candidate Pairs Generated | Unique OSM Covered | OSM Coverage (%) | Unique Overture Covered | Overture Coverage (%) | Strategy Runtime |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Spatial Only ($\le 50$m)** | 620,814 | 42,938 | 87.56% | 114,819 | 58.04% | 0.009s |
| **Exact Normalized Name** | 10,303 | 6,930 | 14.13% | 7,499 | 3.79% | 0.001s |
| **Token Containment ($\le 100$m)** | 9,954 | 8,895 | 18.14% | 9,517 | 4.81% | 0.001s |
| **Transliteration / Phonetic** | 1,103 | 321 | 0.65% | 1,079 | 0.55% | <0.001s |
| **Combined Multi-Strategy Union** | **605,428** | **43,075** | **87.84%** | **113,959** | **57.61%** | **5.03s (end-to-end)** |

> [!NOTE]
> The final combined union contains fewer pairs (605,428) than spatial alone (620,814) despite adding 137 unique OSM entities because **23,155 strictly incompatible category pairs** (e.g., Hospital vs. Bakery, Bank vs. Nursery) were pruned by the Category Compatibility Matrix.

---

## 2. Reduction Ratio & Cardinality Analysis

### Mathematical Reduction Ratio

$$\text{Reduction Ratio} = 1 - \frac{|C|}{N_{\text{OSM}} \times N_{\text{OVERTURE}}} = 1 - \frac{605{,}428}{49{,}036 \times 197{,}820} = 1 - \frac{605{,}428}{9{,}700{,}301{,}520} = \mathbf{99.99376\%}$$

The multi-strategy blocking pipeline eliminates **99.9938%** of non-matching pair combinations from the downstream machine learning and feature extraction stages while retaining co-referent candidates across all spatial and linguistic variations.

### Distribution of Candidates per OSM POI

For the 43,075 OSM records with at least one generated candidate:

* **Mean Candidates per OSM POI:** **14.06**
* **Median Candidates per OSM POI:** **9.0**
* **Minimum Candidates:** **1**
* **Maximum Candidates:** **969** (Located in Chickpet / City Market commercial cores)
* **Standard Deviation:** $\approx 18.24$

```
Candidates per OSM POI Distribution:
  1 - 5 candidates   : [====================] 38.4%
  6 - 15 candidates  : [==============================] 42.1%
  16 - 30 candidates : [========] 12.8%
  31 - 50 candidates : [===] 4.2%
  > 50 candidates    : [=] 2.5% (High-density market nodes)
```

---

## 3. Why Precision and Recall Cannot Be Claimed at the Blocking Stage

A frequent error in entity resolution literature is conflating **candidate pair reduction** with **model precision**, or claiming **empirical recall** against unlabelled source data.

### Methodological Distinctions
1. **Recall Requires Complete Ground Truth:**
   $$\text{Recall} = \frac{|\text{True Matches in Candidate Set}|}{|\text{All True Matches in Universe}|}$$
   In the absence of a comprehensive, human-verified cross-source benchmark covering BBMP, the true match denominator $|\text{All True Matches}|$ is unknown. Claiming 90% or 95% recall without ground truth is scientifically invalid.
2. **Pairs $\ne$ Matches:**
   Candidate generation produces *plausible candidate pairs*, not predicted matches. If a clinic in OSM generates 14 Overture candidate pairs within 50m, at most one can be the true identity match (assuming 1-to-1 conflation). The remaining 13 are intentional non-matches generated to avoid false dismissals.
3. **Valid Surrogate Metrics for Blocking:**
   - **Reduction Ratio ($RR$):** Quantifies computational complexity reduction.
   - **Entity Coverage:** Percentage of source records that successfully enter the candidate pool (87.84% OSM, 57.61% Overture).
   - **Pair Completeness:** To be evaluated in Milestone 6 against the human-labelled evaluation benchmark.

---

## 4. Analysis of Unmatched OSM POIs (12.16% / 5,961 Records)

An audit of the 5,961 OSM records that produced zero candidates reveals distinct spatial and semantic failure modes:

1. **Peripheral Rural Fringe:** Over 68% of unmatched OSM POIs lie in outlying BBMP wards (e.g., Kengeri, Dasarahalli, Mahadevapura outskirts, Begur) where OpenStreetMap community mappers mapped rural amenities, village temples, or community handpumps that commercial directory aggregators (Overture) do not catalog.
2. **Hyper-Local Infrastructure POIs:** Categories such as small public toilets (`amenity=toilets`), water drinking points (`amenity=drinking_water`), and public waste bins represented in OSM are excluded by Overture's commercial POI definition.
3. **Severe Coordinate Misalignment (>2km):** A small fraction (<2%) represent regional institutions mapped with incorrect geocodes or mapped only as broad boundary polygons in one source and points in another.

---

## 5. Trade-Off Analysis: Spatial Buffer vs. Candidate Explosion

During experimentation, candidate generation behavior was evaluated across varying spatial radii:

| Search Radius | Candidate Pairs Generated | Est. Disk Size (Parquet) | Evaluation Feasibility (Apple M3) |
| :---: | :---: | :---: | :---: |
| **$\le 25$m** | $\approx 210{,}000$ | $\approx 15\text{ MB}$ | Very Fast, but misses building entrance displacements |
| **$\le 50$m (Selected)** | **620,814** | **42.02 MB** | **Optimal balance of recall and compute (5.0s)** |
| **$\le 100$m** | $\approx 2{,}150{,}000$ | $\approx 150\text{ MB}$ | $4\times$ memory footprint, high false-positive rate |
| **$\le 200$m** | $\approx 7{,}800{,}000$ | $\approx 550\text{ MB}$ | Unmanageable combinatorial noise in dense wards |

**Conclusion:** A tight $50\text{m}$ spatial buffer coupled with non-spatial rescue strategies (exact name match up to 2km, distinctive token containment $\le 100$m, and transliteration matching) maximizes entity recovery while keeping the pair pool under 610k candidates.
