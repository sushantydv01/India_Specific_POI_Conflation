# Milestone 18: Review Queue Prioritization & Backlog Intelligence

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Target Backlog:** 2,842 Unresolved Candidate Pairs & 1,029 Review Edges  
**Status:** Formal Review Prioritization Report  

---

## 1. Executive Summary

During canonical POI resolution, ambiguous star components, multi-node complex clusters, uncertain model scores, and safeguard intercepts are safely isolated rather than forced into erroneous automated merges. In Milestone 17.1, exactly **2,842 candidate pairs** were held as unresolved pairs in `data/processed/canonical/unresolved_pairs.parquet`.

To maximize the ROI of human annotation, this milestone implements an explainable multi-signal prioritization formula that ranks every unresolved item into four actionable tiers (`P1_CRITICAL`, `P2_HIGH`, `P3_MEDIUM`, `P4_LOW`).

---

## 2. Explainable Prioritization Methodology

Every unresolved pair is scored on a 100-point composite priority scale based on five objective signals:
1. **Decision Threshold Proximity (0 to 30 pts):** Pairs with model scores closest to the 0.55 decision threshold have the highest information value and uncertainty.
2. **Graph Component Complexity (0 to 25 pts):** Resolving multi-node clusters (e.g. 20 OSM vs. 19 Overture) or ambiguous stars unblocks entire clusters of physical entities.
3. **Domain Safeguard Triggers (0 to 20 pts):** Pairs flagged by `SHARED_HONORIFIC_DISJOINT_BRAND`, `ATM_VS_BANK`, or `PARENT_CHILD`.
4. **Spatial Boundary Displacement (0 to 15 pts):** Pairs located within the 15m–45m entrance-to-centroid perimeter.
5. **Category Discrepancy (0 to 10 pts):** Cross-category candidate pairs requiring domain validation.

---

## 3. Backlog Distribution Across Priority Tiers

| Priority Tier | Candidate Pair Count | Percentage | Mean Priority Score | Mean Model Score | Action Guideline |
|:---|:---:|:---:|:---:|:---:|:---|
| **`P3_MEDIUM`** | **2,123** | 74.7% | 45.63 / 100 | 0.8027 | Secondary verification queue (lower topological impact) |
| **`P4_LOW`** | **367** | 12.91% | 34.59 / 100 | 0.7743 | Subordinated star edges; verify only if primary winners rejected |
| **`P2_HIGH`** | **323** | 11.37% | 59.96 / 100 | 0.625 | Primary human review queue (boundary distance & ambiguous stars) |
| **`P1_CRITICAL`** | **29** | 1.02% | 74.86 / 100 | 0.5955 | Immediate senior human adjudication (high graph impact / boundary threshold) |

---

## 4. Top 10 Critical Priority Review Candidates (`P1_CRITICAL`)

| Rank | Pair ID | OSM Name | Overture Name | Score | Dist | Priority Explanation |
|:---:|:---|:---|:---|:---:|:---:|:---|
| **#1** | `way/766245127::e8172f23-3f50-4114-9146-8a04296ad604` | Assumption English High School | Assumption English School | 0.5556 | 21.3m | Score 0.5556 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 21.3m; Cross-category: education vs other |
| **#2** | `node/1470553336::54abfb85-501b-42c0-9380-762f8ea4e19a` | Srinivasa Cool Corner | Srinivasa and Company | 0.558 | 24.1m | Score 0.5580 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 24.1m; Cross-category: sustenance vs commercial_services |
| **#3** | `node/10124399183::5217dde4-d686-4d54-b2a6-8975d20c6281` | Karnataka State Medicinal Plants Authority | Karnataka State Forest Industries Corporation | 0.5595 | 27.8m | Score 0.5595 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 27.8m; Cross-category: commercial_services vs civic_religious |
| **#4** | `way/1106402205::f7aa7d9b-6353-448c-b087-55cb67aec0d5` | Karnataka Forest Department | Karnataka Medicinal Plants Authority | 0.5665 | 25.8m | Score 0.5665 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 25.8m; Cross-category: commercial_services vs civic_religious |
| **#5** | `node/4843104322::7478a6bf-d06c-4771-856f-9c90eda85189` | Alfa fried and Grill | Alfa Residence Lodge | 0.5668 | 27.8m | Score 0.5668 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 27.8m; Cross-category: sustenance vs hospitality |
| **#6** | `way/1249829840::18087439-162b-4f58-bfa1-882008dc0217` | CSI Christha Krupalaya Church | Christa Krupalaya Church | 0.5828 | 30.0m | Score 0.5828 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 30.0m; Cross-category: civic_religious vs other |
| **#7** | `way/1249829840::75e62b6c-4586-495c-a491-f0609571ff1d` | CSI Christha Krupalaya Church | Christa Krupalaya Church | 0.5828 | 30.0m | Score 0.5828 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 30.0m; Cross-category: civic_religious vs other |
| **#8** | `node/12487949148::1abdaa0d-2a17-40e6-ad8d-502898475894` | Brigade Luxury Spa * Salon | Brigade Royale | 0.5942 | 28.8m | Score 0.5942 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 28.8m; Cross-category: retail vs hospitality |
| **#9** | `node/12487949149::1abdaa0d-2a17-40e6-ad8d-502898475894` | Brigade Dine Cafe | Brigade Royale | 0.5942 | 23.5m | Score 0.5942 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 23.5m; Cross-category: sustenance vs hospitality |
| **#10** | `way/1551567993::412f2da4-84a8-4348-b6ce-d6a3ec145066` | Sacred Heart Boys School | Sacred Heart Church | 0.5942 | 28.5m | Score 0.5942 near decision boundary (0.55); Complex multi-node component impact; Boundary distance 28.5m; Cross-category: education vs other |

---

## 5. Deliverables & Structured Exports

The prioritized queue is exported to two production formats in `data/processed/review/`:
1. **Parquet Export:** [`data/processed/review/prioritized_unresolved_queue.parquet`](file://data/processed/review/prioritized_unresolved_queue.parquet) (Snappy compression, 2,842 records)
2. **CSV Export:** [`data/processed/review/prioritized_unresolved_queue.csv`](file://data/processed/review/prioritized_unresolved_queue.csv) (Complete human-readable metadata, scores, and explanations)