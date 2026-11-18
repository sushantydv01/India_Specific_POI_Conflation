"""CLI utility to generate structured AI suggestions for human annotation queues.

Usage:
    python scripts/generate_ai_suggestions.py --queue data/processed/benchmark/pilot_batch_50.csv
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.benchmark.workflow import AnnotationWorkflow
from src.poi_conflation.benchmark.ai_analyzer import HeuristicAIAnalyzer
from src.poi_conflation.benchmark.ai_schema import AIPairSuggestion


def main():
    parser = argparse.ArgumentParser(description="Generate AI-Assisted Annotation Suggestions")
    parser.add_argument(
        "--queue",
        type=str,
        default="data/processed/benchmark/pilot_batch_50.csv",
        help="Path to candidate queue CSV file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl",
        help="Destination JSONL path for AI suggestions",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="reports/pilot_ai_suggestions_summary.json",
        help="Destination path for summary report JSON",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="heuristic_rule_v1",
        help="Model identifier",
    )
    args = parser.parse_args()

    queue_path = Path(args.queue)
    out_path = Path(args.output)
    report_path = Path(args.report)

    if not queue_path.exists():
        raise FileNotFoundError(f"Candidate queue CSV not found: {queue_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    workflow = AnnotationWorkflow(queue_csv=str(queue_path))
    items = workflow.load_queue()
    print(f"Loaded {len(items)} items from {queue_path}")

    analyzer = HeuristicAIAnalyzer(model_id=args.model)
    suggestions: List[AIPairSuggestion] = []

    label_counts: Counter = Counter()
    conf_counts: Counter = Counter()
    evidence_counts: Counter = Counter()
    stratum_distribution: Dict[str, Counter] = {}
    adjudication_count = 0

    with open(out_path, "w", encoding="utf-8") as f:
        for item in items:
            sugg = analyzer.generate_suggestion(item)
            suggestions.append(sugg)
            f.write(json.dumps(sugg.to_dict()) + "\n")

            label = sugg.suggested_label.value
            conf = sugg.suggested_confidence.value
            ev = sugg.suggested_evidence_type.value
            label_counts[label] += 1
            conf_counts[conf] += 1
            evidence_counts[ev] += 1

            if sugg.adjudication_recommended:
                adjudication_count += 1

            stratum = item.sampling_stratum
            if stratum not in stratum_distribution:
                stratum_distribution[stratum] = Counter()
            stratum_distribution[stratum][label] += 1

    summary_data: Dict[str, Any] = {
        "queue_source": str(queue_path),
        "total_pairs_evaluated": len(items),
        "model_identifier": args.model,
        "suggested_label_distribution": dict(label_counts),
        "suggested_confidence_distribution": dict(conf_counts),
        "suggested_evidence_distribution": dict(evidence_counts),
        "adjudication_recommended_count": adjudication_count,
        "stratum_breakdown": {
            s: dict(counts) for s, counts in stratum_distribution.items()
        },
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print("=" * 65)
    print("AI-ASSISTED ANNOTATION SUGGESTION SUMMARY")
    print("=" * 65)
    print(f"Total pairs evaluated:      {len(items)}")
    print(f"Model ID:                  {args.model}")
    print(f"Adjudications recommended: {adjudication_count}")
    print("\nSuggested Label Distribution:")
    for label, count in sorted(label_counts.items()):
        pct = (count / len(items)) * 100
        print(f"  {label:<20} {count:>3} ({pct:>5.1f}%)")
    print("\nSuggested Confidence Distribution:")
    for conf, count in sorted(conf_counts.items()):
        pct = (count / len(items)) * 100
        print(f"  {conf:<20} {count:>3} ({pct:>5.1f}%)")
    print("\nTop Evidence Types:")
    for ev, count in evidence_counts.most_common():
        pct = (count / len(items)) * 100
        print(f"  {ev:<35} {count:>3} ({pct:>5.1f}%)")
    print("=" * 65)
    print(f"Suggestions saved to: {out_path}")
    print(f"Summary report saved to: {report_path}")


if __name__ == "__main__":
    main()
