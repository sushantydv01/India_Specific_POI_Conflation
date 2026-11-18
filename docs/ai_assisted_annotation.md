# AI-Assisted Human Annotation Architecture & Guide

This document specifies the technical design, data schema, heuristics, and operational safeguards for the **AI-Assisted Human Annotation System** in the India-Specific POI Conflation project.

---

## 1. Architectural Philosophy: Human-in-Command AI Assistance

High-quality ground truth is the foundational bedrock of any entity resolution pipeline. Machine-learned models and automated heuristics must **never** write directly to ground truth without explicit human inspection and confirmation.

The AI assistance system operates strictly under the **Human-in-Command** paradigm:

```
┌────────────────────────────────┐
│  Candidate Queue (50 / 500)    │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│      Heuristic AI Analyzer     │  Deterministic rule engine,
│   (Indic translit, phonetics,  │  multilingual awareness,
│   category compatibility, dist)│  no hallucination of missing fields
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│    AIPairSuggestion (JSONL)    │  Stored in separate file:
│ (Label, Conf, Evidence, Logic) │  data/processed/benchmark/ai_suggestions/
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│   Human Review CLI Interface   │  Interactive terminal:
│  scripts/annotate.py           │  Reviewer explicitly Accepts [a],
│  --pilot --ai-assisted         │  Modifies [m], or Rejects [r]
└───────┬────────────────┬───────┘
        │                │
        ▼                ▼
┌─────────────────┐ ┌──────────────────────────────────────┐
│  Human Ground   │ │          AI Audit Trail              │
│  Truth Records  │ │  (Logs human action: ACCEPTED,       │
│  annotations_*. │ │   MODIFIED, REJECTED, INDEPENDENT    │
│  csv            │ │   alongside model recommendation)    │
└─────────────────┘ └──────────────────────────────────────┘
```

### Core Integrity Guarantees
1. **Zero Auto-Labelling:** Generating AI suggestions does not write to any human annotation table. Unreviewed pairs remain unannotated.
2. **Strict Storage Separation:** AI suggestions are stored in `data/processed/benchmark/ai_suggestions/`. Human annotations are stored in `data/processed/benchmark/annotations/annotations_<reviewer>.csv`.
3. **Audit Trail Provenance:** Every human action on an AI suggestion is logged to `data/processed/benchmark/annotations/audit_trail.csv` as `ACCEPTED`, `MODIFIED`, `REJECTED`, or `INDEPENDENT`.
4. **Second-Reviewer Blind Isolation:** Second-reviewer queues (`assigned_qc_queue_<reviewer>.csv`) contain only raw candidate attributes. When run without `--ai-assisted`, the CLI enforces blind independent review to prevent confirmation bias and preserve valid inter-annotator agreement metrics.

---

## 2. Schema Specifications

### `AIPairSuggestion` Dataclass
Represents a structured, explainable recommendation generated for an unlabelled candidate pair:

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `pair_id` | `str` | Stable primary key `<osm_id>::<ov_id>` |
| `suggested_label` | `LabelDecision` | `MATCH`, `NON_MATCH`, `UNCERTAIN`, `NEEDS_ADJUDICATION` |
| `suggested_confidence` | `ConfidenceLevel` | `HIGH`, `MEDIUM`, `LOW` |
| `suggested_evidence_type` | `EvidenceType` | Standard 10-class evidence taxonomy |
| `explanation` | `str` | Transparent natural language justification |
| `supporting_evidence` | `List[str]` | Specific positive signals observed in attributes |
| `contradictory_evidence` | `List[str]` | Conflicting or negative signals observed |
| `missing_information` | `List[str]` | Attributes not present in source data |
| `adjudication_recommended` | `bool` | Flag indicating difficult edge cases |
| `model_identifier` | `str` | Version of the suggestion engine (e.g., `heuristic_rule_v1`) |
| `generation_timestamp` | `str` | ISO 8601 UTC timestamp |

