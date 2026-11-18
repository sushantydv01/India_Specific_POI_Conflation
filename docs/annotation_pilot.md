# POI Benchmark Annotation Pilot Workflow & Reviewer Guide

This guide documents the execution procedures for the **50-Pair Annotation Pilot Batch**, designed to validate annotation guidelines, measure human consensus, and establish quality-control baselines before full-scale benchmark labelling.

---

## 1. Pilot Objectives & Composition

The pilot batch extracts a balanced subset of **50 candidate pairs** from the main queue, selecting exactly **5 pairs from each of the 10 mutually exclusive strata**:

* 5 pairs: `KANNADA_TRANSLITERATION` (Vernacular Kannada script matched to English)
* 5 pairs: `PHONETIC_VARIANTS` (Commercial Indian English spelling variations)
* 5 pairs: `LARGE_DISTANCE_CANDIDATES` (Non-spatial candidates displaced $>50$m up to 2km)
* 5 pairs: `EXACT_NAME_MATCH` (Exact string equality within $\le 50$m)
* 5 pairs: `MULTI_STRATEGY_OVERLAP` (Corroborated by $\ge 2$ independent blocking strategies)
* 5 pairs: `CATEGORY_ADJACENCY` (Cross-domain category overlaps like Sustenance $\leftrightarrow$ Hospitality)
* 5 pairs: `MISSING_OR_GENERIC_NAME` (Pairs with missing, short, or generic names)
* 5 pairs: `CLOSE_SPATIAL_DISTINCT_NAMES` (Immediate physical co-location $\le 15$m with distinct names)
* 5 pairs: `HIGH_DENSITY_HOTSPOTS` (Pairs in top commercial market hubs: Chickpet, MG Road)
* 5 pairs: `SPATIAL_CLUSTER_RESIDUAL` (Baseline spatial candidate pairs)

**File Location:** `data/processed/benchmark/pilot_batch_50.csv`

---

## 2. Reviewer Evidence & Data Fields

For each candidate pair presented in the review session, the following evidence is provided:
* **Stable Pair ID:** Deterministic primary key `<osm_source_id>::<ov_source_id>`.
* **OSM Record:** Source ID, raw name, localized Kannada name (`name:kn`), English name (`name:en`), normalized name, category, and exact latitude/longitude.
* **Overture Record:** Source GID, raw name, normalized name, category, and exact latitude/longitude.
* **Relationship Metrics:** Metric Euclidean distance in meters (UTM 43N), category compatibility classification, and blocking strategy provenance.

> [!NOTE]
> If an optional attribute (such as Kannada script or secondary address) is absent in the source record, it is explicitly shown as `None` / unavailable. Missing attributes are never fabricated.

---

## 3. How to Execute the Pilot Review Session

Launch the terminal annotation CLI pointing to the pilot batch. You may run either with AI assistance enabled (for primary annotation) or in blind independent mode (for second-reviewer QC):

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Option A: AI-assisted review session (displays structured heuristics, accepts [a], modifies [m], rejects [r])
python scripts/annotate.py --pilot --ai-assisted --annotator reviewer_1

# Option B: Blind independent review session (standard human labelling without AI suggestions)
python scripts/annotate.py --pilot --annotator reviewer_1
```

For full details on the AI suggestion schema, heuristics, and audit logging, consult [ai_assisted_annotation.md](file:///Users/sushantydv01/Desktop/India_Specific_POI_Conflation/docs/ai_assisted_annotation.md).

### Review Controls & Actions (AI-Assisted Mode)
1. **AI Action Prompts:**
   - `a`: **Accept** suggestion verbatim (MATCH / NON_MATCH, confidence, and evidence reason).
   - `m`: **Modify** suggestion (pre-populates suggestion, allows human adjustments).
   - `r`: **Reject** suggestion (enter custom decision, confidence, and evidence).
   - `s`: Skip current pair to review later.
   - `q`: Save current progress atomically and exit cleanly.

### Review Controls & Actions (Blind Manual Mode)
1. **Decision Prompts:**
   - `1`: **`MATCH`** — The records refer to the same physical real-world POI.
   - `2`: **`NON_MATCH`** — The records denote distinct real-world entities.
   - `3`: **`UNCERTAIN`** — Ambiguous or insufficient evidence to make a reliable decision.
   - `4`: **`NEEDS_ADJUDICATION`** — Difficult edge case requiring peer discussion.
   - `s`: Skip current pair to review later.
   - `q`: Save current progress atomically and exit cleanly.
2. **Confidence Level Prompts:**
   - `1`: `HIGH`
   - `2`: `MEDIUM`
   - `3`: `LOW`
3. **Structured Evidence Reason:** Select 1 through 10 from the standardized evidence taxonomy.

### Atomic Persistence & Resume
Annotations are saved incrementally to:
`data/processed/benchmark/annotations/annotations_<annotator_id>.csv`

Subsequent invocations automatically resume from the first unreviewed pair in the pilot queue.

---

## 4. Second Reviewer Quality-Control Assignment

To compute inter-annotator agreement and Cohen's Kappa, a subset of pairs (e.g., 50% overlap = 25 pairs) can be assigned to a second independent reviewer:

```python
from src.poi_conflation.benchmark.agreement import AgreementEvaluator

evaluator = AgreementEvaluator()
qc_queue = evaluator.assign_second_reviewer_queue(
    source_queue_csv="data/processed/benchmark/pilot_batch_50.csv",
    second_annotator_id="reviewer_beta",
    overlap_fraction=0.5,
    seed=42
)
```

The second reviewer then runs:
```bash
python scripts/annotate.py --queue data/processed/benchmark/annotations/assigned_qc_queue_reviewer_beta.csv --annotator reviewer_beta
```

Once completed, `AgreementEvaluator.evaluate_pair_agreement("reviewer_alpha", "reviewer_beta")` computes raw percentage agreement and Cohen's $\kappa$, routing any conflicts to `adjudication_queue.csv`.
