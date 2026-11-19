"""Explainability and domain-informed reasoning layer for supervised POI matching.

Translates machine learning model feature importances and tree decision paths into
transparent, auditable domain explanations covering:
1. Spatial Proximity and Contradictions
2. Name & String Similarity (including missing and generic names)
3. Kannada Transliteration & Phonetics
4. Category Harmonization & Incompatibility
5. Pair-Specific TreeSHAP Feature Contributions
6. Diagnostic Error Archetypes (corporate suffixes, branches, ATMs vs banks, collocated businesses)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np

logger = logging.getLogger("poi_explainability")


class POIModelExplainer:
    """Generates human-readable, domain-informed explanations for pairwise POI predictions."""

    def __init__(
        self,
        feature_names: List[str],
        feature_importances: Optional[Dict[str, Any]] = None,
        estimator: Optional[Any] = None,
    ):
        self.feature_names = feature_names
        self.feature_importances = feature_importances or {}
        self.estimator = estimator

    def explain_prediction(
        self,
        features: Dict[str, float],
        match_probability: float,
        decision: str,
        pair_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate structured explanation for a single pair prediction."""
        meta = pair_metadata or {}
        osm_name = meta.get("osm_name_raw", meta.get("osm_name", ""))
        ov_name = meta.get("ov_name_raw", meta.get("ov_name", ""))
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
            spatial_verdict = f"Spatial contradiction: distance {dist:.1f}m exceeds urban premise envelope"

        # 2. Name Domain Reasoning (including generic and missing names)
        jw = features.get("feat_jaro_winkler", 0.0)
        exact_name = features.get("feat_exact_name_match", 0.0)
        tok_contain = features.get("feat_strat_token_containment", 0.0)
        tok_sort = features.get("feat_token_sort_ratio", 0.0)
        is_empty = features.get("feat_is_empty_name", 0.0)
        is_generic = features.get("feat_is_generic_name", 0.0)

        if is_empty == 1.0 or not osm_name.strip() or not ov_name.strip():
            name_verdict = f"Missing / unpopulated name attribute in one or both records ('{osm_name}' vs '{ov_name}')"
        elif is_generic == 1.0:
            name_verdict = f"High-frequency generic commercial name ('{osm_name}') requiring strong secondary corroboration"
        elif exact_name == 1.0:
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

        if cat_incompat == 1.0:
            category_verdict = f"Incompatible taxonomy conflict: OSM '{osm_cat}' vs Overture '{ov_cat}'"
        elif exact_cat == 1.0 or cat_strong == 1.0:
            category_verdict = f"Compatible taxonomy alignment: OSM '{osm_cat}' vs Overture '{ov_cat}'"
        else:
            category_verdict = f"Taxonomy compatibility unknown or unmapped: OSM '{osm_cat}' vs Overture '{ov_cat}'"

        # 5. Top Positive & Negative Feature Drivers
        # Try exact TreeSHAP attribution if booster is available
        shap_available = False
        positive_drivers = []
        negative_drivers = []

        if self.estimator is not None and hasattr(self.estimator, "booster_"):
            try:
                vec = np.array([[features.get(c, 0.0) for c in self.feature_names]], dtype=np.float32)
                shap_contribs = self.estimator.booster_.predict(vec, pred_contrib=True)[0]
                feat_shaps = shap_contribs[:-1]  # Exclude expected value (bias)
                shap_available = True

                for feat_name, shap_val in zip(self.feature_names, feat_shaps):
                    val = features.get(feat_name, 0.0)
                    driver_info = {
                        "feature": feat_name,
                        "value": round(float(val), 4),
                        "attribution_method": "TreeSHAP_log_odds",
                        "impact": round(float(shap_val), 4),
                    }
                    if shap_val > 0:
                        positive_drivers.append(driver_info)
                    elif shap_val < 0:
                        negative_drivers.append(driver_info)

                positive_drivers.sort(key=lambda x: x["impact"], reverse=True)
                negative_drivers.sort(key=lambda x: abs(x["impact"]), reverse=True)
                positive_drivers = positive_drivers[:3]
                negative_drivers = negative_drivers[:3]
            except Exception as e:
                logger.debug(f"TreeSHAP calculation fallback: {e}")
                shap_available = False

        if not shap_available:
            drivers = []
            for feat_name in self.feature_names:
                val = features.get(feat_name, 0.0)
                imp_info = self.feature_importances.get(feat_name, {})
                norm_imp = imp_info.get("normalized_importance", 0.02)

                if "dist" in feat_name or "delta" in feat_name:
                    impact = (1.0 - min(1.0, val / 50.0)) * norm_imp if feat_name == "feat_distance_meters" else (val * norm_imp)
                    is_positive = (val <= 30.0) if feat_name == "feat_distance_meters" else (val > 0)
                elif "incompatible" in feat_name or "empty" in feat_name:
                    impact = val * norm_imp
                    is_positive = False if val > 0 else True
                else:
                    impact = val * norm_imp
                    is_positive = val >= 0.5

                drivers.append({
                    "feature": feat_name,
                    "value": round(float(val), 4),
                    "attribution_method": "importance_proxy",
                    "impact": round(float(impact), 4),
                    "is_positive": is_positive,
                })

            positive_drivers = sorted([d for d in drivers if d.get("is_positive")], key=lambda x: x["impact"], reverse=True)[:3]
            negative_drivers = sorted([d for d in drivers if not d.get("is_positive")], key=lambda x: x["impact"], reverse=True)[:3]

        return {
            "prediction": {
                "decision": decision,
                "model_match_score": round(float(match_probability), 4),
                "match_probability": round(float(match_probability), 4),
                "calibration_status": "uncalibrated_model_score",
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
                f"Predicted {decision} (Model Score: {match_probability:.2f}). "
                f"{spatial_verdict}. {name_verdict}. {category_verdict}."
            ),
        }
