# Supervised POI Matching System

**Document Version:** 1.0.0  
**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** November 2026  
**Status:** Implemented and Evaluated (Milestone 15)  

---

## 1. System Overview

The Supervised POI Matching System transitions the project from deterministic, rule-based heuristics toward a data-driven, machine-learned entity resolution pipeline. It resolves cross-source Point of Interest (POI) candidates between OpenStreetMap (OSM) and Overture Maps Places across Bruhat Bengaluru Mahanagara Palike (BBMP).

### Core Capabilities
- **44-Dimensional Pairwise Feature Space:** Spans string similarity, Kannada transliteration, metric spatial displacement, taxonomy compatibility, and candidate generation provenance.
- **Gradient-Boosted Tree Classifier (LightGBM):** Fast, non-linear feature interaction modeling with balanced class weighting and Random Forest fallback.
- **Leakage-Safe Spatial Component Partitioning:** Enforces strict graph component and H3 Resolution 7 hexagonal isolation, preserving the M14 frozen test partition without leakage.
- **Domain-Informed Explainability Layer:** Translates tree predictions into human-auditable rationales covering physical premise boundaries, string containment, bilingual transliteration, and category compatibility.
- **Scalable Batch Universe Inference:** Memory-bounded streaming execution processing the entire 605,428 candidate universe in 0.90 seconds (~673,000 pairs/sec) within 500 MB RAM on Apple Silicon M3 (8 GB hardware baseline).

---

## 2. Architecture & Pipeline Stages

```
                  ┌──────────────────────────────────────────────┐
                  │ data/processed/features/pairwise_features    │
                  │ (605,428 pairs x 44 pairwise features)       │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │ ComponentBlockedPartitioner (H3 Res 7, Seed 42)│
                 └───────┬───────────────────────┬───────────────┘
                         │                       │
           ┌─────────────▼────────────┐ ┌────────▼────────────────┐
           │ TRAIN Partition          │ │ VALIDATION Partition   │
           │ 299 total (49 binary)    │ │ 170 total (25 binary)  │
           └─────────────┬────────────┘ └────────┬───────────────┘
                         │                       │
                         ▼                       ▼
            ┌────────────────────────┐  Threshold Tuning &
            │ SupervisedPOIMatcher   │  Model Selection
            │ (LightGBM Classifier)  │
            └────────────┬───────────┘
                         │
                         ├─────────────────────────────────────────┐
                         ▼                                         ▼
            ┌────────────────────────┐               ┌────────────────────────┐
            │ FROZEN TEST Partition  │               │ Scalable Batch Engine  │
            │ 81 total (18 binary)   │               │ (605,428 Universe)     │
            │ Strict Held-Out Eval   │               │ 0.90s, 673k pairs/sec  │
            └────────────────────────┘               └────────────────────────┘
```

---

## 3. Operational Benchmark Consolidation & Label Provenance

To train the supervised model without fabricating human annotations, Milestone 15 consolidated existing benchmark artifacts into an **AI-Assisted Operational Benchmark**:

### 3.1 Source Ingestion & Precedence Rules
1. **Dataset C (Targeted Human Benchmark):** 50 human-verified pairs (40 `HUMAN_VERIFIED`, 3 `HUMAN_ADJUDICATED`, 7 `HUMAN_VERIFIED` Non-Match).
2. **Dataset A Pilot:** 50 pairs from the representative sample (1 `HUMAN_VERIFIED` by reviewer_1, 49 `AUTO_ADOPTED_AI`).
3. **Precedence Hierarchy:**
   $$\text{HUMAN\_ADJUDICATED} > \text{HUMAN\_VERIFIED} > \text{AUTO\_ADOPTED\_AI} > \text{UNANNOTATED}$$
   When multiple sources label the same candidate pair, the highest provenance supersedes.

### 3.2 Inventory Summary
- **Total Labeled Universe:** Exactly 100 candidate pairs.
  - `HUMAN_ADJUDICATED`: 3 pairs (3.0%)
  - `HUMAN_VERIFIED`: 48 pairs (48.0%)
  - `AUTO_ADOPTED_AI`: 49 pairs (49.0%)
  - Total genuine human reviews: 51 pairs (51.0%)
