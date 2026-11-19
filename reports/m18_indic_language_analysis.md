# Milestone 18: Indic Language & Transliteration Conflation Analysis

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Linguistic Focus:** Kannada Script, English-Kannada Transliteration & Phonetic Normalization  
**Status:** Formal Linguistic Analysis Report  

---

## 1. Executive Summary

In Bengaluru, POI records reflect an asymmetric linguistic divide between crowdsourced mapping and commercial cartography:
- **OpenStreetMap (OSM):** **6,212 POIs (12.67%)** contain vernacular Kannada names via `name:kn` tags or primary Kannada Unicode script.
- **Overture Maps Places:** Predominantly English-script; only **400 POIs (0.20%)** contain Kannada Unicode script.

Without multilingual blocking and Indic-aware transliteration, cross-source candidate generation would completely miss thousands of genuine POI pairs where OSM records the establishment in Kannada script (e.g. `ವಿದ್ಯಾರ್ಥಿ ಭವನ್`) and Overture records it in English (`Vidyarthi Bhavan`).

---

## 2. Script Distribution Across Source Datasets

| Source Dataset | Total POIs | Kannada `name:kn` Tag | Primary Kannada Unicode Script | Primary English Script | Vernacular Representation Rate |
|:---|:---:|:---:|:---:|:---:|:---:|
| **OpenStreetMap (OSM)** | 49,036 | 6,212 (12.67%) | 24 | 49,012 | **12.67%** |
| **Overture Maps** | 197,820 | 0 (0.00%) | 400 (0.2%) | 197,420 | **0.2%** |

---

## 3. Candidate Generation & Transliteration Features

The candidate generation pipeline deployed an Indic transliteration engine (`indic-transliteration` Sanscript converting Kannada Unicode script to ISO 15919 Latin characters) followed by phonetic Indian English normalization (`bhavana` $\rightarrow$ `bhavan`, `udapi` $\rightarrow$ `udupi`, `shree` $\rightarrow$ `sri`):

- **Total Candidate Pairs Analyzed:** **605,428**
- **Pairs with OSM Kannada Name Available:** **86,537 pairs** (14.29%)
- **Pairs with Transliteration Features Computed:** **87,126 pairs** (14.39%)
- **Pairs Recovered Exclusively via Transliteration Blocking:** **1,082 pairs**
- **Exact Transliteration String Matches:** **3,635 pairs**
- **Average Transliteration Token Similarity:** **0.5413**
- **Average Indic Phonetic Similarity:** **0.3091**

> [!TIP]
> **High-Value Recovery Example:** Candidate pair `node/104::ov-vidyarthi` (*ವಿದ್ಯಾರ್ಥಿ ಭವನ್* vs. *Vidyarthi Bhavan*). Under ASCII string matching, Levenshtein distance is 0.0 (completely disjoint Unicode blocks). Following ISO transliteration and phonetic normalization, token similarity reaches **1.0000**, enabling high-confidence conflation without manual intervention.

---

## 4. Honorific & Brand Core Dynamics in Indic Names

In Bengaluru, commercial establishments frequently prefix their legal or trade names with cultural or religious honorifics (*Sri*, *Shri*, *Sree*, *Saint*, *Dr.*, *Hotel*, *Darshini*, *Bhavan*).

### Risk of Naive Normalization
Aggressively stripping honorific prefixes causes severe false-positive conflations between distinct businesses:
- *Sri Venkateshwara Medicals* vs. *Sri Venkateshwara Xerox*
- *Sri Lakshmi Temple* vs. *Sri Lakshmi Condiments*

### Safeguard Precedence Verified
The `SHARED_HONORIFIC_DISJOINT_BRAND` safeguard (ADR-035 / ADR-036) preserves original and normalized representations separately. It strictly enforces that when two establishments share an honorific prefix, their **distinctive brand cores** must match (minimum 3 characters). If the cores disagree, the pair is routed to `REVIEW` with automated merging prohibited.

---

## 5. Ground Truth Limitations & Dedicated Kannada Review Queue

> [!IMPORTANT]
> **Scientific Integrity Disclosure:** Out of the 51 genuinely human-reviewed pairs in the active gold benchmark, only **2 pairs** feature Kannada script. We explicitly **refuse** to report an extrapolated 'Kannada accuracy score' on a sample of 2 pairs.

To enable rigorous future vernacular evaluation, we extracted all **45 unannotated candidate pairs** from Stratum 6 (`S6: Transliteration Match / Kannada Script`) and exported a dedicated human review queue:
- **Export Path:** [`data/processed/benchmark/evaluation_views/queue_kannada_expansion.csv`](file://data/processed/benchmark/evaluation_views/queue_kannada_expansion.csv)
- **Record Count:** **45 pairs**
- **Review Priority:** `CRITICAL_VERNACULAR_EVALUATION`
- **Queue Attributes:** Pair ID, OSM raw name, Overture raw name, OSM Kannada name (`osm_name_kn`), distance, categories, and sampling stratum.