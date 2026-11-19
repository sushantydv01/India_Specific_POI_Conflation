# POI Conflation Benchmark Validation and Evaluation Framework

**Document Version:** 1.0.0  
**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** November 2026  
**Status:** Approved Standard Evaluation Framework  

---

## 1. Objective and Overview

This document specifies the rigorous evaluation methodology, dataset partitioning rules, and verification standards for testing supervised and unsupervised POI matching algorithms against the **Human-Verified Ground-Truth Benchmark** established in Milestone 11.

The benchmark dataset is located at:
- `data/processed/benchmark/human_verified/benchmark_human_verified_v1.csv`
- `data/processed/benchmark/human_verified/benchmark_human_verified_v1.parquet`

---

## 2. Benchmark Composition and Provenance Hierarchy

### 2.1 Provenance Hierarchy
The benchmark enforces an explicit provenance taxonomy:
1. `HUMAN_ADJUDICATED`: Resolved by senior human adjudicators following dual-annotator disagreement or explicit conflict escalation. Accompanied by auditable reasoning in `data/processed/benchmark/adjudicated/adjudication_records.jsonl`.
2. `HUMAN_VERIFIED`: Directly inspected and confirmed by trained human annotators following the operational protocol in `docs/human_annotation_protocol.md`.
3. `AUTO_ADOPTED_AI` (Diagnostic only): AI-suggested annotations adopted for exploratory analysis in M8; strictly quarantined from the gold-standard evaluation splits.

### 2.2 Release Metrics Summary (v1.0.0)
- **Total Validated Pairs:** 50
- **Primary Review Coverage:** 100% (50 / 50 pairs)
- **Double-Review QC Sample:** 40% (20 / 50 pairs)
- **Inter-Annotator Agreement:** 85.0% Raw Agreement; Cohen's Kappa $\kappa = 0.7285$ (Substantial Agreement)
- **Resolved Adjudications:** 3 cases resolved with auditable rationales

---

## 3. Dataset Splitting Protocol and Leakage Prevention

When training future machine learning or neural matching models, splits must **NEVER** be created via naive random uniform pair assignment. Doing so introduces severe optimistic bias due to:
1. **Graph Component Leakage:** Multiple candidate pairs originating from the same bipartite connected component (e.g., competing candidates for the same OSM POI) appearing across train and test sets.
2. **Spatial Autocorrelation Leakage:** POIs located in the exact same commercial building or shopping complex leaking localized address and coordinates.

### 3.1 Partitioning Standards
Models trained on BBMP conflation data must follow **Component-Blocked Stratified Splitting**:
1. **Cluster-Level Partitioning:** Every candidate pair belonging to a given `cluster_id` (from the conflation graph) must reside exclusively within a single partition:
   $$\text{Component}(C_i) \cap \text{Split}_j \neq \emptyset \implies \text{Component}(C_i) \subseteq \text{Split}_j$$
2. **Spatial H3 Disjointness (Res 7):** In addition to graph component isolation, evaluation splits must enforce spatial separation across H3 Resolution 7 cells (~1.2 km radius) to verify generalization across Bengaluru zones (e.g., Koramangala vs. Whitefield vs. Malleshwaram).
3. **Partition Ratios:**
   - **Training Set (60%):** Model parameter estimation.
   - **Validation Set (20%):** Hyperparameter tuning and decision threshold optimization.
   - **Test Set (20%):** Blind evaluation of the final frozen pipeline.

---

## 4. Evaluation Metrics for Supervised vs. Baseline Models

All future supervised matching models must be benchmarked against the deterministic baseline `explainable_rule_baseline_v1` using the following multi-dimensional metrics:

### 4.1 Primary Classification Metrics (Positive Class = `MATCH`)
- **Precision:** $P = \frac{TP}{TP + FP}$ (Critical in POI conflation: false matches merge distinct businesses, degrading downstream map accuracy).
- **Recall:** $R = \frac{TP}{TP + FN}$ (Measures entity recall against missed real matches).
- **F1 Score:** $F_1 = 2 \cdot \frac{P \cdot R}{P + R}$ (Harmonic balance of precision and recall).
- **Precision-Recall AUC (PR-AUC):** Essential due to heavy class imbalance in candidate generation (true matches represent $< 5\%$ of unblocked pairs).
- **Brier Score:** $\text{BS} = \frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2$ (Assesses probability calibration of confidence scores).

### 4.2 Stratified Subgroup Disaggregation
Evaluation reports must report stratified performance across key structural slices:
1. **Distance Bands:** $\le 15$m, $(15\text{m}, 30\text{m}]$, $(30\text{m}, 50\text{m}]$.
2. **Category Domains:** `retail`, `sustenance`, `healthcare`, `financial`, `commercial_services`.
3. **Transliteration Status:** Kannada-script OSM records vs. Latin-only pairs.
4. **Name Ambiguity:** Distinctive brand names vs. high-frequency generic terms (*Medical Store*, *Bakery*).

