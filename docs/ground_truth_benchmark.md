# Human-Labelled Ground Truth Benchmark & Annotation Schema

This document specifies the architectural foundation, schema definitions, annotation rules, and difficult-case guidelines for the human-labelled ground truth benchmark in the **India-Specific POI Conflation** project across Bruhat Bengaluru Mahanagara Palike (BBMP), Bengaluru, India.

---

## 1. Architectural Motivation & Core Principles

In geospatial entity resolution, evaluating candidate blocking recall, feature engineering predictive power, and model performance requires **empirically verified ground-truth labels**.

### Core Methodological Principles
1. **No Automated Ground Truth:** Machine-generated candidates, string similarity metrics, or spatial co-location scores must **never** be used to automatically assign `MATCH` labels. Doing so creates circular validation where models merely learn their own heuristic assumptions.
2. **Proximity Alone Does Not Establish Identity:** In high-density urban Indian environments (e.g., Indiranagar 100ft Road, Chickpet, multi-story commercial complexes), distinct businesses frequently operate within 0 to 10 meters of each other or share identical geocodes. Spatial proximity is evidence of potential co-location, not identity.
3. **Explicit Uncertainty Handling:** Annotators are never forced into binary classifications. If evidence is ambiguous or incomplete, records are assigned `UNCERTAIN` or routed to `NEEDS_ADJUDICATION`.
4. **Stable Identifier Preservation:** All benchmark pairs preserve the deterministic primary key format `<osm_source_record_id>::<overture_source_record_id>`.

---

## 2. Formal Label Definitions

The annotation schema enforces four mutually exclusive decision classes:

| Decision Class | Definition | Operational Criterion |
| :--- | :--- | :--- |
| **`MATCH`** | Both records refer to the **same physical Point of Interest** in the real world. | Co-referent identity: name, business type, and physical location refer to the same establishment. |
| **`NON_MATCH`** | The records refer to **distinct real-world entities**. | Clear evidence that the records denote different businesses, institutions, or amenities, even if co-located. |
| **`UNCERTAIN`** | Available evidence is **insufficient to make a reliable decision**. | Lack of distinctive name (e.g. "Store"), ambiguous address, or unresolvable temporal change without field verification. |
| **`NEEDS_ADJUDICATION`** | Multiple annotators disagree or the case requires senior expert review. | Significant semantic or spatial ambiguity requiring consensus review. |

---

## 3. Confidence Levels and Evidence Taxonomy

To enforce structured reasoning rather than intuitive guessing, annotators must record both confidence and evidence categories:

### Confidence Levels
* **`HIGH`:** Clear, unambiguous evidence (e.g., exact distinctive name and co-location, or clearly distinct commercial brands).
* **`MEDIUM`:** Strong evidence but minor abbreviation, minor spatial displacement (10–30m), or generic category tags.
* **`LOW`:** Weak evidence, significant phonetic divergence, or substantial spatial displacement.

### Evidence Types
1. **`EXACT_NAME_AND_LOCATION`:** Exact or near-identical distinctive brand name and spatial co-location ($\le 50$m).
2. **`TRANSLITERATION_OR_PHONETIC_MATCH`:** Vernacular Kannada script matching Romanized English or Indian English phonetic variant (`ವಿದ್ಯಾರ್ಥಿ ಭವನ` $\leftrightarrow$ `Vidyarthi Bhavan`).
3. **`NAME_EXPANSION_OR_ACRONYM`:** Corporate legal suffix addition (`Pvt Ltd`), acronym expansion, or store format designation.
4. **`STREET_LEVEL_DISPLACEMENT`:** Centroid offset between street entrance gate node and building roof polygon.
5. **`SAME_BUILDING_DIFFERENT_BUSINESS`:** Distinct commercial establishments operating inside the same shopping complex or arcade.
6. **`SAME_BRAND_DIFFERENT_BRANCH`:** Identical chain brand (e.g., "State Bank of India", "Nandhini Deluxe") operating at distinct geographic branches.
7. **`PARENT_CHILD_RELATION`:** Subsidiary facility operating inside a host institution (e.g., pharmacy inside hospital, cafe inside university campus).
8. **`CATEGORY_DISJOINT`:** Completely unrelated domain categories co-located by chance.
9. **`INSUFFICIENT_EVIDENCE`:** Missing name, generic uninformative label, or unresolvable ambiguity.
10. **`OTHER`:** Specific rationale documented in free-text notes.

---

## 4. Annotation Guidelines for Difficult Urban Cases

### A. Same Brand, Different Branch
* **Scenario:** "State Bank of India, Koramangala" vs "State Bank of India, HSR Layout" (displaced by 800m).
* **Rule:** **`NON_MATCH`**. Distinct branches of a corporate chain or franchise are independent real-world entities.

### B. Same Building, Different Businesses
* **Scenario:** "Nandhini Deluxe Restaurant" and "Kalyan Jewellers" at the exact same coordinates ($0.5$m apart) in a commercial complex.
* **Rule:** **`NON_MATCH`**. Physical co-location inside the same structure does not constitute entity identity. Assign evidence `SAME_BUILDING_DIFFERENT_BUSINESS`.

### C. Parent Institution vs. Internal Facility
* **Scenario:** "Manipal Hospital" vs "Manipal Hospital Pharmacy" located inside the main hospital compound ($18$m apart).
* **Rule:** **`NON_MATCH`** by default under 1-to-1 conflation, unless conflating at institutional parcel level. Record evidence `PARENT_CHILD_RELATION`.

### D. Shopping Mall vs. Individual Store
* **Scenario:** "Nexus Koramangala Mall" vs "Starbucks Nexus Koramangala".
* **Rule:** **`NON_MATCH`**. A commercial tenant is distinct from the host shopping mall.

### E. Kannada Vernacular vs. English Signage
* **Scenario:** `ಶ್ರೀ ಲಕ್ಷ್ಮಿ ಪ್ರೊವಿಷನ್ ಸ್ಟೋರ್` vs `Sri Lakshmi Provision Store`.
* **Rule:** **`MATCH`** if phonetically identical and co-located. Assign evidence `TRANSLITERATION_OR_PHONETIC_MATCH`.

### F. Generic Names (Temples, Mosques, ATMs)
* **Scenario:** "Ganesha Temple" vs "Sri Vinayaka Temple" ($15$m apart).
* **Rule:** If names are generic without distinctive epithet or ward name, mark **`UNCERTAIN`** unless local landmark knowledge confirms identity.

---

## 5. Benchmark Structure & Reproducibility

The benchmark is organized under `data/processed/benchmark/`:
```text
data/processed/benchmark/
├── annotation_queue.csv       # 500 stratified candidate pairs
├── annotations/               # Completed annotator decision files
│   └── annotations_<id>.csv
├── adjudication_queue.csv     # Disagreed or uncertain pairs requiring review
├── missed_match_audit.csv     # 120 unrepresented/weak OSM records
└── benchmark_metadata.json    # Versioned manifest with seeds, commits, and timestamps
```

* **Candidate Generation Snapshot:** Commit `2a1e60f`.
* **Sampling Seed:** `42` (deterministic stratified random sampling).
* **Metadata Manifest:** Synchronized to [reports/benchmark_metadata.json](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/benchmark_metadata.json).
