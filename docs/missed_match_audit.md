# Missed-Match Diagnostic Audit & Recall Methodology

This document details the independent search methodology, sampling design, and empirical findings of the **Missed-Match Diagnostic Audit** in the **India-Specific POI Conflation** project.

---

## 1. Why Candidate Blocking Alone Cannot Measure Recall

A common methodological fallacy in record linkage literature is evaluating blocking quality strictly from generated candidate pairs:

$$\text{Candidate Set } C \subset (N_{\text{OSM}} \times N_{\text{OVERTURE}})$$

If human annotators label pairs sampled exclusively from $C$, the true positive rate among those pairs measures **candidate precision**, not **candidate recall**. True matches that were completely discarded by the blocking pipeline cannot be labelled from $C$.

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

## 4. Scientific Status Semantics & Empirical Audit Results

The audit enforces standardized scientific classifications to prevent premature conclusions:

| Diagnostic Status | Definition | Operational Meaning | Count in Audit | Percentage |
| :--- | :--- | :--- | :---: | :---: |
| **`NO_COUNTERPART_FOUND_IN_SEARCH`** | Search procedure identified no plausible counterpart within 1.5 km. | Plausible data absence in Overture commercial directory; entity mapped by OSM community not present in Overture. | **47** | **39.2%** |
| **`POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING`** | Candidate counterpart identified with fuzzy similarity $\ge 70\%$, but displaced $>50$m. | Candidate hypothesis pending human adjudication; illustrates spatial displacement. | **24** | **20.0%** |
| **`INSUFFICIENT_EVIDENCE`** | OSM record has missing or uninformative short name ($\le 3$ chars). | Attribute sparsity prevents automated or human linkage without field survey. | **49** | **40.8%** |
| **`HUMAN_CONFIRMED_MATCH_OUTSIDE_BLOCKING`** | Human reviewer confirmed identity co-reference. | True confirmed blocking loss (populated during human review phase). | **0** | **0.0%** |
| **`SEARCH_REQUIRES_EXPANSION`** | Search envelope inadequate to form hypothesis. | Further regional search required. | **0** | **0.0%** |

```
Diagnostic Verdict Distribution (N = 120):
  NO_COUNTERPART_FOUND_IN_SEARCH                : [===================] 47 (39.2%)
  POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING        : [==========] 24 (20.0%)
  INSUFFICIENT_EVIDENCE                         : [====================] 49 (40.8%)
```

---

## 5. Methodological Limitations & Proper Interpretation

1. **Diagnostic Rather than Statistical Recall:** This audit is an initial diagnostic tool designed to illuminate failure modes. It does **not** constitute a statistically valid global blocking-recall estimate across the 49,036 OSM universe because the sample was deliberately enriched with high-risk unrepresented records.
2. **Never Equate Search Failure with Proof:** An outcome of `NO_COUNTERPART_FOUND_IN_SEARCH` within 1,500m indicates that the defined procedure did not find a match; it is not proof that Overture completely lacks a counterpart in regional corporate tables.
3. **Never Equate Fuzzy Scores with Confirmation:** A status of `POTENTIAL_COUNTERPART_OUTSIDE_BLOCKING` is an unverified hypothesis; genuine identity can only be confirmed by human review (`HUMAN_CONFIRMED_MATCH_OUTSIDE_BLOCKING`).