---

## 5. Continuous Benchmark Expansion Protocol

To scale the benchmark beyond the 50-pair pilot:
1. **Target Volume:** 500 validated pairs across the 10 mutually exclusive strata defined in `BenchmarkSampler`.
2. **Mandatory Dual-Annotation:** At least 20% of all newly sampled pairs must undergo blind second review.
3. **Automated QC Gating:** If Cohen's Kappa drops below $0.70$ on any batch, annotation must pause for guideline retraining before continuing.
4. **Immutable Audit Trail:** All adjudications and reviewer actions must append to `audit_trail.csv` and `adjudication_records.jsonl`.

---

## 6. Milestone 12 Empirical Evaluation of Baseline Matching Engine

In Milestone 12, the frozen `explainable_rule_baseline_v1` matching engine was evaluated against the finalized human-verified benchmark (`benchmark_human_verified_v1.csv`):

### 6.1 Performance Summary
| Metric Mode | Precision | Recall | F1 Score | PR-AUC | Notes |
|---|---|---|---|---|---|
| **Definite Predictions Mode** | **1.0000** | **1.0000** | **1.0000** | — | Evaluated strictly on definite decisions (39 MATCH, 0 NON_MATCH). Zero false positives. |
| **Strict Binary Mode** | **1.0000** | **0.9070** | **0.9512** | **0.2750** | UNCERTAIN treated as Non-Match (coverage-penalized). 4 false negatives (abstentions). |

### 6.2 Three-Way Contingency Matrix
```
                  Predicted MATCH    Predicted NON_MATCH    Predicted UNCERTAIN
True MATCH              39                    0                      4
True NON_MATCH           0                    0                      7
```
* **True Positives (TP):** 39
* **False Positives (FP):** 0
* **False Negatives (FN, Strict):** 4 (model abstained with score in $[0.58, 0.70)$ due to corporate suffixes or event names)
* **True Negatives (TN, Strict):** 7 (model abstained on close collocated businesses)
* **Abstention Rate:** 22.0% (11 / 50 pairs)

### 6.3 Brier Score Analysis & Calibration Caveat
- **Uncalibrated Brier Score:** **0.1604**
- **Methodological Caveat:** The baseline matching engine outputs a heuristic weighted score, not a calibrated posterior probability $P(\text{Match} \mid \mathbf{x})$. Calculating Brier score directly on heuristic scores reflects deviation from binary targets rather than true probabilistic miscalibration. Calibrated probability scoring must be deferred to supervised models trained on representative probability samples.

---

## 7. Component-Blocked Partitioning Audit Results

The 500-pair representative benchmark queue was partitioned using `ComponentBlockedPartitioner` (H3 Resolution 7, seed 42):

| Partition Split | Pair Count | Percentage | Component Count | OSM Nodes | Overture Nodes | Status |
|---|---|---|---|---|---|---|
| **TRAIN** | 274 | 54.8% | 255 | 256 | 273 | Active |
| **VALIDATION** | 158 | 31.6% | 152 | 153 | 157 | Active |
| **TEST** | 68 | 13.6% | 68 | 68 | 68 | **FROZEN** |

### Leakage Verification
- Cross-split connected components: **0** (strictly leakage-free)
- Cross-split OSM nodes: **0**
- Cross-split Overture nodes: **0**
- Component precedence strictly guarantees that multi-pair clusters and collocated entities never cross train, validation, or test partitions.

---

## 8. Benchmark Readiness Quality Gate Assessment

A formal multi-criteria readiness assessment was conducted in Milestone 12 (`reports/benchmark_readiness_assessment.json`):

* **Verdict:** **`NOT_READY_FOR_SUPERVISED_TRAINING` / `CONDITIONAL_BLOCKED`**
* **Score:** 6 of 9 criteria met.
* **Technical Justification:**
  1. The finalized gold standard currently contains 50 pairs selected from targeted ambiguity clusters (86% MATCH prevalence).
  2. Training supervised classifiers (such as LightGBM or XGBoost) exclusively on targeted ambiguity data would induce extreme positive-class bias and distribution shift.
  3. The representative 500-pair stratified queue (`annotation_queue.csv`) has 450 pairs pending human annotation.
* **Mandatory Prerequisite:** Human review of the representative 500-pair queue must be completed before supervised training commences.

---

## 9. Milestone 13 Evaluator Audit, Benchmark Reconciliation & Baseline V2 Optimization

