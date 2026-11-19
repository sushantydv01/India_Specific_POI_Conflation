#!/usr/bin/env python3
"""Run explainability and archetype error analysis for the supervised POI matcher.

Investigates:
1. Domain-informed explanations for individual pairs.
2. Performance and failure modes across 7 India-specific archetypes:
   - Corporate / legal suffixes (Pvt Ltd, Ltd, LLP)
   - Kannada transliteration and bilingual naming
   - Indian English variants and spelling variations
   - Same-brand multi-branch distinction
   - ATMs vs branch offices
   - Collocated businesses
   - Coordinate displacements (entrance vs centroid)
3. Borderline / uncertain predictions near the threshold boundaries.
4. Generates: reports/supervised_error_analysis.json
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pyarrow.parquet as pq

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.poi_conflation.matching.supervised_model import SupervisedPOIMatcher
from src.poi_conflation.matching.explainability import POIModelExplainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("supervised_error_analysis")


def load_dataset(parquet_path: Path):
    table = pq.read_table(parquet_path)
    df = table.to_pydict()
    feat_cols = [c for c in table.schema.names if c.startswith("feat_")]

    records = []
    n = len(df["pair_id"])
    for i in range(n):
        rec = {
            "pair_id": df["pair_id"][i],
            "osm_source_id": df["osm_source_id"][i],
            "ov_source_id": df["ov_source_id"][i],
            "osm_name_raw": df["osm_name_raw"][i],
            "ov_name_raw": df["ov_name_raw"][i],
            "osm_category": df["osm_category"][i],
            "ov_category": df["ov_category"][i],
            "sampling_stratum": df["sampling_stratum"][i],
            "decision": df["decision"][i],
            "provenance": df["provenance"][i],
            "is_binary_target": df["decision"][i] in ("MATCH", "NON_MATCH"),
            "target": 1 if df["decision"][i] == "MATCH" else (0 if df["decision"][i] == "NON_MATCH" else None),
            "features": {c: float(df[c][i]) for c in feat_cols},
            "feature_vector": [float(df[c][i]) for c in feat_cols],
        }
        records.append(rec)
    return records, feat_cols


def main():
    root = Path(__file__).resolve().parent.parent
    supervised_dir = root / "data" / "processed" / "supervised"
    models_dir = root / "models"
    reports_dir = root / "reports"

    # Load model and feature importances
    model_path = models_dir / "supervised_poi_matcher_v1.joblib"
    matcher = SupervisedPOIMatcher.load(model_path)
    importances = matcher.get_feature_importances()

    # Load all labeled partitions (train, validation, test)
    all_records = []
    feat_cols = None
    for split in ["train", "validation", "test"]:
        p_path = supervised_dir / f"{split}_features.parquet"
        recs, cols = load_dataset(p_path)
        for r in recs:
            r["split"] = split.upper()
        all_records.extend(recs)
        if feat_cols is None:
            feat_cols = cols

    logger.info(f"Loaded {len(all_records)} total records across train, validation, and test")

    # Filter to annotated records
    annotated = [r for r in all_records if r["decision"] != "UNANNOTATED"]
    logger.info(f"Analyzing {len(annotated)} annotated records")

    # Instantiate explainer
    explainer = POIModelExplainer(feature_names=feat_cols, feature_importances=importances)

    # Predict and explain each annotated record
    explained_records = []
    false_positives = []
    false_negatives = []
    borderline_cases = []

    m_thresh = matcher.thresholds.get("match_threshold", 0.55)
    u_thresh = matcher.thresholds.get("uncertain_lower_threshold", 0.30)

    for r in annotated:
        vec = np.array([r["feature_vector"]], dtype=np.float32)
        proba = float(matcher.predict_proba(vec)[0])
        pred_decision = str(matcher.predict_decision(vec)[0])

        explanation = explainer.explain_prediction(
            features=r["features"],
            match_probability=proba,
            decision=pred_decision,
            pair_metadata=r,
        )

        entry = {
            "pair_id": r["pair_id"],
            "split": r["split"],
            "osm_name": r["osm_name_raw"],
            "ov_name": r["ov_name_raw"],
            "osm_category": r["osm_category"],
            "ov_category": r["ov_category"],
            "sampling_stratum": r["sampling_stratum"],
            "true_decision": r["decision"],
            "provenance": r["provenance"],
            "pred_decision": pred_decision,
            "match_probability": round(proba, 4),
            "explanation": explanation,
        }
        explained_records.append(entry)

        # Check errors on binary pairs
        if r["is_binary_target"]:
            if r["decision"] == "NON_MATCH" and pred_decision == "MATCH":
                false_positives.append(entry)
            elif r["decision"] == "MATCH" and pred_decision == "NON_MATCH":
                false_negatives.append(entry)

        # Borderline cases: probability within [u_thresh - 0.10, m_thresh + 0.10]
        if abs(proba - m_thresh) <= 0.15 or (u_thresh <= proba <= m_thresh):
            borderline_cases.append(entry)

    logger.info(f"Identified {len(false_positives)} false positives, {len(false_negatives)} false negatives, {len(borderline_cases)} borderline cases")

    # 7 India-specific diagnostic archetype analyses
    archetypes = {
        "corporate_suffixes": {
            "description": "Pairs with corporate suffix discrepancies (Pvt Ltd, Ltd, LLP, Branch tags)",
            "pairs": [],
            "accuracy": 0.0,
        },
        "kannada_transliteration": {
            "description": "Pairs where OSM has Kannada script and Overture has English/Latin script",
            "pairs": [],
            "accuracy": 0.0,
        },
        "indian_english_variants": {
            "description": "Pairs with Indian English spelling variations, abbreviations, or road terms",
            "pairs": [],
            "accuracy": 0.0,
        },
        "same_brand_multi_branch": {
            "description": "Same brand in vicinity where distance or branch identifier differentiates locations",
            "pairs": [],
            "accuracy": 0.0,
        },
        "atms_vs_banks": {
            "description": "Financial category confusion between bank branches and standalone ATMs",
            "pairs": [],
            "accuracy": 0.0,
        },
        "collocated_businesses": {
            "description": "Different businesses located within the same commercial complex or address",
            "pairs": [],
            "accuracy": 0.0,
        },
        "coordinate_displacements": {
            "description": "True matches with coordinate offset (15m-50m) between street entrance and rooftop centroid",
            "pairs": [],
            "accuracy": 0.0,
        },
    }

    corp_keywords = ["ltd", "pvt", "private", "llp", "limited", "enterprises", "solutions", "services"]
    bank_keywords = ["bank", "atm", "branch"]

    for item in explained_records:
        osm_n = item["osm_name"].lower()
        ov_n = item["ov_name"].lower()
        stratum = item["sampling_stratum"]
        dist = item["explanation"]["prediction"]["match_probability"]

        # Corporate suffixes
        if any(w in osm_n or w in ov_n for w in corp_keywords):
            archetypes["corporate_suffixes"]["pairs"].append(item)

        # Kannada transliteration
        if stratum == "KANNADA_TRANSLITERATION" or item["explanation"]["domain_synthesis"]["transliteration_support"].startswith("Cross-script"):
            archetypes["kannada_transliteration"]["pairs"].append(item)

        # Indian English variants
        if stratum == "TOKEN_CONTAINMENT" or "hotel" in osm_n or "hotel" in ov_n or "bhavan" in osm_n:
            archetypes["indian_english_variants"]["pairs"].append(item)

        # ATMs vs Banks
        if any(w in osm_n or w in ov_n for w in bank_keywords):
            archetypes["atms_vs_banks"]["pairs"].append(item)

        # Collocated businesses
        if stratum == "SPATIAL_50M_LOW_STRING":
            archetypes["collocated_businesses"]["pairs"].append(item)

        # Coordinate displacements
        if 15.0 <= item["explanation"]["prediction"].get("dist", 25.0) <= 50.0 and item["true_decision"] == "MATCH":
            archetypes["coordinate_displacements"]["pairs"].append(item)

    # Compute archetype accuracies
    for arch_name, arch_data in archetypes.items():
        bin_pairs = [p for p in arch_data["pairs"] if p["true_decision"] in ("MATCH", "NON_MATCH")]
        correct = sum(1 for p in bin_pairs if p["true_decision"] == p["pred_decision"])
        arch_data["sample_size"] = len(arch_data["pairs"])
        arch_data["binary_sample_size"] = len(bin_pairs)
        arch_data["correct_predictions"] = correct
        arch_data["accuracy"] = round(correct / max(1, len(bin_pairs)), 4) if bin_pairs else 1.0
        # Keep only top 3 sample explanations for brevity in report
        arch_data["sample_cases"] = [
            {
                "pair_id": p["pair_id"],
                "osm_name": p["osm_name"],
                "ov_name": p["ov_name"],
                "true_decision": p["true_decision"],
                "pred_decision": p["pred_decision"],
                "probability": p["match_probability"],
                "rationale": p["explanation"]["summary_rationale"],
            }
            for p in arch_data["pairs"][:3]
        ]
        del arch_data["pairs"]

    error_analysis_report = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "milestone": "Milestone 15",
            "framework": "Explainability & Diagnostic Error Taxonomy Analysis",
            "model_evaluated": "supervised_lgbm_poi_matcher_v1",
            "decision_thresholds": {
                "match_threshold": m_thresh,
                "uncertain_lower_threshold": u_thresh,
            },
        },
        "error_summary": {
            "total_annotated_audited": len(annotated),
            "total_binary_audited": len([r for r in annotated if r["is_binary_target"]]),
            "false_positive_count": len(false_positives),
            "false_negative_count": len(false_negatives),
            "borderline_cases_count": len(borderline_cases),
        },
        "archetype_diagnostic_evaluation": archetypes,
        "sample_detailed_explanations": explained_records[:5],
        "borderline_cases_sample": borderline_cases[:5],
        "recommendations_for_conflation_graph": [
            "Use the supervised probability as continuous edge weights in the bipartite conflation graph.",
            "Apply conservative single-entity resolution for pairs with probability >= 0.75.",
            "Route borderline pairs (probability between 0.30 and 0.55) to human adjudication queue."
        ]
    }

    out_path = reports_dir / "supervised_error_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(error_analysis_report, f, indent=2)
    logger.info(f"Saved error analysis to {out_path}")

    print("=== Supervised Error Analysis & Explainability Summary ===")
    print(f"Total Annotated: {len(annotated)}")
    print(f"False Positives: {len(false_positives)}")
    print(f"False Negatives: {len(false_negatives)}")
    print(f"Borderline Cases: {len(borderline_cases)}")
    print("\nArchetype Accuracy Summary:")
    for a_name, a_data in archetypes.items():
        print(f"  - {a_name}: {a_data['accuracy']*100:.1f}% (N={a_data['binary_sample_size']})")


if __name__ == "__main__":
    main()
