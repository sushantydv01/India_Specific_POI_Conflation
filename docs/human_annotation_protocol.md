# Human Annotation and POI Conflation Adjudication Protocol

**Document Version:** 1.0.0  
**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** November 2026  
**Status:** Approved Standard Operating Procedure  

---

## 1. Objective and Scope

This protocol defines the formal operational standard for human annotators, secondary reviewers, and adjudicators resolving candidate matches between OpenStreetMap (OSM) Points of Interest and Overture Maps Places within the Bruhat Bengaluru Mahanagara Palike (BBMP) administrative boundary.

The goal of this benchmark is to produce **gold-standard ground-truth annotations** with unambiguous provenance, high inter-annotator agreement, and verifiable evidential rationales.

---

## 2. Match Decision Taxonomy

Every candidate pair evaluated by a reviewer or adjudicator must receive exactly one of the following four primary decision labels:

### 2.1 `MATCH` (Confirmed Entity Identity)
* **Definition:** Both records represent the **exact same physical real-world establishment** occupying the same physical location.
* **Requirements:**
  1. The name refers to the same business or facility (accounting for transliteration, alternate spellings, or legal vs. trade names).
  2. The physical location corresponds to the same physical plot, building, or retail unit (subject to sensor displacement tolerances).
  3. The categories are functionally compatible (e.g., `cafe` and `restaurant` can match; `bank` and `hospital` cannot).

### 2.2 `NON_MATCH` (Confirmed Distinct Entities)
* **Definition:** The two records represent **distinct physical establishments**.
* **Typical Scenarios:**
  1. Different branches of the same franchise (e.g., *Nandhini Deluxe - Jayanagar* vs. *Nandhini Deluxe - BTM Layout*).
  2. Distinct businesses operating in close proximity (e.g., two adjoining shops in the same commercial street).
  3. Collocated entities where one is an anchor or container and the other is an independent tenant (see Section 4.4).
  4. Homonymous or generic businesses that happen to share a name (e.g., two unrelated *Shri Krishna Bakeries* 400 metres apart).

### 2.3 `UNCERTAIN` (Ambiguous / Insufficient Evidence)
* **Definition:** Available attribute evidence is insufficient to confirm identity or non-identity with high confidence.
* **Usage Conditions:**
  - Highly generic names (e.g., *Provision Store*, *Bakery*, *Tea Point*) without secondary address/contact attributes.
  - Spatial displacement near the blocking boundary ($30$–$50$m) in high-density areas with no street or phone corroboration.
  - Truncated or noisy names (e.g., single characters, punctuation artifacts) that prevent disambiguation.

### 2.4 `NEEDS_ADJUDICATION` (Disputed or Structural Conflict)
* **Definition:** Marked by an annotator when encountering a structural graph conflict, severe contradictory evidence, or when a reviewer is unable to decide between parent-child vs. equivalence.
* **Workflow Trigger:** Automatically routes the pair to senior adjudicators alongside graph topology and pairwise feature vectors.

---

## 3. Standardized Evidence Classes

Reviewers must tag at least one primary evidence class (and up to three supporting classes) justifying their decision:

| Code | Evidence Class | Description & Guidance |
|---|---|---|
| `EVD_EXACT_NAME` | Exact Name Match | Identical character strings or identical token sets after normalization. |
| `EVD_TRANSLIT` | Transliteration Equivalence | Cross-script identity between Kannada script (ಕನ್ನಡ) and Latin script (e.g., `ನಂದಿನಿ` $\leftrightarrow$ `Nandhini`). |
| `EVD_SPATIAL_PROX` | Spatial Proximity | Point coordinates within physical tolerance ($\le 15$m rooftop/entrance alignment, $\le 30$m plot boundary). |
| `EVD_CATEGORY_COMPAT` | Category Compatibility | Identical canonical category or valid sub-category subsumption (e.g., `fast_food` $\subset$ `restaurant`). |
| `EVD_CONTAINMENT` | Containment Relation | One entity physically operates inside another (e.g., ATM inside bank, kiosk inside mall). |
| `EVD_COLOCATED_DISTINCT` | Collocated Distinct Businesses | Different commercial entities sharing the same building, address, or doorstep. |
| `EVD_MULTI_BRANCH` | Multiple Brand Branches | Same commercial brand operating at different spatial locations across Bengaluru. |
| `EVD_ADDRESS_ALIGN` | Address / Locality Alignment | Corroborating ward, locality, layout, main road, or pincode match. |
| `EVD_CONTACT_ALIGN` | Phone / Web Corroboration | Matching landline/mobile number, domain URL, or official social profile. |
| `EVD_INSUFFICIENT` | Insufficient / Noisy Evidence | Sparse attributes prevent confident disambiguation. |

---

## 4. India-Specific Operational Guidelines

Annotators operating in Bengaluru must adhere to the following domain-specific rules:

### 4.1 Indic Script and Phonetic Transliteration (Kannada $\leftrightarrow$ Latin)
* **Script Divergence:** A large proportion of OSM POIs in Bengaluru have native Kannada script names (`name:kn` or primary `name`), whereas Overture Places predominantly use Latin script.
* **Phonetic Equivalence:** Reviewers must consider standard phonetic variations as matches:
  - Vowel lengthening: *Shanthi* vs. *Shanti*, *Udupi* vs. *Udipi*, *Bengaluru* vs. *Bangalore*.
  - Aspirated vs. unaspirated consonants: *Bhavan* vs. *Bavan*, *Dhaba* vs. *Daba*, *Chandra* vs. *Chander*.
  - Sibilant variations: *Sagar* vs. *Shagar*, *Sri* vs. *Shree* vs. *Shri*.