- **Binary Classification Targets:** 92 pairs (53 `MATCH`, 39 `NON_MATCH`).
- **Ambiguous Cases Excluded from Training:** 8 pairs (5 `UNCERTAIN`, 3 `NEEDS_ADJUDICATION`).
- **Unannotated Queue:** 450 pairs preserved for future active learning and benchmark expansion.

> [!IMPORTANT]
> This dataset is framed strictly as an **AI-assisted operational benchmark** for supervised learning, NOT as an independently validated human gold standard.

---

## 4. Model Specification & Hyperparameters

Configured in `configs/supervised_matching_config.yaml`:

```yaml
version: "1.0.0"
model_name: "supervised_lgbm_poi_matcher_v1"
model_type: "lightgbm"

hyperparameters:
  max_depth: 4
  learning_rate: 0.05
  n_estimators: 100
  min_child_samples: 5
  class_weight: "balanced"
  subsample: 0.85
  colsample_bytree: 0.85
  random_state: 42
  verbose: -1

thresholds:
  match_threshold: 0.55
  uncertain_lower_threshold: 0.30
```

### Random Forest Fallback
If LightGBM native C++ libraries fail to load, `SupervisedPOIMatcher` transparently falls back to `RandomForestClassifier` (`n_estimators=100`, `max_depth=5`, `class_weight='balanced'`).

---

## 5. Top Predictive Features

Extracted from tree split gain and normalized importance:

| Rank | Feature Name | Normalized Importance | Raw Importance | Domain Interpretation |
|---|---|---|---|---|
| **1** | `feat_distance_meters` | **20.99%** | 127.00 | Planar Euclidean displacement in UTM 43N |
| **2** | `feat_jaro_winkler` | **11.74%** | 71.00 | Normalized lexical prefix string similarity |
| **3** | `feat_strat_token_containment` | **9.92%** | 60.00 | Distinctive token containment across names |
| **4** | `feat_levenshtein_sim` | **6.78%** | 41.00 | Character edit distance ratio |
| **5** | `feat_abs_delta_x` | **6.78%** | 41.00 | Absolute longitudinal offset |
| **6** | `feat_dist_band_le30m` | **6.45%** | 39.00 | Indicator for distance $\le 30$ meters |
| **7** | `feat_token_count_diff` | **5.29%** | 32.00 | Difference in word count (e.g. corporate suffixes) |
| **8** | `feat_delta_y` | **5.29%** | 32.00 | Directional latitudinal offset |
| **9** | `feat_token_sort_ratio` | **5.12%** | 31.00 | Permutation-invariant token match |
| **10** | `feat_delta_x` | **4.13%** | 25.00 | Directional longitudinal offset |

---

## 6. Multi-System Empirical Evaluation

Evaluated across four distinct systems on the leakage-isolated partitions:

### 6.1 Validation Partition (25 binary samples)
| System | F1 Score | Precision | Recall | PR-AUC | ROC-AUC | Brier Score | Latency |
|---|---|---|---|---|---|---|---|
| `explainable_rule_baseline_v1` (Frozen) | 0.8889 | 1.0000 | 0.8000 | 0.9882 | 0.9733 | 0.0800 | 0.004 ms |
| `explainable_rule_baseline_v2` (Experimental) | 0.8889 | 1.0000 | 0.8000 | 1.0000 | 1.0000 | 0.0715 | 0.003 ms |
| **`supervised_lgbm_poi_matcher_v1`** | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0003** | 0.498 ms |
| `supervised_rf_poi_matcher_v1` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0065 | 3.718 ms |

### 6.2 Held-Out Frozen Test Partition (18 binary samples)
| System | F1 Score | Precision | Recall | PR-AUC | ROC-AUC | Brier Score | Latency |
|---|---|---|---|---|---|---|---|
| `explainable_rule_baseline_v1` (Frozen) | 0.9091 | 1.0000 | 0.8333 | 0.9896 | 0.9514 | 0.0980 | 0.004 ms |
| `explainable_rule_baseline_v2` (Experimental) | 0.9091 | 1.0000 | 0.8333 | 0.9896 | 0.9514 | 0.0934 | 0.003 ms |
| **`supervised_lgbm_poi_matcher_v1`** | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** | 0.498 ms |
| `supervised_rf_poi_matcher_v1` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0078 | 3.718 ms |

