# M15.1 — Independent Evaluation Audit & Model Validation Report

**Document Title:** Independent Technical Audit and Validation of the Supervised POI Matching Pipeline  
**Milestone:** Milestone 15.1  
**Project:** India-Specific POI Conflation (BBMP, Bengaluru)  
**Date:** November 2026  
**Auditor:** Independent Technical Auditor  
**Formal Audit Verdict:** **`AUDIT_PASSED_WITH_CORRECTIONS`**  

---

## 1. Executive Summary

Milestone 15 implemented the first machine-learned POI matching system using LightGBM, reporting **F1 = 1.0000** on both the validation partition and the held-out frozen test partition. 

This independent audit conducted a comprehensive, ground-up verification of the repository, training datasets, leakage isolation, individual predictions, ambiguous label treatment, metric implementations, batch inference pipeline, and model explainability.

### Primary Audit Findings
1. **Leakage & Partitioning Integrity (VERIFIED):**
   - Zero bipartite connected component leakage across splits.
   - Zero shared OSM nodes and zero shared Overture nodes across Train, Validation, and Test partitions.
   - The original Milestone 14 frozen test partition (68 pairs from Dataset A) is **100% preserved**.
   - All 44 features are computed via deterministic instance-level logic with zero cross-sample leakage.
2. **Held-Out Test Set Bimodality & Sample Size (IDENTIFIED & CLARIFIED):**
   - The reported **F1 = 1.0000** on the test partition ($N=18$ binary pairs) is **mathematically genuine for this specific sample**, but is driven by **high benchmark bimodality and small sample size**.
   - 10 of the 12 MATCH cases in the test partition are trivial exact name matches within 12.5 meters.
   - The 6 NON_MATCH cases have completely distinct commercial names.
   - Furthermore, **72.2% of the binary test records (13 of 18 pairs) originate from Dataset C (targeted gold standard)**, while only 5 binary pairs originate from Dataset A (representative pilot).
   - This 100% test F1 cannot be extrapolated to claim 100% real-world generalization across arbitrary subtle ambiguities.
3. **Ambiguous Label Treatment (CORRECTED):**
   - M15 error analysis previously claimed "0 errors across 100 annotated pairs".
   - The audit revealed that this phrasing conflated the **92 binary targets** (which had 0 errors) with the **8 ambiguous pairs** (`UNCERTAIN`: 5, `NEEDS_ADJUDICATION`: 3).
   - The model predicted all 8 ambiguous cases as `NON_MATCH` ($p \in [0.003, 0.288]$), primarily because 4 pairs lack OSM names and 3 represent facility-practitioner or campus-park relationships.
   - Ambiguous cases are now explicitly reported separately from binary metrics.
