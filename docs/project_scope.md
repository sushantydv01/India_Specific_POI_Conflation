# Project Scope: India-Specific POI Conflation

## 1. The POI Conflation Problem

Point of Interest (POI) conflation is an entity resolution (record linkage) problem applied to geospatial entity datasets. Given two independent collections of geospatial records—in this project, OpenStreetMap (OSM) and Overture Maps Foundation (Places Theme)—the objective is to identify pairs of records $(r_{\text{OSM}}, r_{\text{Overture}})$ that correspond to the exact same physical, real-world establishment, facility, or landmark.

While general entity resolution is well-studied in tabular domains (e.g., customer deduplication, citation matching), geospatial POI conflation introduces multi-modal entity features:
- Textual attributes (names, alternate names, brands, multilingual scripts).
- Categorical attributes (taxonomies, primary/secondary classifications).
- Geospatial geometry (point coordinates, building footprints, boundaries).
- Contextual metadata (street addresses, localities, parent structures, operating hours).

In the context of Indian urban centers, POI conflation presents distinct structural complexities arising from unstandardized administrative addressing, multilingual naming conventions, and extreme physical POI density.

---

## 2. Why Exact Name Matching is Insufficient

Exact string matching or naive edit-distance thresholds systematically fail in Indian urban environments for several systematic reasons:

1. **Phonetic and Transliteration Drift:**
   Indian business names are frequently transliterated between Indic scripts (e.g., Devanagari, Kannada, Tamil) and Latin script without strict standardization.
   *Example:* "Laxmi", "Lakshmi", "Laxmee", and "लक्ष्मी" denote the identical entity.
2. **Generic Prefixes and Suffixes:**
   Commercial names frequently incorporate honorifics, deity references, or enterprise forms:
   *Example:* "Shree", "Sri", "Shri", "M/s", "Pvt Ltd", "Enterprises", "Traders", "Kalyana Mandapam", "Dhaba".
3. **Informal and Category-Embedded Names:**
   Crowdsourced contributors in OSM or web scrapers feeding commercial datasets frequently conflate the entity name with its functional category:
   *Example:* A record named "Sharma Tea Stall" in OSM may appear as "Sharma Snacks and Beverages" or simply "Sharma" with category `restaurant` in Overture.
4. **Multilingual and Dual-Script Representation:**
   Records may store the primary name in English, in a regional script, or in bilingual format (e.g., "A2B - Adyar Ananda Bhavan / அடையார் ஆனந்த பவன்").

A robust pipeline requires text normalization, token canonicalization, transliteration-aware representations, and soft token-overlap similarity scoring.

---

## 3. Why Geographic Proximity Alone is Insufficient

In low-density suburban or rural contexts, spatial proximity within 50 meters often strongly suggests co-location. However, in urban India, proximity alone produces unacceptable false-positive rates:

1. **High-Density Commercial Complexes & Bazaars:**
   Multi-story shopping centers, tech parks, and traditional markets (e.g., Chandni Chowk in Delhi, T. Nagar in Chennai, or Chickpet in Bengaluru) contain dozens or even hundreds of distinct businesses located within the same 10-to-20 meter radius or even sharing the exact same building centroid.
2. **Inconsistent Geocoding Accuracy:**
   OSM features may be mapped at the precise entrance node, the rooftop centroid of a polygon, or along a roadside parcel. Overture records may be positioned using interpolated address geocoding, mobile location centroids, or cadastral coordinates. Consequently, true matches may be spatially separated by 20 to 60 meters, while unrelated non-matches may sit 2 meters apart.
3. **Stacked Entities (Vertical Stratification):**
   A ground-floor pharmacy, a first-floor pathology clinic, and a second-floor tuition center share horizontal coordinates while remaining distinct legal entities.

Therefore, spatial proximity serves as an effective **candidate blocking constraint** (reducing search space), but cannot serve as the primary matching criterion without joint evaluation of textual, categorical, and contextual attributes.

---

## 4. Expected Linkage Outcomes

The record linkage system will evaluate candidate pairs $(r_{\text{OSM}}, r_{\text{Overture}})$ and classify each into one of three distinct operational outcomes:

```
                  +----------------------------------+
                  |  Candidate Record Pair Formed    |
                  +-----------------+----------------+
                                    |
                    Feature Extraction & Scoring
                                    |
                    +---------------+---------------+
                    |                               |
          Score >= High Threshold          Low < Score < High
                    |                               |
                    v                               v
            +---------------+               +---------------+
            |     MATCH     |               |    REVIEW     |
            +---------------+               +---------------+
                                                    ^
                                                    |
                                          Score <= Low Threshold
                                                    |
                                            +---------------+
                                            |   NON-MATCH   |
                                            +---------------+
```