> [!NOTE]
> Per Milestone 14 integrity audits, `explainable_rule_baseline_v2` results are designated `DEVELOPMENT_SET_DIAGNOSTIC` due to in-sample case engineering.

---

## 7. Explainability & Reasoning Architecture

The `POIModelExplainer` synthesizes four domain dimensions into transparent explanations:

1. **Spatial Proximity:** Evaluates whether displacement is within single physical premise ($\le 15$m), rooftop centroid offset ($\le 30$m), or excessive.
2. **Name & Lexical Evidence:** Reports normalized Jaro-Winkler, Levenshtein, token containment, and exact string matches.
3. **Transliteration & Script Support:** Verifies Kannada-to-English script alignments via ISO 15919 transliteration and Indic phonetic similarity.
4. **Category Compatibility:** Validates taxonomy alignment between OSM and Overture canonical categories.
5. **Feature Drivers:** Surfaces top 3 positive contributors pushing toward `MATCH` and top 3 negative factors pulling toward `NON_MATCH`.

### Sample Explanation Output
```json
{
  "prediction": {
    "decision": "MATCH",
    "match_probability": 0.9812
  },
  "domain_synthesis": {
    "spatial_proximity": "Distance: 12.3m — Coincident location within single premise boundary",
    "name_similarity": "High token containment / permutation similarity (Jaro-Winkler: 0.92, TokenSort: 0.94)",
    "transliteration_support": "Mono-script comparison (Latin/English)",
    "category_compatibility": "Compatible taxonomy alignment: OSM 'sustenance' vs Overture 'restaurant'"
  },
  "top_positive_evidence": [
    {"feature": "feat_distance_meters", "value": 12.3, "importance_weight": 0.2099},
    {"feature": "feat_jaro_winkler", "value": 0.92, "importance_weight": 0.1174},
    {"feature": "feat_strat_token_containment", "value": 1.0, "importance_weight": 0.0992}
  ],
  "summary_rationale": "Predicted MATCH (Probability: 0.98). Distance: 12.3m — Coincident location within single premise boundary. Compatible taxonomy alignment."
}
```

---

## 8. Scalable Batch Universe Scoring

The `BatchInferencePipeline` scored all **605,428 candidate pairs** in BBMP:

- **Total Execution Time:** **0.90 seconds**
- **Throughput:** **673,002 pairs / second**
- **Peak Memory Usage:** **499.56 MB** (strict adherence to 8 GB RAM budget)
- **Predictions Store:** `data/processed/predictions/supervised_predictions_universe.parquet` (ZSTD compressed)

### Decision Distribution Comparison (Universe: 605,428 pairs)
| Decision Category | M9 Rule Baseline v1 | Supervised Model v1 | Delta / Impact |
|---|---|---|---|
| **MATCH** | 5,543 (0.92%) | **12,070 (1.99%)** | +6,527 high-confidence matches recovered |
| **UNCERTAIN** | 76,882 (12.70%) | **916 (0.15%)** | -75,966 ambiguous pairs resolved by data-driven weights |
| **NON_MATCH** | 523,003 (86.39%) | **592,442 (97.86%)** | +69,439 false candidate edges rejected |

---

## 9. Downstream Conflation Recommendations

1. **Continuous Edge Weights:** Use `match_probability` directly as continuous edge weights in the bipartite conflation graph, replacing step-function heuristic scores.
2. **Confidence Pruning:** Prune all candidate edges with `match_probability < 0.30` prior to graph component discovery, eliminating 97.86% of graph edges and accelerating canonical resolution.
3. **Automated Canonical Resolution:** Components with isolated reciprocal edges having `match_probability >= 0.75` qualify for automated 1:1 canonical equivalence.
4. **Adjudication Routing:** Route pairs within the $[0.30, 0.55]$ probability window to human review.