4. **Additional Universe Matches & ATM Vulnerability (AUDITED & QUANTIFIED):**
   - Across the 605,428 candidate universe, the supervised model predicted **12,070 MATCH decisions** (an increase of 6,527 over Rule V1's 5,543).
   - While ~6,200 of these are genuine recoveries where Rule V1's guardrails were overly conservative (e.g., branch address qualifiers appended to chain names), the model exhibits a false-positive vulnerability on **ATM vs Bank Branch pairs (~358 pairs across the universe)** due to brand-level token containment without facility-level category penalization.
   - Downstream graph construction must enforce an explicit `ATM_VS_BANK_FACILITY_DISTINCTION` guardrail.
5. **Explainability Upgrade (CORRECTED):**
   - The explainability layer previously used a linear proxy multiplying feature values by global importance.
   - Upgraded to exact **TreeSHAP causal attribution** computed directly via LightGBM's native C++ booster (`pred_contrib=True`), with explicit handling of generic commercial names and empty attributes.
6. **Calibration Terminology (CORRECTED):**
   - Corrected all occurrences of "calibrated match probability" to **"uncalibrated model score" / "predicted match score"**, reflecting that raw sigmoid tree outputs were not calibrated via Platt scaling or isotonic regression.

---

## 2. Repository & Artifact Inventory

The audit verified the following versioned source artifacts:

| Stage / Component | Source Code / Script | Primary Data Artifacts | Verification Status |
| :--- | :--- | :--- | :--- |
| **Operational Consolidation** | `scripts/consolidate_operational_benchmark.py` | `data/processed/benchmark/operational/operational_benchmark_consolidated.parquet` | Verified (100 pairs) |
| **Supervised Datasets** | `scripts/build_supervised_training_dataset.py` | `data/processed/supervised/{train,validation,test}_features.parquet` | Verified (550 pool records) |
| **Model Configuration** | `configs/supervised_matching_config.yaml` | `models/supervised_poi_matcher_v1.joblib` (96.7 KB) | Verified (LightGBM) |
| **Model Training** | `scripts/train_supervised_matcher.py` | `models/supervised_poi_matcher_v1_metadata.json` | Verified |
| **Model Evaluation** | `scripts/evaluate_supervised_matcher.py` | `reports/supervised_model_evaluation.json` | Audited & Disaggregated |
| **Explainability Engine** | `src/poi_conflation/matching/explainability.py` | `reports/supervised_error_analysis.json` | Upgraded to TreeSHAP |
| **Batch Universe Engine** | `src/poi_conflation/matching/batch_inference.py` | `data/processed/predictions/supervised_predictions_universe.parquet` | Verified (605,428 rows) |
| **Readiness Assessment** | `scripts/assess_model_readiness.py` | `reports/model_readiness_assessment_m15.json` | Re-evaluated |

---

## 3. Training & Leakage Audit

### 3.1 Partition Record Allocation
The supervised pool contains 550 records (500 from Dataset A + 50 from Dataset C) partitioned using `ComponentBlockedPartitioner` (H3 Resolution 7, seed 42):

| Partition | Total Pairs | Binary Targets (`MATCH` / `NON_MATCH`) | Ambiguous (`UNCERTAIN` / `NEEDS_ADJ`) | Unannotated Pool |
| :--- | :--- | :--- | :--- | :--- |
| **TRAIN** | 299 | **49** (26 `MATCH`, 23 `NON_MATCH`) | 4 | 246 |
| **VALIDATION** | 170 | **25** (15 `MATCH`, 10 `NON_MATCH`) | 3 | 142 |
| **TEST** | 81 | **18** (12 `MATCH`, 6 `NON_MATCH`) | 1 | 62 |
| **Total** | **550** | **92** (53 `MATCH`, 39 `NON_MATCH`) | **8** | **450** |

### 3.2 Leakage & Component Disjointness Verification
- **Shared OSM Nodes:**
  - Train vs. Validation: **0**
  - Train vs. Test: **0**
  - Validation vs. Test: **0**
- **Shared Overture Nodes:**
  - Train vs. Validation: **0**
  - Train vs. Test: **0**
  - Validation vs. Test: **0**
- **Cross-Split Connected Components:** **0**
- **M14 Frozen Test Preservation:** All 68 candidate pairs from `data/processed/benchmark/partitions/test_partition.csv` remain strictly in the TEST partition.
- **Preprocessing Isolation:** No scalers, standardizers, or target encoders were fitted. All 44 features are strictly local pairwise calculations.

---

## 4. Individual Held-Out Prediction Audit (Test Partition)

Every one of the 18 binary test records was independently evaluated:

| # | Pair ID | OSM Name | Overture Name | Dist (m) | Actual | Provenance & Source | LGBM Score | LGBM Pred | Rule V1 | Correct? |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | `node/11309805435::a2754a05` | HDFC Bank | HDFC Bank | 9.6 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9965 | `MATCH` | `MATCH` (0.98) | **Yes** |
| **2** | `node/11527324109::1deec41f` | WeWork | WeWork | 9.7 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9965 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **3** | `node/10068956762::1b795c68` | Moplah's | Moplah's | 9.7 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **4** | `node/4702679393::019e33fc` | State Bank of India | State Bank of India | 12.5 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9965 | `MATCH` | `MATCH` (0.98) | **Yes** |
| **5** | `node/5302772313::4f724528` | MedPlus | MedPlus | 10.8 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **6** | `node/5304601990::f5d251e7` | Suraksha Medicals | Suraksha Medicals | 4.4 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **7** | `node/1470856097::3d0d7790` | Sangeeta Mobiles | Meghavi Wellness Spa & Salon | 44.3 | `NON_MATCH` | `AUTO_ADOPTED_AI` (Dataset A) | 0.0033 | `NON_MATCH` | `NON_MATCH` (0.27) | **Yes** |
| **8** | `node/2230257224::f365528a` | ICICI Bank | ICICI Bank Bangalore-Marathalli | 9.6 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9981 | `MATCH` | `UNCERTAIN` (0.61) | **Yes** |
| **9** | `node/13594648879::6917a740` | Print IT Solutions | OM SAI RAM Garments | 6.0 | `NON_MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.0103 | `NON_MATCH` | `UNCERTAIN` (0.60) | **Yes** |
| **10** | `node/13688767224::808b3446` | Yuki | Yuki Brewhouse and Kitchen | 12.7 | `MATCH` | `AUTO_ADOPTED_AI` (Dataset A) | 0.9982 | `MATCH` | `NON_MATCH` (0.35) | **Yes** |
| **11** | `node/1375978217::9558f6da` | Sweet Chariot | Sweet Chariot | 3.4 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **12** | `node/1375978280::f30f79d9` | Purple Haze | Purple Haze | 9.4 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **13** | `node/3556046874::3b6a43d4` | Human Capital Employment | Sri Mangala Travels | 35.7 | `NON_MATCH` | `AUTO_ADOPTED_AI` (Dataset A) | 0.0032 | `NON_MATCH` | `NON_MATCH` (0.27) | **Yes** |
| **14** | `node/3727148134::683742b3` | Vans | Vans | 8.7 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (1.00) | **Yes** |
| **15** | `node/3815223846::20a2537b` | UTX Travel & Holidays | Mobizen Mobile Services | 15.7 | `NON_MATCH` | `AUTO_ADOPTED_AI` (Dataset A) | 0.0050 | `NON_MATCH` | `UNCERTAIN` (0.47) | **Yes** |
| **16** | `node/3951238108::01084bc6` | Mary Matha Church | Mary Matha Church | 11.1 | `MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.9967 | `MATCH` | `MATCH` (0.88) | **Yes** |
| **17** | `node/4386506594::f5c69dd8` | Mithai Ghar | NK Ceramics | 7.3 | `NON_MATCH` | `AUTO_ADOPTED_AI` (Dataset A) | 0.0065 | `NON_MATCH` | `NON_MATCH` (0.35) | **Yes** |
| **18** | `node/11958462030::b8c0d6de` | Vijaya Medical Centre | Naturals Vijayabanklayout | 5.6 | `NON_MATCH` | `HUMAN_VERIFIED` (Dataset C) | 0.0065 | `NON_MATCH` | `UNCERTAIN` (0.57) | **Yes** |

### 4.1 Test Bimodality Finding
- 10 of the 12 matches (83.3%) are trivial exact string matches located within 12.5 meters.
- 2 of the 12 matches (16.7%) are straightforward token containments (`ICICI Bank` vs `ICICI Bank Bangalore-Marathalli` and `Yuki` vs `Yuki Brewhouse and Kitchen`).
- All 6 non-matches have completely distinct business names.
- **Audit Conclusion:** The 100% test F1 is mathematically real on this partition, but is an artifact of sample bimodality and small sample size ($N=18$).

---

## 5. Individual Validation Audit (Validation Partition)

The validation partition contains 25 binary records:
- **Matches (15 pairs):** 10 exact matches within 15m; 4 token containments (`Popeyes`, `Jiva Ayurveda`, `Aubree`, `Blossom Book House`); 1 bilingual/transliterated match. All predicted `MATCH` with scores $> 0.98$.
- **Non-Matches (10 pairs):** 8 collocated businesses in close proximity (1.7m–39m) with distinct names (`Sunnys` vs `Heads Up For Tails`, `Onyx Gym` vs `S S B Tower`, `Chariot` vs `My Bags`); 2 distant same-brand branch candidates (`Cake of the day` at 1,104m and `Bata` at 1,340m).
- **Rule V1 vs LightGBM:** Rule V1 abstained on 5 of the 25 pairs (`UNCERTAIN`), whereas LightGBM scored all 25 accurately without abstention.

---

## 6. Ambiguous-Label Audit

The operational benchmark contains 8 ambiguous/uncertain cases. In M15, these were excluded from binary target training. Their predictions are audited below:

| Split | Pair ID | OSM Name | Overture Name | Dist (m) | Actual Label | Provenance | Model Score | Model Decision | Root Cause |
|---|---|---|---|---|---|---|---|---|---|
| TRAIN | `way/632111019::2fa239d2` | Rainbow Children's Hospital | Dr Anupama Menon - Pediatric Pulmonologist at Rainbow Children's Hospital | 84.2 | `NEEDS_ADJUDICATION` | `AUTO_ADOPTED_AI` | 0.1650 | `NON_MATCH` | Doctor at hospital (practitioner vs facility) |
| TRAIN | `node/4809112928::830a483d` | *(empty)* | Ista Hotel | 30.3 | `UNCERTAIN` | `AUTO_ADOPTED_AI` | 0.0051 | `NON_MATCH` | Unpopulated OSM name |
| TRAIN | `node/3477797065::46f1a8d8` | Rosh Roy's | Sri Krishna Suites | 41.2 | `NEEDS_ADJUDICATION` | `AUTO_ADOPTED_AI` | 0.0033 | `NON_MATCH` | Disjoint names in commercial building |
| TRAIN | `node/12137671760::0b08e9b8` | *(empty)* | Nitrous Oxide Spec | 23.5 | `UNCERTAIN` | `AUTO_ADOPTED_AI` | 0.0048 | `NON_MATCH` | Unpopulated OSM name |
| VAL | `node/1852668995::be7dc1f3` | *(empty)* | Fuchsia | 37.1 | `UNCERTAIN` | `AUTO_ADOPTED_AI` | 0.0033 | `NON_MATCH` | Unpopulated OSM name |
| VAL | `way/1463856132::313cd3c3` | *(empty)* | Pantaloons | 17.9 | `UNCERTAIN` | `AUTO_ADOPTED_AI` | 0.0048 | `NON_MATCH` | Unpopulated OSM name |
| VAL | `way/27789854::a2b5308d` | Wipro Park | Wipro | 51.7 | `NEEDS_ADJUDICATION` | `AUTO_ADOPTED_AI` | 0.2884 | `NON_MATCH` | Municipal park named after corporate campus |
| TEST | `node/4691599028::3be62f5c` | *(empty)* | Grand Krishna Hotel | 36.7 | `UNCERTAIN` | `AUTO_ADOPTED_AI` | 0.0051 | `NON_MATCH` | Unpopulated OSM name |

> [!CAUTION]
> In M15, error analysis reported "0 errors across 100 annotated pairs". This audit clarifies that the model predicted `NON_MATCH` on all 8 ambiguous cases ($p < 0.29$). Because these cases represent unpopulated names or facility-practitioner container relationships, classifying them as `NON_MATCH` is physically reasonable, but they must NOT be counted as verified binary correct predictions.

---

## 7. Label Provenance Disaggregation

Separate evaluation metrics disaggregated by label provenance across partitions:

### 7.1 Frozen Held-Out Test Partition ($N=18$ Binary)
| Subset Breakdown | Sample Count | Matches / Non-Matches | Precision | Recall | F1 Score | ROC-AUC | Brier Score |
|---|---|---|---|---|---|---|---|
| **All Binary Records** | **18** | 12 / 6 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** |
| ↳ `HUMAN_VERIFIED` (Dataset C) | **13** | 11 / 2 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** |
| ↳ `AUTO_ADOPTED_AI` (Dataset A) | **5** | 1 / 4 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** |

### 7.2 Validation Partition ($N=25$ Binary)
| Subset Breakdown | Sample Count | Matches / Non-Matches | Precision | Recall | F1 Score | ROC-AUC | Brier Score |
|---|---|---|---|---|---|---|---|
| **All Binary Records** | **25** | 15 / 10 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0003** |
| ↳ `HUMAN_VERIFIED` (Dataset C) | **12** | 10 / 2 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0000** |
| ↳ `AUTO_ADOPTED_AI` (Dataset A) | **13** | 5 / 8 | **1.0000** | **1.0000** | **1.0000** | **1.0000** | **0.0005** |

---

## 8. Metric Implementation Audit

1. **Precision, Recall, F1:** Implemented strictly per standard definitions ($TP / (TP + FP)$, $TP / (TP + FN)$). Positive class is defined as `1` (`MATCH`), negative class as `0` (`NON_MATCH`).
2. **PR-AUC vs. Sklearn Average Precision:**
   - The repository implements trapezoidal integration over the interpolated precision envelope anchored at $(0, 1)$ (`compute_pr_curve_and_auc`).
   - On the test set, both the custom PR-AUC and `sklearn.metrics.average_precision_score` equal **1.0000**.
3. **Brier Score:**
   - Evaluated using mean squared error between model scores and binary targets. Test Brier score is **0.0000**.
4. **Calibration Status:**
   - The model scores represent raw sigmoid values from the boosted decision trees. Because Platt scaling or isotonic regression was not independently calibrated on an out-of-sample representative dataset, outputs are formally designated as **uncalibrated model scores**.

---

## 9. Batch Inference Performance & Pipeline Audit

Audited via `scripts/audit_supervised_evaluation_m15_1.py`:

- **Target Candidate Population:** Exactly **605,428 pairs**.
- **Unique Records in Output:** Exactly **605,428 unique pair IDs** (0 duplicates, 0 missing, 0 nulls).
- **Probability Bounds:** Minimum = 0.0029, Maximum = 0.9982.
- **Timing Breakdown:**
  - Model Deserialization (`joblib.load`): **0.769 seconds**
  - Streaming, Scoring, & ZSTD Parquet Writing: **0.867 seconds**
  - **End-to-End Total Runtime:** **1.635 seconds**
- **Throughput:**
  - Streaming / Scoring Throughput: **698,660 pairs / second**
  - End-to-End Throughput (including load): **370,224 pairs / second**
- **Peak Memory (RSS):** **462.09 MB** (well within Apple Silicon 8 GB budget).

---

## 10. Additional MATCH Prediction Audit (12,070 Matches)

Across the candidate universe, the supervised model predicted **12,070 MATCH decisions**:
- Overlap with Rule V1 MATCH: **5,422 pairs**
- Additional matches where Rule V1 had `UNCERTAIN`: **6,198 pairs**
- Additional matches where Rule V1 had `NON_MATCH`: **450 pairs**
- **Total Additional Matches:** **6,648 pairs**

### Risk Archetype Breakdown in Additional Matches
1. **Genuine Recoveries (~6,200 pairs):**
   - High token containment where Rule V1 was over-penalized by appended address strings (e.g., `Domino's` vs `Domino's Pizza | Yelahanka Satellite Town` at 4.6m; `Bhima` vs `Bhima Jewellers - Dickenson Road` at 19.5m).
2. **ATM vs Bank Branch Vulnerabilities (~358 pairs):**
   - e.g., `IndusInd Bank` vs `IndusInd Bank- ATM` (84.1m, $p=0.6834$); `HDFC Bank` vs `HDFC Bank ATM` (95.0m, $p=0.6744$).
   - The supervised model over-matches these because brand name similarity and spatial proximity dominate the tree splits without sufficient facility-level category penalty.
3. **Collocated Commercial Containers (~146 pairs):**
   - e.g., `IBM` vs `IBM Block A Cafeteria` (13.8m, $p=0.8698$).
4. **Recommendation for Milestone 16 Conflation Graph:**
   - Edges with $p \ge 0.55$ should NOT be automatically conflated into canonical 1:1 entities without facility-level post-filtering.
   - Enforce an explicit `ATM_VS_BANK_FACILITY_DISTINCTION` guardrail in the graph solver to prevent merging bank branches with standalone ATMs.

---

## 11. Model & Explainability Audit

Upgraded in `src/poi_conflation/matching/explainability.py`:
- **Native TreeSHAP Attribution:** Enabled exact local log-odds attribution via `matcher.estimator.booster_.predict(vec, pred_contrib=True)`. Eliminated heuristic proxy weighting.
- **Missing & Generic Names:** Explainer explicitly detects empty OSM/Overture names and flags high-frequency generic terms (`Medical Store`, `Bakery`).
- **Spatial Contradictions:** Explicitly flags distances $> 50$m as spatial contradictions exceeding premise envelopes.
- **Terminology:** Output fields updated to `model_match_score` with `calibration_status = "uncalibrated_model_score"`.

---

## 12. Corrective Actions Log

| Issue ID | Severity | Description | Corrective Action Applied | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ISS-001** | Major | Error analysis claimed "0 errors across 100 annotated pairs", masking ambiguous cases. | Decoupled binary evaluation (92 targets, 0 errors) from ambiguous triage audit (8 cases, all predicted `NON_MATCH`). | **Resolved** |
| **ISS-002** | Major | Test set composition was 72.2% Dataset C targeted pairs rather than representative queue. | Disaggregated all evaluations by provenance and source benchmark; documented sample size caveats. | **Resolved** |
| **ISS-003** | Major | Raw sigmoid scores were described as "calibrated match probabilities". | Corrected terminology to "uncalibrated model score" / "predicted match score" across codebase and docs. | **Resolved** |
| **ISS-004** | Major | Model over-matches ~358 ATM vs Bank Branch pairs in universe. | Documented vulnerability and formulated graph guardrail recommendations (`ATM_VS_BANK_FACILITY_DISTINCTION`). | **Resolved** |
| **ISS-005** | Minor | Explainability layer used global proxy weighting instead of local causal TreeSHAP. | Upgraded `POIModelExplainer` to compute native C++ TreeSHAP log-odds via LightGBM booster. | **Resolved** |
| **ISS-006** | Minor | Batch inference runtime omitted model loading time (0.77s). | Reported both streaming throughput (698k/s) and end-to-end throughput (370k/s). | **Resolved** |

---

## 13. Final Audit Verdict & Next-Milestone Recommendations

### Final Verdict: **`AUDIT_PASSED_WITH_CORRECTIONS`**

### Downstream Recommendations for Milestone 16 (Graph Conflation & Resolution)
1. **Edge Weighting:** Use `model_match_score` as continuous edge weights in the bipartite graph.
2. **Threshold Policy:**
   - Automated Equivalence: `model_match_score` $\ge 0.75$, with exact name match or high token containment.
   - Ambiguity Routing: `0.30 \le \text{model\_match\_score} < 0.75` routed to connected component conflict analysis.
   - Hard Edge Pruning: `model_match_score < 0.30` pruned prior to graph component expansion.
3. **Mandatory Post-Filters:** Apply `ATM_VS_BANK_FACILITY_DISTINCTION` and parent-child container checks before merging entities.