### `AIAuditRecord` Dataclass
Logs the exact interaction between human decision and AI suggestion:

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `pair_id` | `str` | Primary key `<osm_id>::<ov_id>` |
| `annotator_id` | `str` | Unique human reviewer identifier |
| `human_decision` | `LabelDecision` | Validated decision assigned by human |
| `human_confidence` | `ConfidenceLevel` | Confidence assigned by human |
| `human_evidence_type` | `EvidenceType` | Evidence reason assigned by human |
| `human_action` | `HumanAction` | `ACCEPTED`, `MODIFIED`, `REJECTED`, `INDEPENDENT` |
| `ai_suggested_label` | `Optional[LabelDecision]` | Label originally proposed by AI (if shown) |
| `ai_suggested_confidence` | `Optional[ConfidenceLevel]` | Confidence originally proposed by AI |
| `ai_evidence_type` | `Optional[EvidenceType]` | Evidence reason proposed by AI |
| `ai_model_id` | `Optional[str]` | Model identifier that generated the suggestion |
| `review_timestamp` | `str` | Timestamp when human recorded decision |
| `notes` | `Optional[str]` | Human reviewer notes / justification |

---

## 3. Heuristic Suggestion Rules (`HeuristicAIAnalyzer`)

The `HeuristicAIAnalyzer` operates deterministically using only available candidate attributes without external API dependencies or heavy memory overhead:

1. **Missing / Generic Name Rule:**
   - If either OSM or Overture record lacks a valid non-empty primary name:
   - Output: `UNCERTAIN`, Confidence: `LOW`, Evidence: `INSUFFICIENT_EVIDENCE`.
   - Explicitly records missing name in `missing_information`. Proximity alone is insufficient to assert identity.
2. **Large Distance Rule ($> 100$m):**
   - If names are identical or highly similar ($\ge 0.85$) but distance $> 100$m:
     - Output: `NON_MATCH`, Confidence: `HIGH`, Evidence: `SAME_BRAND_DIFFERENT_BRANCH`.
   - If distance $> 100$m and names are distinct:
     - Output: `NON_MATCH`, Confidence: `HIGH`, Evidence: `OTHER`.
3. **Disjoint / Incompatible Category Rule:**
   - If canonical category compatibility is `INCOMPATIBLE` and names are distinct:
     - Output: `NON_MATCH`, Confidence: `HIGH`, Evidence: `CATEGORY_DISJOINT`.
   - If categories are incompatible but names are identical:
     - Output: `NEEDS_ADJUDICATION`, Confidence: `MEDIUM`, Evidence: `CATEGORY_DISJOINT`, `adjudication_recommended = True`.
4. **Exact Name & Close Location ($\le 25$m):**
   - Normalized names are identical, distance $\le 25$m, categories not incompatible:
   - Output: `MATCH`, Confidence: `HIGH`, Evidence: `EXACT_NAME_AND_LOCATION`.
5. **Exact Name with Street-Level Displacement ($25 < \text{dist} \le 100$m):**
   - Normalized names match, distance between 25m and 100m:
   - Output: `MATCH`, Confidence: `MEDIUM`, Evidence: `STREET_LEVEL_DISPLACEMENT`.
6. **Kannada Transliteration & Phonetic Match ($\le 50$m):**
   - Native Kannada script transliteration matches Latin Overture name (e.g. `ವಿದ್ಯಾರ್ಥಿ ಭವನ` $\rightarrow$ `vidyarthi bhavan`), or phonetic normalization matches:
   - Output: `MATCH`, Confidence: `HIGH` ($\le 25$m) or `MEDIUM` ($25-50$m), Evidence: `TRANSLITERATION_OR_PHONETIC_MATCH`.
7. **Name Expansion / Token Containment ($\le 50$m):**
   - Token subset/superset or high token sort ratio ($\ge 0.70$) within 50m:
   - Output: `MATCH`, Confidence: `MEDIUM` to `HIGH`, Evidence: `NAME_EXPANSION_OR_ACRONYM`.
8. **Close Spatial Proximity with Distinct Names ($\le 25$m):**
   - Physical co-location $\le 25$m but lexical similarity $< 0.35$:
   - Output: `NON_MATCH`, Confidence: `HIGH`, Evidence: `SAME_BUILDING_DIFFERENT_BUSINESS`.

---

## 4. CLI Execution & Review Workflows

### Generating AI Suggestions
To pre-generate structured suggestions for a queue batch:
```bash
python scripts/generate_ai_suggestions.py \
  --queue data/processed/benchmark/pilot_batch_50.csv \
  --output data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl \
  --report reports/pilot_ai_suggestions_summary.json
```

### Launching AI-Assisted Review (Primary Reviewer)
```bash
python scripts/annotate.py --pilot --ai-assisted --annotator reviewer_1
```

