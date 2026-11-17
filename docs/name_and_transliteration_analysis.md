# Kannada Naming and Transliteration Profiling

This document formalizes the linguistic, orthographic, and phonetic research findings for Point of Interest entity resolution across **OpenStreetMap** and **Overture Maps Foundation** within the Bengaluru metropolitan region (BBMP).

---

## 1. Research Motivation & Core Challenge

Entity resolution in Indian geospatial datasets presents unique linguistic challenges rarely encountered in Western benchmarks:
1. **Multilingual Coexistence:** POIs frequently carry names in both English (Latin script) and the state's official vernacular language (**Kannada**, Unicode block `U+0C80`–`U+0CFF`), as well as Hindi (`U+0900`–`U+097F`).
2. **Asymmetric Source Representation:** As revealed by our empirical audit, OpenStreetMap actively curates native Indic script tags (`name:kn`), whereas Overture Maps Foundation records are overwhelmingly populated in Latin/English script.
3. **Phonetic & Orthographic Transliteration Variance:** Because there is no standardized official Latin orthography for Indian commercial establishments, informal phonetic transliteration produces widespread spelling variations for identical physical entities.

---

## 2. Empirical Script Distribution & Source Asymmetry

Analyzing all 246,856 canonical records in the spatially indexed dataset (`data/processed/canonical_pois_h3.parquet`) reveals a profound asymmetry between the two data providers:

| Linguistic Dimension | OpenStreetMap (OSM) | Overture Maps Foundation | Unified Benchmark |
| :--- | :---: | :---: | :---: |
| **Total POIs** | 49,036 | 197,820 | 246,856 |
| **Has Kannada Script (`U+0C80–U+0CFF`)** | **6,223 (12.69%)** | **400 (0.20%)** | **6,623 (2.68%)** |
| **Has English / Latin Script (`A–Z`)** | 34,891 (71.15%) | 197,478 (99.83%) | 232,369 (94.13%) |
| **Bilingual (Both Kannada & English)** | **6,190 (12.62%)** | **159 (0.08%)** | **6,349 (2.57%)** |
| **Kannada Script Exclusively** | 33 (0.07%) | 241 (0.12%) | 274 (0.11%) |
| **English / Latin Script Exclusively** | 28,701 (58.53%) | 197,319 (99.75%) | 226,020 (91.56%) |
| **Unnamed / Empty String** | 14,171 (28.90%) | 0 (0.00%) | 14,171 (5.74%) |

![Script Coverage](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/reports/figures/kannada_english_naming_coverage.png)

### Key Takeaway for Conflation Architecture
* **OSM is the Primary Repository of Vernacular Ground Truth:** In Bengaluru, OSM contributors systematically populate bilingual tags (`name:kn` alongside `name`). Over 99% of Kannada-tagged records in OSM also carry an explicit English name (`6,190 / 6,223 = 99.47%`).
* **Cross-Script Bridge:** Because Overture has almost zero native Kannada coverage (0.20%), matching an OSM feature tagged *only* in Kannada against an Overture record requires algorithmic transliteration (Kannada $\rightarrow$ Latin) or semantic mapping through address/geometry attributes.

---

## 3. Commercial Token Patterns and Honorific Variations

Analysis of 232,685 named entities in the benchmark identifies high-frequency commercial keywords and honorific variations that dominate Indian business nomenclature:

### 3.1 High-Frequency Commercial Tokens (Top 25)

| Rank | Token | Total Frequency | Commercial Semantics |
| :---: | :--- | :---: | :--- |
| 1 | `and` | 12,900 | Partnership / Conjunction |
| 2 | `sri` | **8,143** | Auspicious Honorific Prefix |
| 3 | `bank` | 6,923 | Financial Institution |
| 4 | `bangalore` | 6,127 | City Designation |
| 5 | `school` | 5,258 | Educational Institution |
| 6 | `ltd` / `limited`| 9,041 | Corporate Legal Suffix |
| 7 | `centre` / `center`| 6,658 | Service / Commercial Facility |
| 8 | `store` / `stores`| 4,885 | Retail / Grocery Establishment |
| 9 | `clinic` | 3,383 | Healthcare Facility |
| 10 | `hospital` | 2,292 | Major Healthcare Institution |
| 11 | `temple` | 2,844 | Religious Place of Worship |
| 12 | `hotel` / `restaurant`| 4,236 | Hospitality / Food Service |

