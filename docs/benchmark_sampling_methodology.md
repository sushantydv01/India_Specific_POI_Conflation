# POI Benchmark Sampling Methodology & Stratification Architecture

This document specifies the mathematical formulation, partitioning logic, and inclusion-probability methodology for the **India-Specific POI Conflation** benchmark across Bruhat Bengaluru Mahanagara Palike (BBMP), Bengaluru, India.

---

## 1. Audit of Initial Sampling Design & Resolution

### The Overlap Problem in Naive Stratified Queries
In naive multi-attribute sampling, selecting subsets using independent query filters causes **stratum overlap**:
* A candidate pair possessing native Kannada script (`KANNADA_TRANSLITERATION`) may also have a metric distance $> 50$m (`LARGE_DISTANCE_CANDIDATES`), multiple blocking strategies (`MULTI_STRATEGY_OVERLAP`), and a category overlap (`CATEGORY_ADJACENCY`).
* If population sizes are counted independently per query filter:
  $$\sum_{k=1}^{K} N_k^{\text{query}} \gg N_{\text{Total}}$$
* Under overlapping stratum definitions, calculating inclusion probability as $\pi_i = n_k / N_k^{\text{query}}$ is mathematically invalid because a candidate's actual selection probability depends on the union of probabilities across all qualifying strata.

---

## 2. Mutually Exclusive Priority Stratification Architecture

To establish well-defined inclusion probabilities, the candidate universe of **605,428 pairs** is partitioned into **10 mutually exclusive primary strata** using a deterministic, documented priority hierarchy:

```mermaid
flowchart TD
    Universe[605,428 Candidate Pairs] --> P1{1. Kannada Script?<br/>[ಀ-೿] or Transliteration}
    P1 -->|Yes| S1[1. KANNADA_TRANSLITERATION<br/>N = 86,537]
    P1 -->|No| P2{2. Phonetic Variant Tokens?<br/>Sri, Udupi, Bhavan, etc.}
    
    P2 -->|Yes| S2[2. PHONETIC_VARIANTS<br/>N = 31,065]
    P2 -->|No| P3{3. Distance > 50m?<br/>Long-distance non-spatial}
    
    P3 -->|Yes| S3[3. LARGE_DISTANCE_CANDIDATES<br/>N = 4,102]
    P3 -->|No| P4{4. Exact Name Match?<br/>Normalized name equality}
    
    P4 -->|Yes| S4[4. EXACT_NAME_MATCH<br/>N = 3,488]
    P4 -->|No| P5{5. Multi-Strategy Overlap?<br/>>= 2 independent strategies}
    
    P5 -->|Yes| S5[5. MULTI_STRATEGY_OVERLAP<br/>N = 2,954]
    P5 -->|No| P6{6. Category Adjacency?<br/>POTENTIALLY_COMPATIBLE}
    
    P6 -->|Yes| S6[6. CATEGORY_ADJACENCY<br/>N = 140,685]
    P6 -->|No| P7{7. Name Missing or Short?<br/>Null or <= 3 characters}
    
    P7 -->|Yes| S7[7. MISSING_OR_GENERIC_NAME<br/>N = 73,377]
    P7 -->|No| P8{8. Close Spatial Distinct?<br/>Dist <= 15m, distinct names}
    
    P8 -->|Yes| S8[8. CLOSE_SPATIAL_DISTINCT_NAMES<br/>N = 39,550]
    P8 -->|No| P9{9. High-Density Hotspot?<br/>Top 5 H3 Res 9 cells}
    
    P9 -->|Yes| S9[9. HIGH_DENSITY_HOTSPOTS<br/>N = 18,005]
    P9 -->|No| S10[10. SPATIAL_CLUSTER_RESIDUAL<br/>N = 205,665]
```

### Mathematical Properties of the Partition
1. **Exhaustive Partition:** Every candidate pair belongs to exactly one stratum:
   $$\bigcup_{k=1}^{10} S_k = \text{Candidates}, \quad S_i \cap S_j = \emptyset \quad \forall i \ne j$$
   $$\sum_{k=1}^{10} |S_k| = 86{,}537 + 31{,}065 + 4{,}102 + 3{,}488 + 2{,}954 + 140{,}685 + 73{,}377 + 39{,}550 + 18{,}005 + 205{,}665 = \mathbf{605{,}428}$$
2. **Exact Inclusion Probabilities:** For each stratum $k$, taking a simple random sample of $n_k = 50$ pairs without replacement yields exact inclusion probabilities:
   $$\pi_i = P(p_i \in \text{sample} \mid p_i \in S_k) = \frac{n_k}{N_k}$$
3. **Horvitz-Thompson Sampling Weights:** Each sampled pair represents $w_k = 1/\pi_k$ candidate pairs in the candidate universe.

---

## 3. Stratum Population and Sample Parameter Table

The parameters derived from [reports/benchmark_sampling_report.json](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/benchmark_sampling_report.json) are detailed below:

| Primary Stratum | Population ($N_k$) | Universe Share (%) | Sample Size ($n_k$) | Inclusion Prob ($\pi_k$) | Sampling Weight ($w_k$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`KANNADA_TRANSLITERATION`** | 86,537 | 14.29% | 50 | 0.000578 | 1,730.74 |
| **`PHONETIC_VARIANTS`** | 31,065 | 5.13% | 50 | 0.001610 | 621.30 |
| **`LARGE_DISTANCE_CANDIDATES`** | 4,102 | 0.68% | 50 | 0.012189 | 82.04 |
| **`EXACT_NAME_MATCH`** | 3,488 | 0.58% | 50 | 0.014335 | 69.76 |
| **`MULTI_STRATEGY_OVERLAP`** | 2,954 | 0.49% | 50 | 0.016926 | 59.08 |
| **`CATEGORY_ADJACENCY`** | 140,685 | 23.24% | 50 | 0.000355 | 2,813.70 |
| **`MISSING_OR_GENERIC_NAME`** | 73,377 | 12.12% | 50 | 0.000681 | 1,467.54 |
| **`CLOSE_SPATIAL_DISTINCT_NAMES`**| 39,550 | 6.53% | 50 | 0.001264 | 791.00 |
| **`HIGH_DENSITY_HOTSPOTS`** | 18,005 | 2.97% | 50 | 0.002777 | 360.10 |
| **`SPATIAL_CLUSTER_RESIDUAL`** | 205,665 | 33.97% | 50 | 0.000243 | 4,113.30 |
| **Total** | **605,428** | **100.00%** | **500** | — | — |

---

## 4. Methodological Distinction of Sample Types

It is critical to distinguish between three fundamentally different types of evaluation samples:

1. **Diagnostic Difficulty-Stratified Sample (Our 500-pair Queue):**
   - **Purpose:** Stress-test entity resolution algorithms against known hard matching archetypes (vernacular transliteration, phonetic shifts, co-located distinct shops, large distance displacements).
   - **Properties:** Equal allocation ($n_k = 50$) intentionally oversamples rare failure modes (e.g., exact matches at large distances) relative to baseline spatial clusters.
   - **Limitation:** Raw accuracy on this sample **cannot** be reported as the global model accuracy across natural data.
2. **Probability Sample for Population Estimates:**
   - **Purpose:** Provide mathematically unbiased estimates of population precision, recall, and F1 across the 605,428 candidate universe.
   - **Properties:** Requires Horvitz-Thompson estimation weighting each sample by $w_k = N_k / n_k$.
3. **Naturally Distributed Evaluation Sample:**
   - **Purpose:** Reflect the raw, unstratified prevalence where non-matches vastly outnumber matches ($>95\%$ negative class).
