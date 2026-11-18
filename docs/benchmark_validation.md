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