### 3.2 Honorific Spelling Variations
The auspicious prefix designating reverence or prosperity appears under multiple phonetic spellings across providers:
* `sri`: 8,143 occurrences (dominant standard)
* `shree`: 1,152 occurrences
* `shri`: 844 occurrences
* `sree`: 287 occurrences

Standard string distance algorithms (such as Levenshtein) penalize substitutions like `sri` $\leftrightarrow$ `shree` heavily despite semantic equivalence. Token normalization must treat these prefixes as equivalence classes.

---

## 4. Typology of Transliteration and Matching Challenges

Inspection of real candidate pairs within the $50\text{m}$ proximity window reveals five distinct challenge typologies:

### Type 1: Phonetic Transliteration Divergence
* **Example:** `Udupi Grand` (OSM) $\leftrightarrow$ `Udapi grand` (Overture) [Distance: $24.87\text{ m}$]
* **Challenge:** Vowel substitution ($u \leftrightarrow a$) reflecting differing English transliterations of Kannada short vowel ಉ / ಅ.
* **Resolution:** Double Metaphone or phonetic encoding bridges this divergence where edit distance degrades.

### Type 2: Script Discordance (Bilingual Coexistence)
* **Example:** `Vidyarthi Bhavan` (Overture) $\leftrightarrow$ `ವಿದ್ಯಾರ್ಥಿ ಭವನ` (OSM `name:kn`)
* **Challenge:** Orthographic disjointness. Unicode code points share 0% overlap ($U+0C80$ vs ASCII).
* **Resolution:** Rely on the bilingual bridge in OSM (`name:en` or `name` field) or automated ISO 15919 Indic transliteration.

### Type 3: Hierarchical Affiliation & Sub-Entity Containment
* **Example 1:** `Apollo Cradle` (OSM) $\leftrightarrow$ `Apollo Cradle Hospital` (Overture) [Distance: $24.52\text{ m}$]
* **Example 2:** `Rainbow Children's Hospital` (OSM) $\leftrightarrow$ `Dr Seema Gonsalves - Pediatric Allergy Rainbow Children's Hospital Bannerghatta` (Overture) [Distance: $35.26\text{ m}$]
* **Challenge:** Doctor / department name prepended to parent hospital name. Standard token sort ratios fail ($0.51$), whereas **Token Set Ratio** achieves $1.00$ by recognizing complete subset containment.

### Type 4: Corporate & Legal Suffixes
* **Example:** `Karnataka State Agricultural Produce Processing and Export Corporation Limited` (OSM) $\leftrightarrow$ `KAPPEC Ltd` (Common alias).
* **Challenge:** Extreme acronym expansion ($70\text{ chars}$ vs $10\text{ chars}$).
* **Resolution:** Acronym extraction rules and alias field matching.

---

## 5. Lexical Similarity Baseline on Proximate Candidates ($\le 50\text{m}$)

To establish a statistical baseline before developing ML matching models, five similarity measures were benchmarked on proximate cross-source pairs:

| Similarity Measure | Mean Score | Median Score | $p_{25}$ Score | $p_{75}$ Score | Pairs with Score $\ge 0.80$ | Pairs with Score $< 0.30$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Token Jaccard** | 0.051 | 0.000 | 0.000 | 0.000 | 3.07% | **93.87%** |
| **Character 3-Gram Jaccard** | 0.062 | 0.000 | 0.000 | 0.012 | 3.37% | **93.25%** |
| **RapidFuzz Ratio (Levenshtein)** | 0.331 | 0.299 | 0.242 | 0.360 | 4.60% | 50.31% |
| **RapidFuzz Token Sort Ratio** | 0.328 | 0.296 | 0.244 | 0.359 | 4.29% | 51.53% |
| **RapidFuzz Token Set Ratio** | **0.338** | **0.296** | **0.246** | **0.359** | **6.44%** | **50.92%** |

### Critical Analytical Insight
* **Only 3% to 6% of geographically proximate pairs ($\le 50\text{m}$) represent true name matches.**
* The remaining 94%+ are distinct independent businesses operating in the same commercial structure, street row, or shopping mall.
* This quantitatively confirms that spatial blocking produces a candidate search space, while entity resolution requires multi-attribute probabilistic scoring (combining Token Set Ratio, phonetic encoding, category consistency, and address PIN codes).
