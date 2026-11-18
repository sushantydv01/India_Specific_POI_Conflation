"""AI-assisted pair analysis engine for POI conflation benchmark annotation.

Provides:
- AISuggestionProvider: Abstract protocol for suggestion engines.
- HeuristicAIAnalyzer: Deterministic, high-precision domain-rule suggestion analyzer
  tailored to Indian urban POI naming, Kannada script, and multi-attribute blocking.
- Extensible architecture to plug in external LLM providers when configured.
"""

import re
from abc import ABC, abstractmethod
from typing import List, Optional, Set, Dict, Any, Tuple
from rapidfuzz import fuzz

from src.poi_conflation.benchmark.schema import (
    LabelDecision,
    ConfidenceLevel,
    EvidenceType,
    AnnotationQueueItem,
)
from src.poi_conflation.benchmark.ai_schema import AIPairSuggestion
from src.poi_conflation.blocking.multilingual import MultilingualTransliterationEngine
from src.poi_conflation.blocking.lexical import extract_distinctive_tokens
from src.poi_conflation.blocking.category import CategoryCompatibility


class AISuggestionProvider(ABC):
    """Abstract interface for generating AI-assisted annotation suggestions."""

    @property
    @abstractmethod
    def model_identifier(self) -> str:
        """Return unique identifier for the suggestion model."""
        pass

    @abstractmethod
    def generate_suggestion(self, item: AnnotationQueueItem) -> AIPairSuggestion:
        """Generate a structured, explainable suggestion for an unlabelled pair."""
        pass

    def generate_batch(self, items: List[AnnotationQueueItem]) -> List[AIPairSuggestion]:
        """Generate suggestions for a list of queue items."""
        return [self.generate_suggestion(item) for item in items]


