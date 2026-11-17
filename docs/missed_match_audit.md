# Missed-Match Diagnostic Audit & Recall Methodology

This document details the independent search methodology, sampling design, and empirical findings of the **Missed-Match Diagnostic Audit** conducted as part of Milestone 5 of the **India-Specific POI Conflation** project.

---

## 1. Why Candidate Blocking Alone Cannot Measure Recall

A common methodological fallacy in record linkage literature is evaluating blocking quality strictly from generated candidate pairs:

$$\text{Candidate Set } C \subset (N_{\text{OSM}} \times N_{\text{OVERTURE}})$$

If a human annotates pairs sampled exclusively from $C$, the true positive rate among those pairs measures **candidate precision**, not **candidate recall**. True matches that were completely discarded by the blocking pipeline cannot be labelled from $C$.

To diagnose candidate-generation blind spots, an **independent search procedure** must be executed that deliberately departs from the blocking engine's assumptions.

---

## 2. Independent Search Methodology

The audit inspects a diagnostic sample of **120 OpenStreetMap records** that were unrepresented or weakly represented in the candidate generation pool.

For each audited OSM POI, an independent search against Overture Places was executed:
1. **Radial Expansion to 1,500m:** The spatial search envelope was expanded from $50\text{m}$ to $1{,}500\text{m}$ ($30\times$ the blocking radius).
2. **Category-Unconstrained Search:** All category compatibility restrictions were eliminated, allowing cross-domain matching.
3. **Comprehensive Fuzzy Token Matching:** RapidFuzz `token_sort_ratio` and `partial_ratio` were evaluated against all Overture candidates within the 1.5 km envelope.

---

## 3. Sampling Design for Unrepresented Entities

The 120 audited entities were sampled across four distinct vulnerability strata:

| Audit Stratum | Count | Selection Rationale |
| :--- | :---: | :--- |
| **`ZERO_CANDIDATE_KANNADA`** | 30 | OSM records with zero candidates possessing native Kannada script (`name_kn` or Unicode `\u0C80`–`\u0CFF`). Tests transliteration failure modes. |
| **`ZERO_CANDIDATE_PERIPHERAL`** | 30 | OSM records with zero candidates located in outer municipal wards ($>12$km from city center). Tests geographic boundary coverage. |
| **`ZERO_CANDIDATE_INSTITUTION`** | 30 | OSM records with zero candidates in institutional domains (`education`, `healthcare`, `civic_religious`). Tests large campus centroid offsets. |
| **`WEAK_CANDIDATES_ONLY`** | 30 | OSM records with $\le 3$ candidate pairs, all with distance $>40$m and low lexical similarity. Tests low-confidence candidate quality. |

---

## 4. Empirical Audit Results

The empirical results from [reports/missed_match_audit_summary.json](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/missed_match_audit_summary.json) are summarized below:

```
Missed-Match Diagnostic Verdict Distribution (N = 120):
  NO_COUNTERPART_FOUND                          : [===================] 47 (39.2%)
  POTENTIAL_COUNTERPART_FOUND_OUTSIDE_BLOCKING  : [==========] 24 (20.0%)
  INSUFFICIENT_EVIDENCE                         : [====================] 49 (40.8%)
```

### Detailed Failure Mode Analysis

| Primary Failure Reason | Count | Percentage | Architectural Insight |
| :--- | :---: | :---: | :--- |
| **`SOURCE_COVERAGE_ABSENCE_IN_OVERTURE`** | **47** | **39.2%** | **True Data Absence:** The physical entity mapped by OSM community members (e.g., small local temple, municipal borewell, community hall) is completely absent from Overture's commercial directory data. No candidate blocker could ever find a match because the entity does not exist in the counterpart dataset. |
| **`SPATIAL_DISTANCE_DISPLACEMENT_EXCEEDED_50M`** | **24** | **20.0%** | **Blocking Recall Loss:** Genuine matching entities existed in Overture, but were displaced by **$55\text{m}$ to $820\text{m}$**. Typical examples include large engineering colleges (entrance gate in OSM vs admin building in Overture) or multi-acre hospital campuses. |
| **`NAME_MISSING_IN_OSM_OR_OVERTURE`** | **49** | **40.8%** | **Attribute Sparsity:** The OSM node was tagged with an amenity code (e.g., `amenity=school` or `amenity=place_of_worship`) but the `name` tag was completely blank or generic (e.g., "Shop"). Linking is impossible without external field surveys. |

---

## 5. Methodological Limitations

1. **Diagnostic Rather than Statistical Recall:** This audit provides an essential qualitative diagnostic of failure modes. It does **not** constitute a global statistically unbiased estimate of blocking recall across the entire 49,036 OSM universe because the sample was deliberately enriched with high-risk records.
2. **Centroid vs. Polygon Geometry:** Coordinate displacement beyond 50m in institutional campuses highlights the necessity of polygon-aware matching in future iterations rather than naive point centroid Euclidean distance.
