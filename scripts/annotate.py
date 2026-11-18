"""Terminal-based interactive annotation tool for human ground truth labelling.

Usage:
    python scripts/annotate.py --annotator reviewer_1 --pilot --ai-assisted
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationQueueItem,
)
from src.poi_conflation.benchmark.ai_schema import (
    HumanAction,
    AIPairSuggestion,
)
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

EVIDENCE_INV_MAP = {v: k for k, v in EVIDENCE_MAP.items()}
DECISION_INV_MAP = {v: k for k, v in DECISION_MAP.items()}
CONFIDENCE_INV_MAP = {v: k for k, v in CONFIDENCE_MAP.items()}


def print_ai_suggestion_box(sugg: AIPairSuggestion):
    """Render a structured, formatted display of the AI suggestion."""
    print()
    print("  +----------------------- AI ASSISTANT SUGGESTION -----------------------+")
    print(f"  | Suggested Decision:  {sugg.suggested_label.value:<48} |")
    print(f"  | Suggested Conf:      {sugg.suggested_confidence.value:<48} |")
    print(f"  | Suggested Evidence:  {sugg.suggested_evidence_type.value:<48} |")
    print(f"  | Model Identifier:    {sugg.model_identifier:<48} |")
    print("  |                                                                        |")
    print("  | Explanation:                                                           |")

    # Word-wrap explanation at 68 chars
    words = sugg.explanation.split()
    line = "  |   "
    for word in words:
        if len(line) + len(word) + 1 > 73:
            print(f"{line:<74} |")
            line = f"  |   {word} "
        else:
            line += f"{word} "
    if line.strip():
        print(f"{line:<74} |")

    if sugg.supporting_evidence:
        print("  |                                                                        |")
        print("  | Supporting Evidence:                                                   |")
        for ev in sugg.supporting_evidence:
            print(f"  |   + {ev:<66} |")

    if sugg.contradictory_evidence:
        print("  |                                                                        |")
        print("  | Contradictory Evidence:                                                |")
        for ev in sugg.contradictory_evidence:
            print(f"  |   - {ev:<66} |")

    if sugg.missing_information:
        print("  |                                                                        |")
        print("  | Missing Attributes (Not in Source Data):                               |")
        for m in sugg.missing_information:
            print(f"  |   ? {m:<66} |")

    print("  +------------------------------------------------------------------------+")
    print()


def prompt_manual_decision() -> Optional[LabelDecision]:
    while True:
        cmd = input("Decision [1: MATCH, 2: NON_MATCH, 3: UNCERTAIN, 4: NEEDS_ADJUDICATION, s: skip, q: quit]: ").strip().lower()
        if cmd == "q":
            return None
        if cmd == "s":
            return "skip"
        if cmd in DECISION_MAP:
            return DECISION_MAP[cmd]
        print("Invalid input. Please enter 1, 2, 3, 4, s, or q.")


def prompt_manual_confidence() -> ConfidenceLevel:
    while True:
        c_cmd = input("Confidence [1: HIGH, 2: MEDIUM, 3: LOW]: ").strip()
        if c_cmd in CONFIDENCE_MAP:
            return CONFIDENCE_MAP[c_cmd]
        print("Invalid input. Please enter 1, 2, or 3.")


def prompt_manual_evidence() -> EvidenceType:
    print("Evidence Reason:")
    print("  1: EXACT_NAME_AND_LOCATION        6: SAME_BRAND_DIFFERENT_BRANCH")
    print("  2: TRANSLITERATION_OR_PHONETIC    7: PARENT_CHILD_RELATION")
    print("  3: NAME_EXPANSION_OR_ACRONYM      8: CATEGORY_DISJOINT")
    print("  4: STREET_LEVEL_DISPLACEMENT      9: INSUFFICIENT_EVIDENCE")
    print("  5: SAME_BUILDING_DIFFERENT_BIZ   10: OTHER")
    while True:
        e_cmd = input("Select Evidence [1-10]: ").strip()
        if e_cmd in EVIDENCE_MAP:
            return EVIDENCE_MAP[e_cmd]
        print("Invalid input. Please select 1 through 10.")


def main():
    parser = argparse.ArgumentParser(description="Interactive Human Annotation CLI")
    parser.add_argument("--annotator", type=str, default="annotator_1", help="Annotator identifier")
    parser.add_argument("--pilot", action="store_true", help="Annotate the 50-pair pilot batch specifically")
    parser.add_argument("--queue", type=str, default=None, help="Explicit path to queue CSV")
    parser.add_argument("--ai-assisted", action="store_true", help="Enable AI-assisted suggestions and review workflow")
    parser.add_argument("--suggestions", type=str, default=None, help="Explicit path to AI suggestions JSONL")
    args = parser.parse_args()

    if args.queue:
        queue_path = args.queue
    elif args.pilot:
        queue_path = "data/processed/benchmark/pilot_batch_50.csv"
    else:
        queue_path = "data/processed/benchmark/annotation_queue.csv"

    suggestions_path = args.suggestions or "data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl"
    workflow = AnnotationWorkflow(
        queue_csv=queue_path,
        ai_suggestions_file=suggestions_path,
    )
    unannotated = workflow.get_unannotated_items(args.annotator)
    total_queue = len(workflow.load_queue())
    completed = total_queue - len(unannotated)

    mode_label = "PILOT BATCH (50 pairs)" if args.pilot or "pilot" in queue_path else "MAIN QUEUE (500 pairs)"
    ai_label = "ENABLED" if args.ai_assisted else "DISABLED (BLIND INDEPENDENT REVIEW)"

    print("=" * 70)
    print(f"POI CONFLATION BENCHMARK — INTERACTIVE ANNOTATION TOOL [{mode_label}]")
    print("=" * 70)
    print(f"Annotator:            {args.annotator}")
    print(f"Queue File:           {queue_path}")
    print(f"AI Assistance:        {ai_label}")
    print(f"Completed / Total:    {completed} / {total_queue}")
    print(f"Remaining in Queue:   {len(unannotated)}")
    print("=" * 70)

    ai_suggestions = {}
    if args.ai_assisted:
        ai_suggestions = workflow.load_ai_suggestions()
        print(f"Loaded {len(ai_suggestions)} AI suggestions from {suggestions_path}\n")

    if not unannotated:
        print("\nAll items in the queue have been annotated! Congratulations.")
        return

    print("Controls: [q] Save & Quit | [s] Skip to next pair\n")

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

        sugg = ai_suggestions.get(item.pair_id) if args.ai_assisted else None

        if args.ai_assisted and sugg:
            print_ai_suggestion_box(sugg)
            print("Quick Actions with AI Suggestion:")
            print(f"  [a] Accept suggestion verbatim ({sugg.suggested_label.value} / {sugg.suggested_confidence.value} / {sugg.suggested_evidence_type.value})")
            print("  [m] Modify suggestion (keep base, adjust decision/confidence/evidence/notes)")
            print("  [r] Reject suggestion (enter custom decision, confidence, and evidence)")
            print("  [s] Skip pair | [q] Quit session")
            print()

            while True:
                action_choice = input("Select Action [a: Accept, m: Modify, r: Reject, s: Skip, q: Quit]: ").strip().lower()
                if action_choice in ("a", "m", "r", "s", "q"):
                    break
                print("Invalid choice. Enter a, m, r, s, or q.")

            if action_choice == "q":
                print("\nSaving session and exiting. Goodbye!")
                return
            if action_choice == "s":
                print("Skipped pair.")
                continue

            if action_choice == "a":
                decision = sugg.suggested_label
                confidence = sugg.suggested_confidence
                evidence = sugg.suggested_evidence_type
                human_action = HumanAction.ACCEPTED
                notes = input("Optional Notes (Enter to keep empty): ").strip() or None

            elif action_choice == "m":
                human_action = HumanAction.MODIFIED
                # Modify Decision
                def_dec_idx = DECISION_INV_MAP[sugg.suggested_label]
                dec_in = input(f"Decision [1: MATCH, 2: NON_MATCH, 3: UNCERTAIN, 4: NEEDS_ADJUDICATION] (default {def_dec_idx}: {sugg.suggested_label.value}): ").strip()
                decision = DECISION_MAP[dec_in] if dec_in in DECISION_MAP else sugg.suggested_label

                # Modify Confidence
                def_conf_idx = CONFIDENCE_INV_MAP[sugg.suggested_confidence]
                conf_in = input(f"Confidence [1: HIGH, 2: MEDIUM, 3: LOW] (default {def_conf_idx}: {sugg.suggested_confidence.value}): ").strip()
                confidence = CONFIDENCE_MAP[conf_in] if conf_in in CONFIDENCE_MAP else sugg.suggested_confidence

                # Modify Evidence
                def_ev_idx = EVIDENCE_INV_MAP[sugg.suggested_evidence_type]
                print("Evidence Reason: 1: EXACT, 2: TRANSLIT, 3: EXPANSION, 4: STREET_DISP, 5: SAME_BLDG, 6: SAME_BRAND, 7: PARENT_CHILD, 8: CAT_DISJOINT, 9: INSUFF, 10: OTHER")
                ev_in = input(f"Select Evidence [1-10] (default {def_ev_idx}: {sugg.suggested_evidence_type.value}): ").strip()
                evidence = EVIDENCE_MAP[ev_in] if ev_in in EVIDENCE_MAP else sugg.suggested_evidence_type

                notes = input("Notes (explain rationale for modification): ").strip() or None

            else:  # action_choice == 'r'
                human_action = HumanAction.REJECTED
                print("Enter your independent decision to reject AI suggestion:")
                decision = prompt_manual_decision()
                if decision is None:
                    return
                if decision == "skip":
                    continue
                confidence = prompt_manual_confidence()
                evidence = prompt_manual_evidence()
                notes = input("Notes (explain why AI suggestion was rejected): ").strip() or None

        else:
            # Independent review (Blind or AI disabled)
            human_action = HumanAction.INDEPENDENT
            decision = prompt_manual_decision()
            if decision is None:
                print("\nSaving session and exiting. Goodbye!")
                return
            if decision == "skip":
                print("Skipped pair.")
                continue

            confidence = prompt_manual_confidence()
            evidence = prompt_manual_evidence()
            notes = input("Optional Notes (press Enter to skip): ").strip() or None

        workflow.record_decision(
            queue_item=item,
            decision=decision,
            annotator_id=args.annotator,
            confidence=confidence,
            evidence_type=evidence,
            notes=notes,
            human_action=human_action,
            ai_suggestion=sugg,
        )
        print(f"Decision recorded: {decision.value} ({confidence.value}) [Action: {human_action.value}]")
        print()


if __name__ == "__main__":
    main()
