"""Explainable deterministic matching score engine.

Implements transparent weighted scoring, contradiction guardrails, and structured
evidence generation for POI entity resolution without black-box ML models.
"""

from typing import Dict, Any, List, Tuple, Optional
from src.poi_conflation.matching.config import MatchingConfig


class MatchingDecision:
    MATCH = "MATCH"
    NON_MATCH = "NON_MATCH"
    UNCERTAIN = "UNCERTAIN"


class ExplainableMatchingEngine:
    """Computes deterministic scores [0, 1] and interpretable matching decisions with guardrails."""

    def __init__(self, config: Optional[MatchingConfig] = None):
        self.config = config or MatchingConfig.load()
        self.weights = self.config.feature_group_weights
        self.thresholds = self.config.thresholds
        self.guardrails = self.config.guardrails

    def evaluate_pair(self, feat: Dict[str, float]) -> Dict[str, Any]:
        """Evaluate a single feature dictionary and return score, decision, and explanation."""
        # 1. Name group subscore
        is_empty = feat.get("feat_is_empty_name", 0.0) == 1.0
        if is_empty:
            name_score = 0.0
        else:
            name_score = (
                feat.get("feat_exact_name_match", 0.0) * 0.25
                + feat.get("feat_jaro_winkler", 0.0) * 0.25
                + feat.get("feat_token_sort_ratio", 0.0) * 0.25
                + feat.get("feat_token_set_ratio", 0.0) * 0.15
                + feat.get("feat_char_3gram_jaccard", 0.0) * 0.10
            )

        # 2. Transliteration / Phonetic group subscore
        translit_avail = feat.get("feat_translit_available", 0.0) == 1.0
        phonetic_sim = feat.get("feat_indic_phonetic_sim", 0.0)
        translit_sim = feat.get("feat_translit_sim", 0.0)
        translit_exact = feat.get("feat_translit_exact_match", 0.0)

        if translit_avail:
            translit_score = max(
                phonetic_sim,
                translit_exact * 0.50 + translit_sim * 0.50,
            )
        else:
            # When Kannada transliteration is not applicable, use Indian phonetic similarity
            translit_score = phonetic_sim

        # 3. Spatial group subscore (distance-band weighted proximity)
        dist_m = feat.get("feat_distance_meters", 999999.0)
        missing_coords = feat.get("feat_missing_coords", 0.0) == 1.0

        if missing_coords:
            spatial_score = 0.0
        else:
            spatial_score = (
                feat.get("feat_dist_band_le15m", 0.0) * 0.40
                + feat.get("feat_dist_band_le30m", 0.0) * 0.30
                + feat.get("feat_dist_band_le50m", 0.0) * 0.20
                + feat.get("feat_dist_band_le100m", 0.0) * 0.10
            )

        # 4. Category group subscore
        exact_cat = feat.get("feat_exact_category_match", 0.0)
        strong_cat = feat.get("feat_category_strongly_compat", 0.0)
        potential_cat = feat.get("feat_category_potentially_compat", 0.0)
        unknown_cat = feat.get("feat_category_unknown_compat", 0.0)
        incompat_cat = feat.get("feat_category_incompatible", 0.0)

        if incompat_cat == 1.0:
            category_score = 0.0
        elif exact_cat == 1.0:
            category_score = 1.0
        elif strong_cat == 1.0:
            category_score = 0.80
        elif potential_cat == 1.0:
            category_score = 0.40
        elif unknown_cat == 1.0:
            category_score = 0.20
        else:
            category_score = 0.10

        # 5. Candidate blocking strategy subscore
        strat_exact = feat.get("feat_strat_exact_name", 0.0)
        strat_spat = feat.get("feat_strat_spatial_50m", 0.0)
        strat_tok = feat.get("feat_strat_token_containment", 0.0)
        strat_trans = feat.get("feat_strat_translit", 0.0)
        strat_phon = feat.get("feat_strat_phonetic", 0.0)
        multi_strat = feat.get("feat_multi_strategy_overlap", 0.0)

        strat_score = min(
            1.0,
            strat_exact * 0.40
            + strat_spat * 0.20
            + strat_tok * 0.20
            + strat_trans * 0.10
            + strat_phon * 0.10
            + multi_strat * 0.20,
        )

        # Weighted aggregate score
        w_name = self.weights.get("name", 0.35)
        w_trans = self.weights.get("transliteration", 0.15)
        w_spat = self.weights.get("spatial", 0.30)
        w_cat = self.weights.get("category", 0.15)
        w_strat = self.weights.get("strategy", 0.05)

        contrib_name = w_name * name_score
        contrib_trans = w_trans * translit_score
        contrib_spat = w_spat * spatial_score
        contrib_cat = w_cat * category_score
        contrib_strat = w_strat * strat_score

        raw_score = contrib_name + contrib_trans + contrib_spat + contrib_cat + contrib_strat
        raw_score = max(0.0, min(1.0, raw_score))

        final_score = raw_score
        applied_guardrails: List[str] = []

        # Default decision based on thresholds
        match_thresh = self.thresholds.get("match_min_score", 0.75)
        uncertain_thresh = self.thresholds.get("uncertain_min_score", 0.40)

        if final_score >= match_thresh:
            decision = MatchingDecision.MATCH
        elif final_score < uncertain_thresh:
            decision = MatchingDecision.NON_MATCH
        else:
            decision = MatchingDecision.UNCERTAIN

        # --- Contradiction Guardrails ---
        # Guardrail 1: Incompatible category guard
        if incompat_cat == 1.0:
            final_score = min(final_score, 0.35)
            decision = MatchingDecision.NON_MATCH
            applied_guardrails.append("CATEGORY_DISJOINT")

        # Guardrail 2: Excessive spatial separation
        if dist_m > 500.0:
            final_score = min(final_score, 0.20)
            decision = MatchingDecision.NON_MATCH
            applied_guardrails.append("EXCESSIVE_SPATIAL_SEPARATION")

        # Guardrail 3: Same brand different branch guard
        exact_name_match = feat.get("feat_exact_name_match", 0.0) == 1.0
        tok_sort = feat.get("feat_token_sort_ratio", 0.0)
        if dist_m > 100.0 and (exact_name_match or tok_sort >= 0.90):
            final_score = min(final_score, 0.35)
            decision = MatchingDecision.NON_MATCH
            applied_guardrails.append("SAME_BRAND_DIFFERENT_BRANCH")

        # Guardrail 4: Same building different business guard
        if dist_m <= 25.0 and tok_sort < 0.30 and not is_empty:
            final_score = min(final_score, 0.35)
            decision = MatchingDecision.NON_MATCH
            applied_guardrails.append("SAME_BUILDING_DIFFERENT_BUSINESS")

        # Guardrail 5: Empty name guard
        if is_empty:
            if decision == MatchingDecision.MATCH:
                decision = MatchingDecision.UNCERTAIN
            applied_guardrails.append("INSUFFICIENT_NAME_EVIDENCE")

        # --- Explanations and Evidence Gathering ---
        pos_evidence: List[str] = []
        neg_evidence: List[str] = []
        missing_evidence: List[str] = []

        if exact_name_match:
            pos_evidence.append("Exact normalized name match")
        elif tok_sort >= 0.80:
            pos_evidence.append(f"High token sort similarity ({tok_sort:.2f})")
        elif tok_sort < 0.40 and not is_empty:
            neg_evidence.append(f"Low token similarity ({tok_sort:.2f})")

        if is_empty:
            missing_evidence.append("Missing or empty name in one or both records")

        if translit_exact == 1.0:
            pos_evidence.append("Exact match after Kannada-to-Latin transliteration")
        elif translit_avail and translit_sim >= 0.80:
            pos_evidence.append(f"Strong transliteration similarity ({translit_sim:.2f})")

        if phonetic_sim == 1.0 and not is_empty:
            pos_evidence.append("Exact Indian English phonetic equivalence")

        if missing_coords:
            missing_evidence.append("Missing coordinates")
        else:
            if dist_m <= 15.0:
                pos_evidence.append(f"Immediate co-location within 15m ({dist_m:.1f}m)")
            elif dist_m <= 50.0:
                pos_evidence.append(f"Close spatial proximity within 50m ({dist_m:.1f}m)")
            elif dist_m > 200.0:
                neg_evidence.append(f"Substantial spatial separation ({dist_m:.1f}m)")

        if exact_cat == 1.0:
            pos_evidence.append("Identical canonical category")
            cat_rule = "Exact category agreement"
        elif strong_cat == 1.0:
            pos_evidence.append("Strong cross-domain category compatibility")
            cat_rule = "Strongly compatible categories"
        elif potential_cat == 1.0:
            cat_rule = "Potentially compatible commercial domain"
        elif incompat_cat == 1.0:
            neg_evidence.append("Disjoint incompatible categories")
            cat_rule = "Disjoint incompatible category pair"
        else:
            cat_rule = "Unclassified or generic category pairing"

        bearing = feat.get("feat_bearing_deg", -1.0)
        bearing_str = f", bearing {bearing:.1f}°" if bearing >= 0.0 else ""
        spatial_ev = f"{dist_m:.1f}m Euclidean distance in EPSG:32643 UTM 43N{bearing_str}"

        return {
            "final_score": round(final_score, 4),
            "raw_score": round(raw_score, 4),
            "decision": decision,
            "applied_guardrails": applied_guardrails,
            "positive_evidence": pos_evidence,
            "negative_evidence": neg_evidence,
            "missing_evidence": missing_evidence,
            "category_rule": cat_rule,
            "spatial_evidence": spatial_ev,
            "feature_contributions": {
                "name": round(contrib_name, 4),
                "transliteration": round(contrib_trans, 4),
                "spatial": round(contrib_spat, 4),
                "category": round(contrib_cat, 4),
                "strategy": round(contrib_strat, 4),
            },
        }