The reviewer is presented with:
1. Complete OSM and Overture record attributes, coordinates, distance, and blocking strategy.
2. Formatted **AI Assistant Suggestion Box** detailing recommendation, confidence, evidence reason, explanation, and audited missing attributes.
3. Quick actions:
   - `[a]` **Accept**: Confirms AI suggestion verbatim with one keypress.
   - `[m]` **Modify**: Uses AI suggestion as default while allowing the human to adjust label, confidence, evidence, or notes.
   - `[r]` **Reject**: Bypasses AI suggestion and enters custom human decision.
   - `[s]` **Skip**: Moves to next pair without recording.
   - `[q]` **Quit**: Saves progress and exits cleanly.

### Blind Review (Second Reviewer / QC)
To ensure independent validation and uncompromised inter-annotator agreement metrics:
```bash
python scripts/annotate.py \
  --queue data/processed/benchmark/annotations/assigned_qc_queue_reviewer_2.csv \
  --annotator reviewer_2
```
Omission of the `--ai-assisted` flag runs the session in blind independent mode where suggestions are completely hidden, recording all submissions under `HumanAction.INDEPENDENT`.

---

## 5. Pilot Batch AI Evaluation Results

Evaluation across the 50-pair pilot batch (`pilot_batch_50.csv` across 10 strata) yielded the following distribution:

| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Total Pairs Evaluated** | 50 | 100.0% |
| **Suggested Matches (`MATCH`)** | 10 | 20.0% |
| **Suggested Non-Matches (`NON_MATCH`)** | 32 | 64.0% |
| **Suggested Uncertain (`UNCERTAIN`)** | 5 | 10.0% |
| **Adjudication Recommended (`NEEDS_ADJUDICATION`)** | 3 | 6.0% |

### Evidence Type Breakdown
- `CATEGORY_DISJOINT`: 13 (26.0%)
- `SAME_BUILDING_DIFFERENT_BUSINESS`: 10 (20.0%)
- `OTHER`: 7 (14.0%)
- `SAME_BRAND_DIFFERENT_BRANCH`: 5 (10.0%)
- `NAME_EXPANSION_OR_ACRONYM`: 5 (10.0%)
- `INSUFFICIENT_EVIDENCE`: 5 (10.0%)
- `EXACT_NAME_AND_LOCATION`: 4 (8.0%)
- `STREET_LEVEL_DISPLACEMENT`: 1 (2.0%)

---

## 6. Automated Adoption Workflow & Provenance Disambiguation

Milestone 8 introduces fully automated adoption of deterministic heuristic suggestions into the pilot annotation dataset.

### Execution Command
```bash
python scripts/annotate.py --pilot --auto-adopt-ai --annotator ai_auto_adopter
```

### Methodological Provenance Taxonomy
To prevent machine-generated annotations from being misrepresented as human ground truth, the system enforces a three-tier provenance model:

1. **`AI_GENERATED`**: The raw suggestion generated by the heuristic or model provider (`pilot_ai_suggestions.jsonl`).
2. **`AUTO_ADOPTED_AI`**: Automated script adoption of an AI suggestion into the pilot annotation tables (`annotations_ai_auto_adopter.csv`).
3. **`HUMAN_VERIFIED`**: An annotation independently inspected, evaluated, and confirmed by a human reviewer (`annotations_reviewer_1.csv`).

### Operational Guarantees
- **Human Record Preservation:** Existing human annotations (such as Pair 1 reviewed by `reviewer_1`) are preserved intact and never overwritten.
- **Conflict Tracking:** If an existing human decision conflicts with an AI suggestion, both records are preserved and the discrepancy is logged to `adjudication_queue.csv` and the summary report.
- **Idempotency:** Repeated executions check existing keys and skip re-appending, ensuring zero duplicate rows in annotation files and audit trails.
- **Consolidated Dataset:** Generates `data/processed/benchmark/pilot_annotations_adopted.csv` containing all 50 pilot pairs with explicit per-row `provenance` tags.
- **Manifest State:** Updates the benchmark lifecycle manifest to `AI_AUTO_ANNOTATED_PILOT` (`is_frozen = false`).

### Known Methodological Limitations
- The auto-adopted pilot records are **not** independently verified human ground truth.
- They must not be used to compute human inter-annotator agreement or model precision/recall.
- The 50-pair pilot remains strictly separate from the 500-pair main benchmark queue.
