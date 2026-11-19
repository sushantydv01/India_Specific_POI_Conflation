"""Candidate POI Matching Engine V2 (explainable_rule_baseline_v2).

Builds upon explainable_rule_baseline_v1 by incorporating:
1. Domain-specific corporate suffix normalization (Limited, Ltd, Pvt Ltd, LLP).
2. Locality and branch qualifier separation (e.g. Bangalore-Marathalli, Rajarajeshwarinagar).
3. Temporal and event qualifier handling (e.g. Annual show 2017).
4. Explicit ATM versus Bank facility differentiation.
5. Contextual spatial displacement resolution for commercial rooftops vs. street entrances (<= 50m).
6. Preserves v1 baseline unchanged.
"""

from typing import Dict, Any, List, Optional
from src.poi_conflation.matching.config import MatchingConfig
from src.poi_conflation.matching.engine import MatchingDecision
from src.poi_conflation.matching.normalization import EnhancedNameNormalizer


class ExplainableMatchingEngineV2:
    """Enhanced explainable matching engine with domain-specific qualifier extraction."""

    def __init__(self, config: Optional[MatchingConfig] = None):
        self.config = config or MatchingConfig.load()
        self.weights = self.config.feature_group_weights
        self.thresholds = self.config.thresholds
        self.guardrails = self.config.guardrails
        self.engine_version = "explainable_rule_baseline_v2"
        self.normalizer = EnhancedNameNormalizer()

    def evaluate_pair(
        self,
        feat: Dict[str, float],
        osm_name_raw: Optional[str] = None,
        ov_name_raw: Optional[str] = None,
        osm_category: Optional[str] = None,
        ov_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate a pair feature dictionary and optional raw names/categories."""
        applied_guardrails: List[str] = []
        applied_rules: List[str] = []

        is_empty = feat.get("feat_is_empty_name", 0.0) == 1.0
        dist_m = feat.get("feat_distance_meters", 999999.0)
        missing_coords = feat.get("feat_missing_coords", 0.0) == 1.0

        # Optional raw name processing if provided
        norm_osm = self.normalizer.normalize_and_extract(osm_name_raw) if osm_name_raw else None
        norm_ov = self.normalizer.normalize_and_extract(ov_name_raw) if ov_name_raw else None

        # 1. Name group subscore with containment boost
        tok_set_ratio = feat.get("feat_token_set_ratio", 0.0)
        tok_sort_ratio = feat.get("feat_token_sort_ratio", 0.0)
        jaro_winkler = feat.get("feat_jaro_winkler", 0.0)
        exact_name_match = feat.get("feat_exact_name_match", 0.0) == 1.0

        if is_empty:
            name_score = 0.0
        else:
            base_name_score = (
                feat.get("feat_exact_name_match", 0.0) * 0.25
                + jaro_winkler * 0.25
                + tok_sort_ratio * 0.25
                + tok_set_ratio * 0.15
                + feat.get("feat_char_3gram_jaccard", 0.0) * 0.10
            )

            # Rule V2-1: Contextual Subset Containment Boost
            # When one name is completely contained in the other (tok_set_ratio == 1.0),
            # spatial displacement is <= 50m (entrance-to-rooftop displacement),
            # and name length differs due to corporate/locality expansion
            if tok_set_ratio == 1.0 and dist_m <= 50.0:
                containment_boost = 0.85 * jaro_winkler + 0.15 * tok_set_ratio
                if containment_boost > base_name_score:
                    name_score = containment_boost
                    applied_rules.append("NAME_SUBSET_CONTAINMENT_BOOST_LE50M")
                else:
                    name_score = base_name_score
            else:
                name_score = base_name_score

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
            translit_score = phonetic_sim

        # 3. Spatial group subscore
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

        # Guardrail 3: Same brand different branch guard (distance > 100m)
        if dist_m > 100.0 and (exact_name_match or tok_sort_ratio >= 0.90):
            final_score = min(final_score, 0.35)
            decision = MatchingDecision.NON_MATCH
            applied_guardrails.append("SAME_BRAND_DIFFERENT_BRANCH")

        # Guardrail 4: Same building different business guard (<= 25m, distinct names)
        if dist_m <= 25.0 and tok_sort_ratio < 0.30 and not is_empty:
            final_score = min(final_score, 0.35)
            decision = MatchingDecision.NON_MATCH
            applied_guardrails.append("SAME_BUILDING_DIFFERENT_BUSINESS")

        # Guardrail 5: Empty name guard
        if is_empty:
            if decision == MatchingDecision.MATCH:
                decision = MatchingDecision.UNCERTAIN
            applied_guardrails.append("INSUFFICIENT_NAME_EVIDENCE")

        # Guardrail 6 (V2): ATM versus Bank facility differentiation
        is_atm_pair = False
        if norm_osm and norm_ov:
            if norm_osm["is_atm"] != norm_ov["is_atm"]:
                is_atm_pair = True
        elif osm_category and ov_category:
            if ("atm" in osm_category.lower() or "atm" in ov_category.lower()) and osm_category.lower() != ov_category.lower():
                is_atm_pair = True

        if is_atm_pair:
            # An ATM is a facility of a bank, not the identical POI entity
            final_score = min(final_score, 0.60)
            if decision == MatchingDecision.MATCH:
                decision = MatchingDecision.UNCERTAIN
            applied_guardrails.append("ATM_VS_BANK_FACILITY_DISTINCTION")

        # Guardrail 7 (V2): Contradicting Locality Qualifiers (Different branches within 100m)
        if norm_osm and norm_ov:
            loc_osm = norm_osm.get("locality_qualifier")
            loc_ov = norm_ov.get("locality_qualifier")
            if loc_osm and loc_ov and loc_osm != loc_ov:
                final_score = min(final_score, 0.35)
                decision = MatchingDecision.NON_MATCH
                applied_guardrails.append("CONTRADICTING_BRANCH_LOCALITY")

        # Rule V2-2: Record event / temporal qualifier presence
        if norm_ov and norm_ov.get("event_qualifier"):
            applied_rules.append(f"EVENT_QUALIFIER_DETECTED_{norm_ov['event_qualifier'].upper()}")

        return {
            "final_score": round(final_score, 4),
            "raw_score": round(raw_score, 4),
            "decision": decision,
            "applied_guardrails": applied_guardrails,
            "applied_rules": applied_rules,
            "engine_version": self.engine_version,
            "feature_contributions": {
                "name": round(contrib_name, 4),
                "transliteration": round(contrib_trans, 4),
                "spatial": round(contrib_spat, 4),
                "category": round(contrib_cat, 4),
                "strategy": round(contrib_strat, 4),
            },
        }