class HeuristicAIAnalyzer(AISuggestionProvider):
    """Deterministic, domain-aware heuristic analyzer for Indian urban POI pairs.
    
    Synthesizes available canonical attributes (names, Kannada script, categories,
    coordinates, distance, blocking strategy provenance) without hallucinating missing fields.
    """

    def __init__(self, model_id: str = "heuristic_rule_v1"):
        self._model_id = model_id

    @property
    def model_identifier(self) -> str:
        return self._model_id

    def _compute_lexical_similarity(self, s1: Optional[str], s2: Optional[str]) -> float:
        """Compute token-sort ratio between two normalized names [0.0 - 1.0]."""
        if not s1 or not s2:
            return 0.0
        return fuzz.token_sort_ratio(s1.lower(), s2.lower()) / 100.0

    def _check_token_containment(self, s1: Optional[str], s2: Optional[str]) -> bool:
        """Check if one name is a token containment/subset of the other."""
        if not s1 or not s2:
            return False
        tokens1 = set(re.findall(r"\b\w+\b", s1.lower()))
        tokens2 = set(re.findall(r"\b\w+\b", s2.lower()))
        if not tokens1 or not tokens2:
            return False
        return tokens1.issubset(tokens2) or tokens2.issubset(tokens1)

    def generate_suggestion(self, item: AnnotationQueueItem) -> AIPairSuggestion:
        """Evaluate pair against structured India-specific POI conflation rules."""
        supporting: List[str] = []
        contradictory: List[str] = []
        missing_info: List[str] = []

        # 1. Audit missing attributes (never hallucinate missing details)
        osm_name_raw = (item.osm_name_raw or "").strip()
        ov_name_raw = (item.ov_name_raw or "").strip()
        osm_norm = (item.osm_name_normalized or "").strip().lower()
        ov_norm = (item.ov_name_normalized or "").strip().lower()

        if not osm_name_raw:
            missing_info.append("OSM primary name is empty or missing")
        if not ov_name_raw:
            missing_info.append("Overture primary name is empty or missing")
        
        missing_info.append("Phone numbers and full postal addresses not present in candidate schema")

        # 2. Check for missing or generic names
        if not osm_norm or not ov_norm:
            explanation = (
                f"Cannot establish identity because one or both records lack a valid primary name "
                f"(OSM: '{item.osm_name_raw or ''}', Overture: '{item.ov_name_raw or ''}'). "
                f"Physical distance is {item.distance_meters:.1f}m, but proximity alone cannot confirm entity identity."
            )
            if item.distance_meters <= 25.0:
                supporting.append(f"Close spatial proximity: {item.distance_meters:.1f}m")
            contradictory.append("Missing primary name on record")

            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.UNCERTAIN,
                suggested_confidence=ConfidenceLevel.LOW,
                suggested_evidence_type=EvidenceType.INSUFFICIENT_EVIDENCE,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # 3. Compute lexical similarity and token containment
        lex_sim = self._compute_lexical_similarity(osm_norm, ov_norm)
        is_exact_name = (osm_norm == ov_norm)
        is_containment = self._check_token_containment(osm_norm, ov_norm)
        is_incompatible_cat = (item.category_compatibility == CategoryCompatibility.INCOMPATIBLE.value)
        is_strongly_compat = (item.category_compatibility == CategoryCompatibility.STRONGLY_COMPATIBLE.value)

        # 4. Transliteration & Phonetic Analysis
        kannada_match = False
        kannada_text = item.osm_name_kn.strip() if item.osm_name_kn else None
        if kannada_text:
            lat_kn, _ = MultilingualTransliterationEngine.transliterate_kannada_to_latin(kannada_text)
            if lat_kn:
                kn_sim = self._compute_lexical_similarity(lat_kn, ov_norm)
                if kn_sim >= 0.70 or self._check_token_containment(lat_kn, ov_norm):
                    kannada_match = True
                    supporting.append(f"Kannada script transliteration ('{lat_kn}') matches Overture name ('{ov_norm}')")

        osm_phon, _ = MultilingualTransliterationEngine.apply_phonetic_normalization(osm_norm)
        ov_phon, _ = MultilingualTransliterationEngine.apply_phonetic_normalization(ov_norm)
        phonetic_match = (osm_phon == ov_phon) and (osm_phon != "")
        if phonetic_match and not is_exact_name:
            supporting.append(f"Phonetic normalization match: '{osm_phon}' == '{ov_phon}'")

        # 5. Evaluate Rules in order of specificity

        # --- Rule A: Large Distance (> 100m) ---
        if item.distance_meters > 100.0:
            if is_exact_name or lex_sim >= 0.85:
                supporting.append(f"High name similarity: {lex_sim:.2f}")
                contradictory.append(f"Excessive physical separation: {item.distance_meters:.1f}m > 100m")
                explanation = (
                    f"OSM ('{item.osm_name_raw}') and Overture ('{item.ov_name_raw}') share identical or near-identical "
                    f"names but are separated by {item.distance_meters:.1f}m in an urban area. This strongly indicates "
                    f"distinct chain/franchise branches or separate geographical locations."
                )
                return AIPairSuggestion(
                    pair_id=item.pair_id,
                    suggested_label=LabelDecision.NON_MATCH,
                    suggested_confidence=ConfidenceLevel.HIGH,
                    suggested_evidence_type=EvidenceType.SAME_BRAND_DIFFERENT_BRANCH,
                    explanation=explanation,
                    supporting_evidence=supporting,
                    contradictory_evidence=contradictory,
                    missing_information=missing_info,
                    adjudication_recommended=False,
                    model_identifier=self.model_identifier,
                )
            else:
                contradictory.append(f"Excessive physical separation: {item.distance_meters:.1f}m")
                contradictory.append(f"Low lexical similarity: {lex_sim:.2f}")
                explanation = (
                    f"Entities are separated by {item.distance_meters:.1f}m with low name similarity "
                    f"('{item.osm_name_raw}' vs '{item.ov_name_raw}'). Definitive non-match."
                )
                return AIPairSuggestion(
                    pair_id=item.pair_id,
                    suggested_label=LabelDecision.NON_MATCH,
                    suggested_confidence=ConfidenceLevel.HIGH,
                    suggested_evidence_type=EvidenceType.OTHER,
                    explanation=explanation,
                    supporting_evidence=supporting,
                    contradictory_evidence=contradictory,
                    missing_information=missing_info,
                    adjudication_recommended=False,
                    model_identifier=self.model_identifier,
                )

        # --- Rule B: Incompatible Category Conflict ---
        if is_incompatible_cat:
            contradictory.append(f"Incompatible canonical categories: OSM '{item.osm_category}' vs Overture '{item.ov_category}'")
            if is_exact_name:
                supporting.append("Exact name match")
                explanation = (
                    f"Records share identical normalized name ('{osm_norm}') at {item.distance_meters:.1f}m, "
                    f"but have disjoint incompatible categories ({item.osm_category} vs {item.ov_category}). "
                    f"Requires human adjudication to resolve potential dual-use or tagging error."
                )
                return AIPairSuggestion(
                    pair_id=item.pair_id,
                    suggested_label=LabelDecision.NEEDS_ADJUDICATION,
                    suggested_confidence=ConfidenceLevel.MEDIUM,
                    suggested_evidence_type=EvidenceType.CATEGORY_DISJOINT,
                    explanation=explanation,
                    supporting_evidence=supporting,
                    contradictory_evidence=contradictory,
                    missing_information=missing_info,
                    adjudication_recommended=True,
                    model_identifier=self.model_identifier,
                )
            else:
                explanation = (
                    f"OSM ('{item.osm_name_raw}') and Overture ('{item.ov_name_raw}') feature disjoint incompatible "
                    f"categories ({item.osm_category} vs {item.ov_category}) and differing names at {item.distance_meters:.1f}m."
                )
                return AIPairSuggestion(
                    pair_id=item.pair_id,
                    suggested_label=LabelDecision.NON_MATCH,
                    suggested_confidence=ConfidenceLevel.HIGH,
                    suggested_evidence_type=EvidenceType.CATEGORY_DISJOINT,
                    explanation=explanation,
                    supporting_evidence=supporting,
                    contradictory_evidence=contradictory,
                    missing_information=missing_info,
                    adjudication_recommended=False,
                    model_identifier=self.model_identifier,
                )

        # --- Rule C: Exact Name and Close Distance (<= 25m) ---
        if is_exact_name and item.distance_meters <= 25.0:
            supporting.append(f"Exact normalized name match: '{osm_norm}'")
            supporting.append(f"Close spatial proximity: {item.distance_meters:.1f}m <= 25m")
            if is_strongly_compat:
                supporting.append(f"Identical categories: {item.osm_category}")
            explanation = (
                f"Exact name agreement ('{osm_norm}') within tight spatial threshold "
                f"({item.distance_meters:.1f}m <= 25m) with compatible categories."
            )
            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.MATCH,
                suggested_confidence=ConfidenceLevel.HIGH,
                suggested_evidence_type=EvidenceType.EXACT_NAME_AND_LOCATION,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # --- Rule D: Exact Name with Street-Level Displacement (25m - 100m) ---
        if is_exact_name and 25.0 < item.distance_meters <= 100.0:
            supporting.append(f"Exact normalized name match: '{osm_norm}'")
            contradictory.append(f"Moderate spatial displacement: {item.distance_meters:.1f}m")
            explanation = (
                f"Exact normalized name agreement ('{osm_norm}') at {item.distance_meters:.1f}m distance. "
                f"Consistent with street-level centroid or frontage GPS offset between OSM and Overture."
            )
            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.MATCH,
                suggested_confidence=ConfidenceLevel.MEDIUM,
                suggested_evidence_type=EvidenceType.STREET_LEVEL_DISPLACEMENT,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # --- Rule E: Multilingual Kannada or Phonetic Match (<= 50m) ---
        if (kannada_match or phonetic_match) and item.distance_meters <= 50.0:
            confidence = ConfidenceLevel.HIGH if item.distance_meters <= 25.0 else ConfidenceLevel.MEDIUM
            explanation = (
                f"Indic multilingual/phonetic correspondence verified at {item.distance_meters:.1f}m "
                f"between OSM ('{item.osm_name_raw}' / Kannada: '{item.osm_name_kn or ''}') and "
                f"Overture ('{item.ov_name_raw}')."
            )
            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.MATCH,
                suggested_confidence=confidence,
                suggested_evidence_type=EvidenceType.TRANSLITERATION_OR_PHONETIC_MATCH,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # --- Rule F: Name Expansion or Acronym (<= 50m) ---
        if (is_containment or lex_sim >= 0.70) and item.distance_meters <= 50.0:
            supporting.append(f"Name token containment or high lexical similarity ({lex_sim:.2f})")
            supporting.append(f"Proximity within 50m: {item.distance_meters:.1f}m")
            explanation = (
                f"Strong token containment / abbreviation expansion observed between OSM ('{item.osm_name_raw}') "
                f"and Overture ('{item.ov_name_raw}') at {item.distance_meters:.1f}m."
            )
            confidence = ConfidenceLevel.HIGH if item.distance_meters <= 20.0 and lex_sim >= 0.85 else ConfidenceLevel.MEDIUM
            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.MATCH,
                suggested_confidence=confidence,
                suggested_evidence_type=EvidenceType.NAME_EXPANSION_OR_ACRONYM,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # --- Rule G: Close Spatial Proximity (<= 25m) with Distinct Names ---
        if item.distance_meters <= 25.0 and lex_sim < 0.35:
            supporting.append(f"Close spatial proximity: {item.distance_meters:.1f}m")
            contradictory.append(f"Completely distinct names (similarity: {lex_sim:.2f}): '{osm_norm}' vs '{ov_norm}'")
            explanation = (
                f"OSM ('{item.osm_name_raw}') and Overture ('{item.ov_name_raw}') occupy the same immediate spatial "
                f"footprint ({item.distance_meters:.1f}m <= 25m) but feature entirely distinct names. "
                f"Represents distinct establishments or commercial tenants inside the same building complex."
            )
            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.NON_MATCH,
                suggested_confidence=ConfidenceLevel.HIGH,
                suggested_evidence_type=EvidenceType.SAME_BUILDING_DIFFERENT_BUSINESS,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # --- Rule H: Distinct Names at Moderate Distance (25m - 100m) ---
        if item.distance_meters > 25.0 and lex_sim < 0.50:
            contradictory.append(f"Distinct names (similarity: {lex_sim:.2f}): '{osm_norm}' vs '{ov_norm}'")
            contradictory.append(f"Spatial separation: {item.distance_meters:.1f}m")
            evidence_type = EvidenceType.CATEGORY_DISJOINT if item.osm_category != item.ov_category else EvidenceType.OTHER
            explanation = (
                f"OSM ('{item.osm_name_raw}') and Overture ('{item.ov_name_raw}') have distinct names "
                f"(similarity: {lex_sim:.2f}) and are separated by {item.distance_meters:.1f}m. Non-match."
            )
            return AIPairSuggestion(
                pair_id=item.pair_id,
                suggested_label=LabelDecision.NON_MATCH,
                suggested_confidence=ConfidenceLevel.HIGH if lex_sim < 0.25 else ConfidenceLevel.MEDIUM,
                suggested_evidence_type=evidence_type,
                explanation=explanation,
                supporting_evidence=supporting,
                contradictory_evidence=contradictory,
                missing_information=missing_info,
                adjudication_recommended=False,
                model_identifier=self.model_identifier,
            )

        # --- Default: Ambiguous / Borderline Pair ---
        explanation = (
            f"Borderline lexical similarity ({lex_sim:.2f}) and spatial separation of {item.distance_meters:.1f}m "
            f"between '{item.osm_name_raw}' and '{item.ov_name_raw}'. Recommended for adjudicator inspection."
        )
        return AIPairSuggestion(
            pair_id=item.pair_id,
            suggested_label=LabelDecision.NEEDS_ADJUDICATION,
            suggested_confidence=ConfidenceLevel.LOW,
            suggested_evidence_type=EvidenceType.OTHER,
            explanation=explanation,
            supporting_evidence=supporting,
            contradictory_evidence=contradictory,
            missing_information=missing_info,
            adjudication_recommended=True,
            model_identifier=self.model_identifier,
        )
