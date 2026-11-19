# Milestone 18 Preflight: Evaluation Readiness & Ground Truth Reconnaissance

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** 2026-11-19  
**Repository State:** `ebbe2ab` (Clean working tree, 219 passing tests)  
**Document Goal:** Establish an honest audit of available evaluation datasets, label provenance, existing models, rule baselines, leakage vectors, and evaluation limitations before implementing M18 evaluation modules.

---

## 1. Inventory of Available Datasets & Record Counts

The repository contains multi-tiered data artifacts spanning raw sources, candidate pairs, features, benchmark annotations, supervised partitions, and production canonical outputs:

| Tier | Dataset Artifact | Format | Record Count | Description |
|:---|:---|:---:|:---:|:---|
| **Raw Sources** | `data/raw/osm/bengaluru_osm_pois.parquet` | Parquet | 49,036 | OSM POIs inside BBMP boundary |
| **Raw Sources** | `data/raw/overture/bengaluru_overture_places.parquet` | Parquet | 197,820 | Overture Places inside BBMP boundary |
| **Indexed Sources**| `data/processed/canonical_pois_h3.parquet` | Parquet | 246,856 | Unified normalized sources with H3 (Res 8, 9, 10) |
| **Candidate Universe** | `data/processed/candidate_pairs/candidate_pairs_union.parquet` | Parquet | 605,428 | Union of 4 blocking strategies ($\le 50$m, exact name, token containment, transliteration) |
| **Pairwise Features**| `data/processed/features/pairwise_features.parquet` | Parquet | 605,428 | 44-dimensional pairwise feature vectors |
| **Supervised Predictions**| `data/processed/predictions/supervised_predictions_universe.parquet` | Parquet | 605,428 | Match probability and decisions from LightGBM model |
| **Production Edges**| `data/processed/canonical/conflation_edges.parquet` | Parquet | 605,428 | Candidate edges with safeguards and final dispositions |
| **Canonical Inventory**| `data/processed/canonical/canonical_pois.parquet` | Parquet | 238,083 | Resolved canonical POI entities (100% source accounting) |
| **Relationships** | `data/processed/canonical/poi_relationships.parquet` | Parquet | 985 | Non-equivalence relationships (362 ATM, 420 parent-child, 203 campus) |
| **Unresolved Backlog**| `data/processed/canonical/unresolved_pairs.parquet` | Parquet | 2,842 | Unresolved candidate pairs (uncertain score band & complex multi-node components) |
| **Benchmark Pool** | `data/processed/benchmark/operational/operational_benchmark_full_pool.csv` | CSV | 550 | Stratified sampling pool (500 main queue + 50 pilot) |
| **Consolidated Benchmark**| `data/processed/benchmark/operational/operational_benchmark_consolidated.parquet` | Parquet | 100 | Active 100-pair operational benchmark (51 human + 49 AI-adopted) |
| **Human Gold V1** | `data/processed/benchmark/human_verified/benchmark_human_verified_v1.parquet` | Parquet | 50 | Dataset C: 47 human-verified + 3 human-adjudicated pairs |
| **Pilot AI Adopted** | `data/processed/benchmark/pilot_annotations_adopted.csv` | CSV | 50 | Dataset A Pilot: 49 auto-adopted AI + 1 legacy human pair |
| **Dual-Review QC** | `data/processed/benchmark/annotations/annotations_human_reviewer_2.csv` | CSV | 20 | Blind second-reviewer annotations on 20 pairs |
| **Adjudication Records**| `data/processed/benchmark/adjudicated/adjudication_records.jsonl` | JSONL | 3 | Senior adjudicator dispute resolutions |

---

## 2. Label Provenance & Reliability Audit

A rigorous evaluation requires tracing every label to its authoritative origin:

### Provenance Taxonomy
We map all benchmark annotations to six mutually exclusive, non-collapsible provenance tiers:

1. **`HUMAN_DUAL_REVIEWED` (20 pairs):**
   - Pairs independently reviewed by two distinct human annotators (`human_reviewer_1` and `human_reviewer_2`).
   - 17 pairs had complete agreement between reviewers.
   - 3 pairs had conflicting initial labels and were resolved via documented senior consensus adjudication (`adjudication_records.jsonl`).
   - Reliability: **Gold Standard (Highest Trust)**.
