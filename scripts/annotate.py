"""Terminal-based interactive annotation tool for human ground truth labelling.

Usage:
    python scripts/annotate.py --annotator expert_1
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.benchmark.schema import LabelDecision, ConfidenceLevel, EvidenceType
from src.poi_conflation.benchmark.workflow import AnnotationWorkflow


DECISION_MAP = {
    "1": LabelDecision.MATCH,
    "2": LabelDecision.NON_MATCH,
    "3": LabelDecision.UNCERTAIN,
    "4": LabelDecision.NEEDS_ADJUDICATION,
}

CONFIDENCE_MAP = {
    "1": ConfidenceLevel.HIGH,
    "2": ConfidenceLevel.MEDIUM,
    "3": ConfidenceLevel.LOW,
}

EVIDENCE_MAP = {
    "1": EvidenceType.EXACT_NAME_AND_LOCATION,
    "2": EvidenceType.TRANSLITERATION_OR_PHONETIC_MATCH,
    "3": EvidenceType.NAME_EXPANSION_OR_ACRONYM,
    "4": EvidenceType.STREET_LEVEL_DISPLACEMENT,
    "5": EvidenceType.SAME_BUILDING_DIFFERENT_BUSINESS,
    "6": EvidenceType.SAME_BRAND_DIFFERENT_BRANCH,
    "7": EvidenceType.PARENT_CHILD_RELATION,
    "8": EvidenceType.CATEGORY_DISJOINT,
    "9": EvidenceType.INSUFFICIENT_EVIDENCE,
    "10": EvidenceType.OTHER,
}


def main():
    parser = argparse.ArgumentParser(description="Interactive Human Annotation CLI")
    parser.add_argument("--annotator", type=str, default="annotator_1", help="Annotator identifier")
    parser.add_argument("--pilot", action="store_true", help="Annotate the 50-pair pilot batch specifically")
    parser.add_argument("--queue", type=str, default=None, help="Explicit path to queue CSV")
    args = parser.parse_args()

    if args.queue:
        queue_path = args.queue
    elif args.pilot:
        queue_path = "data/processed/benchmark/pilot_batch_50.csv"
    else:
        queue_path = "data/processed/benchmark/annotation_queue.csv"

    workflow = AnnotationWorkflow(queue_csv=queue_path)
    unannotated = workflow.get_unannotated_items(args.annotator)
    total_queue = len(workflow.load_queue())
    completed = total_queue - len(unannotated)

    mode_label = "PILOT BATCH (50 pairs)" if args.pilot or "pilot" in queue_path else "MAIN QUEUE (500 pairs)"

    print("=" * 70)
    print(f"POI CONFLATION BENCHMARK — INTERACTIVE ANNOTATION TOOL [{mode_label}]")
    print("=" * 70)
    print(f"Annotator:          {args.annotator}")
    print(f"Queue File:         {queue_path}")
    print(f"Completed / Total:  {completed} / {total_queue}")
    print(f"Remaining in Queue: {len(unannotated)}")
    print("=" * 70)

    if not unannotated:
        print("\nAll items in the queue have been annotated! Congratulations.")
        return

    print("\nControls: [q] Save & Quit | [s] Skip to next pair\n")

    for idx, item in enumerate(unannotated, start=completed + 1):
        print("-" * 70)
        print(f"Pair [{idx}/{total_queue}] | Stratum: {item.sampling_stratum} | Pair ID: {item.pair_id}")
        print("-" * 70)
        print(f"  OSM Record:       {item.osm_source_id}")
        print(f"    Raw Name:       {item.osm_name_raw}")
        if item.osm_name_kn:
            print(f"    Kannada Name:   {item.osm_name_kn}")
        print(f"    Normalized:     {item.osm_name_normalized}")
        print(f"    Category:       {item.osm_category}")
        print(f"    Coordinates:    ({item.osm_latitude:.6f}, {item.osm_longitude:.6f})")
        print()
        print(f"  Overture Record:  {item.ov_source_id}")
        print(f"    Raw Name:       {item.ov_name_raw}")
        print(f"    Normalized:     {item.ov_name_normalized}")
        print(f"    Category:       {item.ov_category}")
        print(f"    Coordinates:    ({item.ov_latitude:.6f}, {item.ov_longitude:.6f})")
        print()
        print(f"  Distance:         {item.distance_meters:.2f} meters")
        print(f"  Category Rel:     {item.category_compatibility}")
        print(f"  Strategies:       {item.blocking_strategies}")
        print("-" * 70)

        # Prompt Decision
        while True:
            cmd = input("Decision [1: MATCH, 2: NON_MATCH, 3: UNCERTAIN, 4: NEEDS_ADJUDICATION, s: skip, q: quit]: ").strip().lower()
            if cmd == "q":
                print("\nSaving session and exiting. Goodbye!")
                return
            if cmd == "s":
                print("Skipped pair.")
                break
            if cmd in DECISION_MAP:
                decision = DECISION_MAP[cmd]
                break
            print("Invalid input. Please enter 1, 2, 3, 4, s, or q.")

        if cmd == "s":
            continue

        # Prompt Confidence
        while True:
            c_cmd = input("Confidence [1: HIGH, 2: MEDIUM, 3: LOW]: ").strip()
            if c_cmd in CONFIDENCE_MAP:
                confidence = CONFIDENCE_MAP[c_cmd]
                break
            print("Invalid input. Please enter 1, 2, or 3.")

        # Prompt Evidence
        print("Evidence Reason:")
        print("  1: EXACT_NAME_AND_LOCATION        6: SAME_BRAND_DIFFERENT_BRANCH")
        print("  2: TRANSLITERATION_OR_PHONETIC    7: PARENT_CHILD_RELATION")
        print("  3: NAME_EXPANSION_OR_ACRONYM      8: CATEGORY_DISJOINT")
        print("  4: STREET_LEVEL_DISPLACEMENT      9: INSUFFICIENT_EVIDENCE")
        print("  5: SAME_BUILDING_DIFFERENT_BIZ   10: OTHER")
        while True:
            e_cmd = input("Select Evidence [1-10]: ").strip()
            if e_cmd in EVIDENCE_MAP:
                evidence = EVIDENCE_MAP[e_cmd]
                break
            print("Invalid input. Please select 1 through 10.")

        notes = input("Optional Notes (press Enter to skip): ").strip()
        notes_val = notes if notes else None

        workflow.record_decision(
            queue_item=item,
            decision=decision,
            annotator_id=args.annotator,
            confidence=confidence,
            evidence_type=evidence,
            notes=notes_val
        )
        print(f"Decision recorded: {decision.value} ({confidence.value})")


if __name__ == "__main__":
    main()