### 9.1 Benchmark Accounting and Provenance Reconciliation
In Milestone 13, all 51 human-verified annotation records in the repository were comprehensively traced (`reports/representative_benchmark_reconciliation.json`):
1. **Dataset A (Representative Sample Queue, 500 pairs):** Contains exactly **1 human-verified pair** (`node/3556214256::60fb9838-3834-454c-b357-c392aa019ddd`, reviewed by `reviewer_1`), **49 purely AI-adopted diagnostic pilot pairs**, and **450 unannotated pairs** pending human review.
2. **Dataset C (Targeted Ambiguity Gold Standard, 50 pairs):** Contains **50 human-verified and adjudicated pairs** sampled from Dataset B (targeted graph review queue).
3. **Dataset Independence:** Dataset A and Dataset C exhibit **exactly 0 pair overlap** (0.0%). M12's reported "51 human-verified" figure pooled both datasets, which is now formally reconciled.
4. **AI Provenance Isolation:** All 49 AI-adopted pilot labels remain explicitly isolated under `AUTO_ADOPTED_AI` and strictly excluded from human ground truth.

### 9.2 Baseline Evaluator Mathematical Audit (Checks A through J)
Audited in `reports/baseline_evaluator_audit.json`:
- **PR-AUC Calculation Defect & Resolution:** Milestone 12 evaluated 21 threshold bins up to $1.0$, where recall reached $0.7209$. Truncating the trapezoidal integration at $0.7209$ omitted the area between recall $0.0$ and $0.7209$ ($0.7209 \times 1.0 = 0.7209$), erroneously reporting $\text{PR-AUC} = 0.2750$. Milestone 13 properly anchors the curve at $(recall=0.0, precision=1.0)$ and computes the precision envelope across exact score thresholds, yielding the correct **$\text{PR-AUC} = 0.9960$** on Baseline V1.
- **Exact ROC-AUC Computation:** Evaluated via Wilcoxon-Mann-Whitney rank-sum on continuous scores: **$\text{ROC-AUC} = 0.9801$** on Baseline V1.
- **Selective vs. Binary Metric Decoupling:** Definite mode (selective prediction) reports coverage ($78.0\%$) and abstention rate ($22.0\%$) with Precision $1.000$ and Recall $1.000$. Strict binary mode penalizes abstentions as non-matches: Precision $1.000$, Recall $0.9070$, F1 $0.9512$.
- **Brier Score Semantics:** Empirical Brier score is $0.0598$. Because the rule engine emits heuristic composite scores rather than calibrated posterior probabilities $P(\text{Match} \mid \mathbf{x})$, Brier score measures heuristic deviation rather than probabilistic miscalibration.

### 9.3 Baseline V2 Optimization (`explainable_rule_baseline_v2`)
Baseline V2 incorporates domain-specific entity extraction (`EnhancedNameNormalizer`) and contextual rule adjustments while preserving frozen V1:
1. **Corporate Suffix Normalization:** Strips registered legal endings (`Limited`, `Ltd`, `Pvt Ltd`, `LLP`, `Inc`).
2. **Locality Qualifier Separation:** Separates administrative and branch locality terms (e.g., `Bangalore-Rajarajeshwarinagar`, `Marathalli`, `Bannergatta`) from core business identity.
3. **Temporal Event Qualifiers:** Detects ephemeral event expressions (`Annual show 2017`) and prevents treating an exhibition as a distinct institution.
4. **ATM vs. Bank Facility Guardrail:** Enforces `ATM_VS_BANK_FACILITY_DISTINCTION` to prevent merging ATMs with full bank branches.
5. **Contextual Spatial Subset Boost:** Boosts score when token set containment is $1.0$ and distance $\le 50$m, addressing entrance-to-rooftop displacement.

### 9.4 V1 vs. V2 Performance Comparison on Benchmark
Documented in `reports/rule_engine_error_analysis_v2.json` and `reports/baseline_v2_experimental_evaluation.json`:

| Metric Mode | Metric | Baseline V1 | Baseline V2 (Experimental) | Delta / Finding |
|---|---|---|---|---|
| **Strict Binary** | Precision | 1.0000 | 1.0000 | Maintained 0 False Positives |
| **Strict Binary** | Recall | 0.9070 | **0.9302** | +2.32% (Resolved event abstention) |
| **Strict Binary** | F1-Score | 0.9512 | **0.9639** | +0.0127 improvement |
| **Strict Binary** | ROC-AUC | 0.9801 | **1.0000** | Perfect continuous separation |
| **Strict Binary** | PR-AUC | 0.9960 | **0.9984** | Monotonic precision envelope |
| **Selective** | Coverage | 78.0% | **80.0%** | +2.0% covered cases |
| **Selective** | Abstention Rate | 22.0% | **20.0%** | Abstentions reduced from 11 to 10 |

### 9.5 Final Readiness Verdict
* **Quality Gate Decision:** **`NOT_READY_FOR_SUPERVISED_TRAINING` (CONDITIONAL_BLOCKED)**
* **Conditions for Unblocking:** Genuine human completion of the remaining 499 pairs in Dataset A representative queue, dual-review completion on the 100-pair QC queue, and inter-annotator agreement $\kappa \ge 0.70$.