2. **`HUMAN_REVIEWED` (31 pairs):**
   - Pairs reviewed by a single human annotator (`human_reviewer_1` on 30 pairs, `reviewer_1` on 1 legacy pair).
   - Reliability: **High Trust**, but lacking independent inter-annotator corroboration.
3. **`AI_ADOPTED` (49 pairs):**
   - Pairs where heuristic rule suggestions (`heuristic_rule_v1`) were adopted non-interactively by an automated agent (`ai_auto_adopter`).
   - Reliability: **Medium / Synthetic**. Under research integrity requirements, these **must not** be conflated with human ground truth.
4. **`AI_GENERATED` (0 active in operational, 50 in raw suggestions):**
   - Raw model recommendations in `data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl`.
5. **`HEURISTIC` (0 active):**
   - Unreviewed deterministic heuristic rules.
6. **`UNREVIEWED` (450 in pool, 605,328 in candidate universe):**
   - Pairs in the candidate population and unannotated queue slots without ground truth labels.

### Ground Truth Summary
- **Pure Human Ground Truth:** **51 pairs** (20 dual-reviewed, 31 single-reviewed).
- **Consolidated Operational Benchmark:** **100 pairs** (51 human, 49 auto-adopted AI).
- **Unannotated Benchmark Queue:** **450 pairs**.

---

## 3. Existing Model & Baseline Artifacts

The repository contains three distinct decision-making engines:

1. **Explainable Rule Baseline V1 (`ExplainableMatchingEngine` in `src/poi_conflation/matching/engine.py`):**
   - Deterministic 5-factor weighted linear score with contradiction guardrails.
   - Outputs: Score $\in [0, 1]$, Classification (`MATCH`, `POSSIBLE_MATCH`, `UNCERTAIN`, `NO_MATCH`), transparent explanation notes.
   - Configuration: `configs/matching_baseline.yaml`.
2. **Explainable Rule Baseline V2 (`ExplainableMatchingEngineV2` in `src/poi_conflation/matching/engine_v2.py`):**
   - Optimized feature representation with corporate suffix normalization, token set ratio adjustments, and banking guardrails.
   - Reclassified as experimental diagnostic baseline (ADR-029).
3. **Supervised LightGBM Matcher (`SupervisedPOIMatcher` in `src/poi_conflation/matching/supervised_model.py`):**
   - Gradient-boosted decision tree classifier trained on 44 pairwise features.
   - Model artifact: `models/supervised_poi_matcher_v1.joblib` (Random Forest fallback: `supervised_rf_poi_matcher_v1.joblib`).
   - Hyperparameters: `max_depth=4`, `learning_rate=0.05`, `n_estimators=100`, `class_weight='balanced'`.
   - Thresholds: Match threshold = `0.55`, Uncertain threshold = `0.30`.
   - Native TreeSHAP attribution and 4-factor domain explainability.
4. **Production Pipeline Safeguards (`ConflationSafeguardValidator` in `src/poi_conflation/graph/safeguards.py`):**
   - Domain safeguards operating on candidate edges: `ATM_VS_BANK_FACILITY_DISTINCTION`, `PARENT_CHILD_CONTAINER`, `SAME_BRAND_DIFFERENT_BRANCH`, `GENERIC_NAME_COLLISION`, `SHARED_HONORIFIC_DISJOINT_BRAND`.
   - Dispositions: `ACCEPTED_EQUIVALENCE`, `PARENT_CHILD`, `REVIEW`, `REJECTED`.

---

## 4. Leakage Risks & Existing Split Analysis

### Existing Partitions
In Milestone 15, the 550-pair pool was partitioned into:
- **Train Partition (`train_partition.csv` / `train_features.parquet`):** 299 pairs (49 binary: 26 match, 23 non-match; 246 unannotated).
- **Validation Partition (`validation_partition.csv` / `validation_features.parquet`):** 170 pairs (25 binary: 15 match, 10 non-match; 145 unannotated).
- **Test Partition (`test_partition.csv` / `test_features.parquet`):** 81 pairs (18 binary: 12 match, 6 non-match; 63 unannotated).