1. **`MATCH` (Definite Positive):**
   - High composite confidence across spatial distance, normalized name similarity, and category compatibility.
   - Example: OSM record "Naturals Ice Cream" (Ice Cream Parlour, distance 6m) and Overture record "Natural Ice Cream" (Dessert Shop).
   - Automated acceptance without human review.
2. **`NON-MATCH` (Definite Negative):**
   - Candidate pairs generated by spatial proximity that represent distinct entities.
   - Example: "Apollo Pharmacy" and "Subway" situated in the same commercial plaza (distance 8m, zero name/category overlap).
   - Automatically discarded from match sets.
3. **`REVIEW` (Uncertain / Ambiguous):**
   - Marginal similarity scores, partial name overlap with category discrepancy, or high name similarity with borderline spatial displacement.
   - Example: "State Bank of India - SME Branch" vs "State Bank of India ATM" (distance 15m; potentially co-located or distinct service points).
   - Routed to an inspection queue or human adjudication workflow to prevent precision degradation.

---

## 5. Project Objectives

1. **Data Ingestion Pipeline:** Develop a reproducible ingestion flow capable of extracting, filtering, and projecting OSM `.osm.pbf` and Overture Places Parquet data into clean, typed intermediate tabular structures.
2. **Spatial Indexing & Blocking:** Implement spatial blocking using discrete global grid systems (e.g., H3) to partition data into localized spatial cells, keeping pairwise comparisons tractable.
3. **Domain-Specific Feature Engineering:** Design features that capture:
   - Coordinate distances (Haversine / Vincenty geodesics).
   - Token-based string distances (Levenshtein, token sort, token set ratios).
   - Indic phonetic encoding and script-transliteration similarity.
   - Category mapping taxonomy alignment.
4. **Decision Boundary Formulation:** Calibrate deterministic thresholds or probabilistic models (e.g., Fellegi-Sunter via Splink) to produce clean separation between MATCH, REVIEW, and NON-MATCH.
5. **Rigorous Benchmark Evaluation:** Measure pipeline performance against a manually curated evaluation dataset containing representative positive, negative, and edge-case pairs.

---

## 6. Initial Scope Limitations

To maintain empirical rigor and project tractability within available computational resources, the following scope boundaries are established:

- **Geographic Scope:** Restricted to a single, well-defined Indian municipal boundary / urban area (to be selected in Milestone 2 based on OSM and Overture data density). Multi-city or national-scale conflation is out of scope for the initial study.
- **Entity Types:** Focused on commercial and institutional Points of Interest (shops, restaurants, amenities, healthcare, banking, educational facilities). Linear features (roads, waterways) and administrative boundaries are strictly excluded.
- **Infrastructure Constraints:** The entire pipeline must be runnable on a single local development machine (e.g., Apple M3, 8 GB RAM) without requiring distributed clusters (Spark, Ray, Hadoop) or dedicated cloud infrastructure.
- **Implementation Phasing:** No production deployment, API serving, or user-facing real-time matching services will be built. The deliverable is a batch research pipeline with documented experimental benchmarks.

---

## 7. Planned Evaluation Methodology

Evaluation will follow standard information retrieval and record linkage metrics:

- **Ground Truth Sampling:** A stratified random sample of candidate pairs will be extracted, covering:
  - High-confidence probable matches.
  - Close-proximity probable non-matches (distractors within 50 meters).
  - Ambiguous cases (partial token matches, brand chains with multiple branches).
- **Manual Labeling Protocol:** Each sample pair will be independently reviewed and labeled (`True Match` vs. `True Non-Match`) with documented rationales based on satellite imagery, street view, and business directories.
- **Quantitative Metrics:**
  - **Precision:** $\frac{TP}{TP + FP}$ (critical: false merges must be minimized).
  - **Recall:** $\frac{TP}{TP + FN}$ (measuring coverage of true co-occurring POIs).
  - **$F_1$ and $F_{0.5}$ Scores:** Harmonic means penalizing false positives more heavily than false negatives.
  - **Reduction Ratio (Candidate Filtering Efficiency):** Fraction of Cartesian product eliminated by the blocking index.
  - **Pairs Completeness:** Recall of true matches retained after the blocking step.