* **Rule:** If the Kannada transliteration matches the Latin name and the spatial distance is within $30$m, mark as `MATCH` with `EVD_TRANSLIT` and `EVD_SPATIAL_PROX`.

### 4.2 Generic Commercial Names
* **High-Frequency Generic Words:** Common names such as *Medical Store*, *General Stores*, *Bakery*, *Tea Stall*, *Xerox*, *Tailor Shop*, *Condiments*, *Electricals*, *Saloon/Salon*, and *Amul Parlour* are distributed densely throughout Bengaluru.
* **Rule:** Do **NOT** match two entities based solely on a generic name unless:
  - They share a distinctive prefix or owner name (e.g., *Manjunatha Medicals* vs. *Manjunatha Medicals* is a candidate; *Medicals* vs. *Medicals* is NOT sufficient without strict distance $< 10$m).
  - Distance $> 20$m with purely generic name must be classified as `UNCERTAIN` or `NON_MATCH`.

### 4.3 Multi-Branch Brand Dispersion
* **Franchise Chains:** Bengaluru hosts thousands of chain branches (e.g., *A2B - Adyar Ananda Bhavan*, *Empire Restaurant*, *Chai Point*, *Cult.fit*, *Apollo Pharmacy*, *Subway*, *KFC*).
* **Rule:** Two records representing the same brand must be classified as `NON_MATCH` (tagged `EVD_MULTI_BRANCH`) if:
  - Distance exceeds $50$ metres, OR
  - They specify distinct localities/areas (e.g., *Indiranagar 100ft Road* vs. *HAL 2nd Stage*).
* **Exception:** If distance is $\le 20$m and both represent the sole branch in that commercial strip, confirm as `MATCH`.

### 4.4 Parent-Child vs. Identity Match
* **Malls, Tech Parks, and Commercial Complexes:** (e.g., *Orion Mall*, *Forum South Bangalore*, *Manyata Embassy Business Park*, *Prestige Tech Park*).
* **Rule:** An anchor tenant (e.g., *PVR Cinemas*, *Zara*, *Starbucks*) must **NEVER** be matched to the container mall/complex:
  - Label: `NON_MATCH`
  - Evidence: `EVD_CONTAINMENT`
  - Note: Record relationship as `PARENT_CHILD` where supported by tooling.

### 4.5 Spatial Displacement and Urban Density Tolerances
* **Urban Canopy & GPS Multipath:** Due to multi-story concrete structures and narrow commercial roads (e.g., Chickpet, Malleshwaram, Commercial Street), GPS centroids frequently vary between $15$m and $35$m.
* **Rooftop vs. Road Centerline:** Overture records derived from satellite footprints may place the centroid at the building centroid, while OSM user nodes may place it at the street-level entrance gate.
* **Tolerance Rules:**
  - $\le 15$m: Spatial proximity is strongly corroborating.
  - $15$–$35$m: Spatial proximity is acceptable if names and categories match strongly.
  - $35$–$50$m: Requires exact or near-exact distinctive name match + identical category.
  - $> 50$m: Presumed `NON_MATCH` unless extraordinary corroborating contact/address evidence exists.

---

## 5. Review and Adjudication Workflow

```
[Candidate Pair / Ambiguous Cluster]
                │
                ▼
   ┌─────────────────────────┐
   │ Primary Reviewer (R1)   │
   │ (Human Annotation)      │
   └────────────┬────────────┘
                │
                ├─────────────────────────────────────────┐
                ▼ (Subset for QA)                         ▼ (Direct consensus)
   ┌─────────────────────────┐                            │
   │ Blind Second Review (R2)│                            │
   │ (Independent Annotation)│                            │
   └────────────┬────────────┘                            │
                │                                         │
        ┌───────┴───────┐                                 │
        ▼               ▼                                 │
   [Agreement]    [Disagreement]                          │
        │               │                                 │
        │               ▼                                 │
        │      ┌─────────────────────────┐                │
        │      │ Adjudication Panel (ADJ)│                │
        │      │ (Resolves conflict)     │                │
        │      └────────┬────────────────┘                │
        │               │                                 │
        ▼               ▼                                 ▼
   ───────────────────────────────────────────────────────────
              Validated Human Ground-Truth Benchmark
```

### 5.1 Primary Review
- Reviewer inspects OSM attributes, Overture attributes, pairwise features, distance, and graph cluster context.
- Explicitly selects decision, evidence class, confidence rating ($1$–$5$), and free-text notes.

### 5.2 Independent Blind Second Review
- A minimum $20$\% sample of review pairs is assigned to a secondary reviewer.
- The interface enforces strict **blindness**: the second reviewer is not shown the first reviewer's label, confidence, or notes.

### 5.3 Formal Inter-Annotator Agreement Evaluation
- Inter-annotator agreement is computed via:
  1. Percentage Exact Agreement.
  2. Cohen's Kappa coefficient ($\kappa$).
  3. $3 \times 3$ Confusion Matrix (`MATCH`, `NON_MATCH`, `UNCERTAIN`).
- Target Benchmark Quality: $\kappa \ge 0.75$ (substantial agreement) before release.

### 5.4 Adjudication
- Disagreements between Reviewer 1 and Reviewer 2, as well as pairs labeled `NEEDS_ADJUDICATION`, are reviewed by a senior adjudicator.
- The adjudicator inspects both reviews, feature vectors, and bipartite graph context, recording a definitive final decision and an audit rationale.