### Leakage Audit Findings
1. **Pair-Level Disjointness:** Verified 0 pair ID overlaps between Train, Validation, and Test ($0$ shared pairs).
2. **Graph Component Disjointness:** Verified 0 shared `graph_component_id` values across splits ($0$ cross-split component leaks).
3. **Spatial Anchor Isolation:** Partitions were grouped by spatial H3-7 cells and connected components, preventing spatial proximity leakage.
4. **Small-Sample Bimodality on Test Set:**
   - The test partition contains only **18 binary labeled pairs**.
   - Of those 18 pairs, **13 pairs are human-verified** (11 matches, 2 non-matches) and **5 pairs are AI-adopted** (1 match, 4 non-matches).
   - All 11 human match pairs in the test set have near-identical names (*HDFC Bank*, *WeWork*, *MedPlus*, *Sweet Chariot*), while the non-matches have completely disjoint names (*Print IT Solutions* vs. *OM SAI RAM Garments*).
   - **Conclusion:** The previously reported $F_1 = 1.0000$ is a mathematical artifact of an extraordinarily small (18-sample), trivial bimodal test set. It does **not** reflect real-world population-level generalization.

---

## 5. What Can and Cannot Be Evaluated Honestly

### What CAN Be Evaluated Honestly:
1. **Model & Baseline Benchmark Metrics on Available Labeled Sets:**
   - We can evaluate Rule V1, Rule V2, and Supervised LightGBM across:
     - Pure Human Gold Standard ($N = 51$).
     - Consolidated Operational Benchmark ($N = 100$).
     - Held-out Test Split ($N = 18$ binary: 13 human, 5 AI-adopted).
   - For all evaluations, we must report exact counts, confusion matrices, and confidence intervals or small-sample warnings.
2. **Comparative Engine Differences:**
   - How Rule V1, Rule V2, and LightGBM agree or disagree on match decisions.
3. **Population-Level Matching Behavior ($N = 605,428$):**
   - Distribution of scores, score bands, and safeguard activations.
   - Score sensitivity and candidate distance relationships across all 10 canonical categories.
4. **True Geospatial Intelligence:**
   - BBMP spatial coverage, H3 spatial density, matched vs. unmatched geographic distribution, review-heavy ward hotspots.
5. **Indic Language & Transliteration Coverage:**
   - Kannada script prevalence, transliteration feature impact, and naming variations.
6. **Review Backlog Prioritization:**
   - Multi-factor ranking of the 1,029 review candidate edges and 2,842 unresolved graph pairs.

### What CANNOT Be Claimed Honestly:
1. **We CANNOT claim $F_1 = 1.0000$ is the true system accuracy for Bengaluru POI conflation.**
2. **We CANNOT report population-level precision and recall from a 18-sample test split.**
3. **We CANNOT treat the 49 AI-adopted pilot labels as gold human annotations.**
4. **We CANNOT claim high accuracy on Kannada script without sufficient ground truth examples.** (Kannada POIs in the labeled benchmark are rare; we must evaluate coverage and prepare a dedicated queue).

---

## 6. Preflight Action Plan for M18

1. **Benchmark Engine:** Formalize the 6-class provenance schema and dual-view benchmark structure (Gold Human vs. Operational Consolidated).
2. **Quality Evaluator:** Build automated, reproducible evaluation scripts calculating precision, recall, F1, specificity, FPR, FNR, threshold curves, and confusion matrices with full provenance stratification.
3. **Error Analysis:** Conduct forensic case studies of all false positives and false negatives on ground truth pairs and safeguard-intercepted review pairs.
4. **Geospatial Intelligence Engine:** Process H3 spatial clusters, distance-decay distributions, and source disagreement within the official BBMP boundary polygon, exporting lightweight static visual charts.
5. **Indic Language Diagnostics:** Profile Kannada script POIs and evaluate transliteration feature behavior.
6. **Review Prioritization Pipeline:** Implement an explainable scoring formula to rank the 2,842 unresolved pairs and 1,029 review edges into high, medium, and low human review priorities.
7. **Regression Test Suite:** Expand automated test coverage for all evaluation metrics, provenance preservation, and queue prioritization.
