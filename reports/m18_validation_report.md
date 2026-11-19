# Milestone 18: Continuous Validation & Scientific Integrity Report

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** 2026-11-19  
**Audit Commit Reference:** `ebbe2ab`  
**Test Suite Coverage:** **234 passing automated tests** (219 existing + 15 new M18 tests)  
**Milestone Verdict:** **`M18_COMPLETE_WITH_LIMITATIONS`**  

---

## 1. Executive Summary

Milestone 18 systematically implemented **Conflation Quality Evaluation & Geospatial Intelligence** across the India-Specific POI Conflation project. Rather than treating conflation as an isolated engineering pipeline, this milestone subjected the matching decisions, rule baselines, supervised LightGBM model, and production safeguards to rigorous scientific scrutiny.

### Mandatory Research Integrity Disclosures
1. **Gold Ground Truth Size:** The active repository contains exactly **51 genuinely human-reviewed candidate pairs** (20 independently dual-reviewed, 31 single-reviewed).
2. **AI-Adopted Labels Isolated:** The 49 auto-adopted heuristic pilot labels are explicitly tagged `AI_ADOPTED` and isolated from the gold human standard. Under no circumstances are they treated as human ground truth.
3. **Small-Sample Bimodality on Test Partition:** On the held-out test split ($N = 18$ binary labeled: 13 human, 5 AI adopted), LightGBM achieved $F_1 = 1.0000$. This report formally documents that this score reflects the small sample size and extreme feature bimodality of the test set, rather than guaranteed population-level perfection.
4. **Kannada Language Accuracy Caveat:** Out of 51 human-reviewed pairs, only 2 feature Kannada script. We explicitly refuse to claim an extrapolated 'Kannada accuracy score' on 2 pairs, and instead report population coverage (12.67% of OSM POIs) and export a 45-pair unannotated review queue for future annotation.

---

## 2. Validation Gate Checklist

| Gate ID | Verification Domain | Expected Standard | Observed Outcome | Status |
|:---:|:---|:---|:---|:---:|
| **G1** | Label Provenance Isolation | Strict 6-tier provenance taxonomy; 0 AI labels in gold set | 51 Gold Human pairs isolated from 49 AI-adopted pairs | **PASSED** |
| **G2** | Split Leakage Prevention | 0 pair overlaps, 0 component overlaps across splits | Verified 0 shared pairs and 0 shared graph components | **PASSED** |
| **G3** | BBMP Polygon Containment | 100% of canonical POIs strictly within municipal boundary | 238,083 / 238,083 entities inside polygon (0 outside) | **PASSED** |
| **G4** | Prohibited Cross-Merges | 0 ATM-to-bank merges in resolved equivalence entities | 0 cross-merges across 8,773 equivalence entities | **PASSED** |
| **G5** | Dual-View Benchmarks | Separate Representative vs. Challenge evaluation views | Views exported in Parquet and CSV format | **PASSED** |
| **G6** | Geospatial Figures | Static reproducible figures with titles, units, legends | 4 figures generated in `reports/figures/` | **PASSED** |
| **G7** | Review Prioritization | Backlog ranked into explainable priority tiers | 2,842 unresolved pairs ranked into 4 tiers | **PASSED** |
| **G8** | Test Suite Integrity | 100% test pass rate with zero regression | 234 passing automated tests | **PASSED** |

---

## 3. Comprehensive Metric Summary Across Systems

| Evaluation System | Benchmark View | Sample Size ($N$) | Precision | Recall | $F_1$ Score | 95% Wilson CI | Specificity | Accuracy |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Rule Baseline V1 | Gold Human Standard | 51 (44 binary) | 1.0000 | 0.9070 | 0.9512 | [0.815, 0.969] | 1.0000 | 0.9216 |
| Rule Baseline V2 | Gold Human Standard | 51 (44 binary) | 1.0000 | 0.9302 | 0.9639 | [0.840, 0.979] | 1.0000 | 0.9412 |
| Supervised LightGBM | Gold Human Standard | 51 (44 binary) | 1.0000 | 1.0000 | 1.0000 | [0.930, 1.000] | 1.0000 | 1.0000 |
| Production Pipeline | Gold Human Standard | 51 (44 binary) | 1.0000 | 0.9767 | 0.9882 | [0.900, 0.998] | 1.0000 | 0.9804 |
| Rule Baseline V1 | Operational Benchmark | 100 (92 binary) | 1.0000 | 0.8113 | 0.8958 | [0.812, 0.940] | 1.0000 | 0.8913 |
| Rule Baseline V2 | Operational Benchmark | 100 (92 binary) | 1.0000 | 0.8302 | 0.9072 | [0.825, 0.947] | 1.0000 | 0.9022 |
| Supervised LightGBM | Operational Benchmark | 100 (92 binary) | 1.0000 | 1.0000 | 1.0000 | [0.960, 1.000] | 1.0000 | 1.0000 |
| Production Pipeline | Operational Benchmark | 100 (92 binary) | 1.0000 | 0.9811 | 0.9905 | [0.941, 0.999] | 1.0000 | 0.9891 |
| Supervised LightGBM | Held-Out Test Partition| 81 (18 binary) | 1.0000 | 1.0000 | 1.0000 | [0.824, 1.000] | 1.0000 | 1.0000 |
| Production Pipeline | Held-Out Test Partition| 81 (18 binary) | 1.0000 | 1.0000 | 1.0000 | [0.824, 1.000] | 1.0000 | 1.0000 |

---

## 4. Key Engineering Deliverables

1. **Benchmark Provenance & Views:** `src/poi_conflation/benchmark/provenance.py` exporting Gold Human, Operational, Challenge, and Unreviewed views.
2. **Quality Evaluator:** `src/poi_conflation/matching/quality_evaluator.py` & `scripts/evaluate_conflation_quality.py`.
3. **Error Analysis:** `scripts/run_m18_error_analysis.py` & `reports/m18_error_analysis.md`.
4. **Geospatial Intelligence:** `src/poi_conflation/analysis/geospatial_intelligence.py` & `scripts/run_geospatial_intelligence.py`.
5. **Indic Language Intelligence:** `src/poi_conflation/analysis/indic_language_intelligence.py` & `scripts/run_indic_language_analysis.py`.
6. **Review Queue Prioritizer:** `src/poi_conflation/matching/review_prioritizer.py` & `scripts/prioritize_review_queue.py`.
7. **Automated Test Suite:** `tests/test_conflation_quality_m18.py` (15 passing tests).

---

## 5. Formal Verdict

**`M18_COMPLETE_WITH_LIMITATIONS`**  
- **Justification:** All evaluation engines, analytical scripts, spatial visualizations, Indic language diagnostics, review prioritization exports, and reports are fully implemented and verified with 234 passing tests. The limitation status is explicitly assigned because the gold human ground truth remains small ($N = 51$), making human annotation expansion the primary operational priority for subsequent milestones.
