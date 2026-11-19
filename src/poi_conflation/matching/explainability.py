"""Explainability and domain-informed reasoning layer for supervised POI matching.

Translates machine learning model feature importances and tree decision paths into
transparent, auditable domain explanations covering:
1. Spatial Proximity
2. Name & String Similarity
3. Kannada Transliteration & Phonetics
4. Category Harmonization & Compatibility
5. Diagnostic Error Archetypes (corporate suffixes, branches, ATMs vs banks, collocated businesses)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("poi_explainability")


class POIModelExplainer:
    """Generates human-readable, domain-informed explanations for pairwise POI predictions."""

    def __init__(self, feature_names: List[str], feature_importances: Optional[Dict[str, Any]] = None):
        self.feature_names = feature_names
        self.feature_importances = feature_importances or {}

    def explain_prediction(
        self,
        features: Dict[str, float],
        match_probability: float,
        decision: str,
        pair_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate structured explanation for a single pair prediction."""
        meta = pair_metadata or {}
        osm_name = meta.get("osm_name_raw", "")
        ov_name = meta.get("ov_name_raw", "")
        osm_cat = meta.get("osm_category", "")
        ov_cat = meta.get("ov_category", "")

        # 1. Spatial Domain Reasoning
        dist = features.get("feat_distance_meters", 0.0)
        if dist <= 15.0:
            spatial_verdict = f"Distance: {dist:.1f}m — Coincident location within single premise boundary"
        elif dist <= 30.0:
            spatial_verdict = f"Distance: {dist:.1f}m — Close proximity consistent with rooftop centroid vs street entrance displacement"
        elif dist <= 50.0:
            spatial_verdict = f"Distance: {dist:.1f}m — Moderate offset within commercial compound / parcel envelope"
        else:
            spatial_verdict = f"Distance: {dist:.1f}m — Substantial spatial displacement exceeding physical premise threshold"

        # 2. Name Domain Reasoning
        jw = features.get("feat_jaro_winkler", 0.0)
        exact_name = features.get("feat_exact_name_match", 0.0)
        tok_contain = features.get("feat_strat_token_containment", 0.0)
        tok_sort = features.get("feat_token_sort_ratio", 0.0)

        if exact_name == 1.0:
            name_verdict = f"Exact normalized name match ('{osm_name}' == '{ov_name}')"
        elif tok_contain == 1.0 or tok_sort >= 0.85:
            name_verdict = f"High token containment / permutation similarity (Jaro-Winkler: {jw:.2f}, TokenSort: {tok_sort:.2f})"
        elif jw >= 0.75:
            name_verdict = f"Moderate string similarity (Jaro-Winkler: {jw:.2f}), likely spelling or punctuation variant"
        else:
            name_verdict = f"Distinct name strings (Jaro-Winkler: {jw:.2f}, TokenSort: {tok_sort:.2f})"

        # 3. Transliteration / Script Reasoning
        translit_avail = features.get("feat_translit_available", 0.0)
        translit_sim = features.get("feat_translit_sim", 0.0)
        phonetic_sim = features.get("feat_indic_phonetic_sim", 0.0)

        if translit_avail == 1.0 and (translit_sim >= 0.80 or phonetic_sim >= 0.80):
            script_verdict = f"Cross-script match verified: Kannada-English transliteration similarity {translit_sim:.2f}, phonetic {phonetic_sim:.2f}"
        elif translit_avail == 1.0:
            script_verdict = f"Bilingual script detected, but transliteration similarity is weak ({translit_sim:.2f})"
        else:
            script_verdict = "Mono-script comparison (Latin/English)"

        # 4. Category Reasoning
        exact_cat = features.get("feat_exact_category_match", 0.0)
        cat_strong = features.get("feat_category_strongly_compat", 0.0)
        cat_incompat = features.get("feat_category_incompatible", 0.0)

        if exact_cat == 1.0 or cat_strong == 1.0:
            category_verdict = f"Compatible taxonomy alignment: OSM '{osm_cat}' vs Overture '{ov_cat}'"
        elif cat_incompat == 1.0:
            category_verdict = f"Incompatible taxonomy conflict: OSM '{osm_cat}' vs Overture '{ov_cat}'"
        else:
            category_verdict = f"Taxonomy compatibility unknown or unmapped: OSM '{osm_cat}' vs Overture '{ov_cat}'"

        # 5. Top Positive & Negative Feature Drivers
        # Weight by feature importance if available, otherwise by deviation from neutral
        drivers = []
        for feat_name in self.feature_names:
            val = features.get(feat_name, 0.0)
            imp_info = self.feature_importances.get(feat_name, {})
            norm_imp = imp_info.get("normalized_importance", 0.02)

            # Heuristic impact:
            if "dist" in feat_name or "delta" in feat_name:
                # Lower distance -> positive impact
                impact = (1.0 - min(1.0, val / 50.0)) * norm_imp if feat_name == "feat_distance_meters" else (val * norm_imp)
                is_positive = (val <= 30.0) if feat_name == "feat_distance_meters" else (val > 0)
            elif "incompatible" in feat_name:
                impact = val * norm_imp
                is_positive = False if val > 0 else True
            else:
                impact = val * norm_imp
                is_positive = val >= 0.5

            drivers.append({
                "feature": feat_name,
                "value": round(float(val), 4),
                "importance_weight": round(float(norm_imp), 4),
                "is_positive": is_positive,
                "score_contribution": round(float(impact), 4),
            })

        positive_drivers = sorted([d for d in drivers if d["is_positive"]], key=lambda x: x["score_contribution"], reverse=True)[:3]
        negative_drivers = sorted([d for d in drivers if not d["is_positive"]], key=lambda x: x["score_contribution"], reverse=True)[:3]

        return {
            "prediction": {
                "decision": decision,
                "match_probability": round(float(match_probability), 4),
            },
            "domain_synthesis": {
                "spatial_proximity": spatial_verdict,
                "name_similarity": name_verdict,
                "transliteration_support": script_verdict,
                "category_compatibility": category_verdict,
            },
            "top_positive_evidence": positive_drivers,
            "top_negative_evidence": negative_drivers,
            "summary_rationale": (
                f"Predicted {decision} (Probability: {match_probability:.2f}). "
                f"{spatial_verdict}. {name_verdict}. {category_verdict}."
            ),
        }
