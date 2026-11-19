# Milestone 18: Benchmark Methodology & Evaluation Architecture

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** 2026-11-19  
**Status:** Approved Evaluation Architecture  

---

## 1. Objective & Research Integrity Principles

Milestone 18 shifts the project focus from pipeline engineering to rigorous scientific evaluation. The integrity of any POI conflation evaluation hinges upon the trustworthiness, transparency, and independence of its evaluation benchmark.

### Core Methodological Rules
1. **Zero AI Label Substitution:** Under no circumstances are AI-generated, AI-adopted, or rule-heuristic labels silently treated as human gold standard ground truth.
2. **Explicit Provenance Retention:** Every evaluation record preserves its immutable provenance metadata (annotator identities, timestamps, initial disagreement, and adjudication rationales).
3. **Dual Evaluation Views:** The system maintains two distinct evaluation perspectives:
   - **Representative View:** Reflects real-world candidate population characteristics across balanced strata.
   - **Challenge View:** Intentionally targets hard ambiguities (multilingual transliterations, dense clusters, boundary distances, and brand/branch conflicts). Performance on challenge sets is never misrepresented as population-level accuracy.
4. **Leakage-Isolated Splitting:** Partitions are strictly isolated by bipartite connected component ID and H3-7 spatial anchors.

---

## 2. Six-Tier Provenance Taxonomy

To avoid generic "ground truth" conflation, all evaluation labels are mapped to six explicit provenance categories:

```
[Candidate Pair Universe]
        │
        ├─► UNREVIEWED (605,328 universe pairs + 450 pool queue)
        │
        ├─► HEURISTIC (0 active; raw rule proposals)
        │
        ├─► AI_GENERATED (0 active in benchmark; 50 raw pilot suggestions)
        │
        ├─► AI_ADOPTED (49 pairs; heuristic proposals auto-adopted non-interactively)
        │
        └─► HUMAN GROUND TRUTH (51 pairs total)
                 │
                 ├─► HUMAN_REVIEWED (31 pairs; single human review)
                 │
                 └─► HUMAN_DUAL_REVIEWED (20 pairs; independent blind dual review)
                          │
                          ├─► Consensus Agreement (17 pairs)
                          └─► Senior Consensus Adjudication (3 pairs)
```

| Provenance Category | Record Count | Trust Level | Description |
|:---|:---:|:---:|:---|
| `HUMAN_DUAL_REVIEWED` | 20 | **Gold Standard (Highest)** | Independently annotated by two distinct human reviewers; conflicts adjudicated by senior adjudicator. |
| `HUMAN_REVIEWED` | 31 | **High Trust** | Verified by a single human reviewer without independent second review. |
| `AI_ADOPTED` | 49 | **Diagnostic Only** | Heuristic suggestions accepted via automated batch adoption (`ai_auto_adopter`). |
| `AI_GENERATED` | 0 | **Untrusted** | Raw AI suggestions without human or automated adoption. |
| `HEURISTIC` | 0 | **Untrusted** | Unverified rule outputs. |
| `UNREVIEWED` | 450 | **Unlabeled** | Stratified candidate queue items awaiting human review. |

---

## 3. Evaluation Datasets & Views

Evaluation is structured into four distinct dataset views (`data/processed/benchmark/evaluation_views/`):

### View A: Pure Gold Human Standard (`view_gold_human.parquet`, $N = 51$)
- **Composition:** 20 `HUMAN_DUAL_REVIEWED` + 31 `HUMAN_REVIEWED`.
- **Class Balance:** 44 MATCH, 7 NON_MATCH.
- **Purpose:** Authoritative ground-truth evaluation of baseline rules, supervised LightGBM model, and production safeguards.
- **Caveat:** Small sample size ($N = 51$) requires reporting Wilson score confidence intervals and prohibits claiming high-precision decimal F1 scores.

### View B: Consolidated Operational Benchmark (`view_consolidated_operational.parquet`, $N = 100$)
- **Composition:** 51 Human Ground Truth + 49 `AI_ADOPTED` pilot pairs.
- **Class Balance:** 53 MATCH, 39 NON_MATCH, 5 UNCERTAIN, 3 NEEDS_ADJUDICATION.
- **Binary Targets:** 92 binary pairs (53 positive, 39 negative).
- **Purpose:** Engineering benchmark used for model training, threshold sweeps, and sensitivity analysis, with explicit provenance filtering.

### View C: Challenge Evaluation View (`view_challenge_difficulty.parquet`, $N = 13$)
- **Composition:** Hard human-verified pairs satisfying at least one difficulty criterion:
  1. Distance $\ge 25$ meters.
  2. Disjoint or non-exact normalized names.
  3. Disputed pairs requiring senior adjudication.
- **Class Balance:** 10 MATCH, 3 NON_MATCH.
- **Purpose:** Stress-testing matcher robustness against spatial displacement and token variations.

### View D: Unreviewed Expansion Queue (`view_unreviewed_pool.parquet`, $N = 450$)
- **Composition:** 450 unannotated pairs across 10 strata.
- **Purpose:** Prioritized expansion pool for future human annotation campaigns.

---

## 4. Leakage Audit & Split Methodology

The benchmark pool was partitioned using component-blocked spatial hashing:
1. **Component Grouping:** All candidate edges belonging to the same connected component are assigned to the same partition.
2. **Spatial Anchoring:** POIs are anchored to Uber H3 Resolution 7 cells (~1.2 km radius).
3. **Verification Results:**
   - Pair-level overlap between train, validation, and test: **0 pairs**.
   - Connected component overlap between splits: **0 components**.
   - Test partition size: **81 total pairs** (18 binary labeled: 13 human-reviewed, 5 AI-adopted; 63 unannotated).

---

## 5. Structured Human-Review Expansion Plan

Given that only 51 pairs are genuinely human-reviewed, scaling the gold benchmark is essential. M18 produces a structured 450-pair expansion queue ([data/processed/benchmark/evaluation_views/view_unreviewed_pool.csv](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/data/processed/benchmark/evaluation_views/view_unreviewed_pool.csv)) stratified across 10 strata with priority ranking based on:
1. Spatial distance uncertainty (20m–50m).
2. Name similarity ambiguity (token sort ratio 0.50–0.80).
3. Transliteration / Indic script presence.
4. Model versus rule prediction discordance.
