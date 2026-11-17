# POI Conflation Annotation Workflow & Quality Control

This guide documents the procedures for generating annotation queues, conducting human review sessions, resuming progress, calculating inter-annotator agreement, and adjudicating disputed pairs.

---

## 1. Generating or Refreshing the Annotation Queue

To generate the stratified 500-pair annotation queue and missed-match diagnostic audit from existing candidate pairs:

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Execute benchmark initialization pipeline
python scripts/run_benchmark_setup.py
```

This generates:
* `data/processed/benchmark/annotation_queue.csv` (500 stratified candidate pairs).
* `reports/benchmark_sampling_report.json` (Stratum inclusion probabilities).
* `data/processed/benchmark/missed_match_audit.csv` (120 diagnostic POI records).
* `reports/missed_match_audit_summary.json` (Diagnostic failure categorization).
* `data/processed/benchmark/benchmark_metadata.json` (Versioned manifest).

---

## 2. Interactive Annotation Session (CLI)

The repository provides a dedicated, terminal-based review interface that runs locally on macOS without external cloud dependencies:

```bash
python scripts/annotate.py --annotator <your_identifier>
```

### Session Controls
* **`1`**: `MATCH` (Co-referent identity)
* **`2`**: `NON_MATCH` (Distinct entities)
* **`3`**: `UNCERTAIN` (Ambiguous or insufficient evidence)
* **`4`**: `NEEDS_ADJUDICATION` (Complex edge case requiring peer discussion)
* **`s`**: Skip current pair to review later
* **`q`**: Save current session cleanly and exit

### Resume Capability
The workflow engine (`src/poi_conflation/benchmark/workflow.py`) automatically compares `annotation_queue.csv` against the annotator's completed file (`data/processed/benchmark/annotations/annotations_<annotator_id>.csv`). Resuming the CLI immediately presents the next unreviewed candidate pair without losing prior labels or creating duplicate records.

---

## 3. Quality Control & Inter-Annotator Agreement

To measure labelling consistency across multiple human reviewers, the pipeline computes **Cohen's Kappa ($\kappa$)** on overlapping pairs:

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

* $p_o$: Observed percentage agreement across all decision classes.
* $p_e$: Expected agreement by chance based on marginal label distributions:
  $$p_e = \sum_{k \in \text{Classes}} P(\text{Annotator}_A = k) \times P(\text{Annotator}_B = k)$$

### Running Agreement Evaluation Programmatically
```python
from src.poi_conflation.benchmark.agreement import AgreementEvaluator

evaluator = AgreementEvaluator()
report = evaluator.evaluate_pair_agreement("annotator_1", "annotator_2")

print(f"Overlapping Pairs:  {report['overlapping_pairs']}")
print(f"Raw Agreement:      {report['raw_agreement_pct']}%")
print(f"Cohen's Kappa:      {report['cohens_kappa']}")

# Automatically sync conflicted pairs to adjudication queue
synced = evaluator.sync_disagreements_to_adjudication_queue(report)
print(f"Disagreements routed to adjudication: {synced}")
```

---

## 4. Adjudication Workflow

When annotators disagree on a pair (e.g., Annotator A marks `MATCH` while Annotator B marks `NON_MATCH`), the `AgreementEvaluator` routes the conflict to:

`data/processed/benchmark/adjudication_queue.csv`

### Adjudication Guidelines:
1. Senior reviewers inspect the original OSM and Overture records side-by-side.
2. Reviewers examine high-resolution satellite imagery or municipal street listings if available.
3. The consensus decision is recorded with rationale logged in the `notes` column.
4. Once consensus is reached, the adjudicated label replaces conflicting records in the frozen benchmark.
