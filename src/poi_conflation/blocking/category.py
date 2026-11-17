"""Category compatibility blocking rules for canonical POI taxonomies.

Defines an explicit compatibility matrix across the 10 canonical categories:
- STRONGLY_COMPATIBLE: Identical categories.
- POTENTIALLY_COMPATIBLE: Plausible cross-domain overlaps (e.g. sustenance & hospitality, healthcare & retail).
- COMPATIBLE_UNKNOWN: Unclassified or generic category ('other') paired with any category.
- INCOMPATIBLE: Disjoint, non-overlapping domains (e.g. healthcare & sustenance, education & financial).
"""

from enum import Enum
from typing import Tuple, Dict, Any


class CategoryCompatibility(str, Enum):
    STRONGLY_COMPATIBLE = "STRONGLY_COMPATIBLE"
    POTENTIALLY_COMPATIBLE = "POTENTIALLY_COMPATIBLE"
    COMPATIBLE_UNKNOWN = "COMPATIBLE_UNKNOWN"
    INCOMPATIBLE = "INCOMPATIBLE"


# Plausible cross-domain compatibility pairings (symmetric)
POTENTIALLY_COMPATIBLE_PAIRS = {
    # Hotels frequently have restaurants/bars/cafes inside
    frozenset({"sustenance", "hospitality"}): "Hotel with on-premise restaurant, cafe, or bar",
    
    # Pharmacies/chemists sell retail goods; supermarkets sell food/sustenance
    frozenset({"retail", "sustenance"}): "Bakery, sweet shop, or grocer with food counter",
    frozenset({"retail", "healthcare"}): "Pharmacy or medical store selling retail goods",
    
    # Financial services in commercial complexes
    frozenset({"commercial_services", "financial"}): "Financial advisory, accounting firm, or fintech office",
    
    # Resorts, heritage lodges
    frozenset({"hospitality", "leisure_tourism"}): "Resort, heritage lodge, or theme park accommodation",
    
    # Temples and historical monuments frequently dual-tagged
    frozenset({"civic_religious", "leisure_tourism"}): "Historical monument, heritage place of worship, or tourist shrine",
    
    # Institutional schools/colleges with religious or civic trusts
    frozenset({"education", "civic_religious"}): "Religious school, seminary, or public institution",
    frozenset({"education", "commercial_services"}): "Commercial coaching center, training institute, or corporate academy",
    frozenset({"commercial_services", "retail"}): "Showroom with corporate service center or repair office",
}

# Explicitly incompatible disjoint domains
DISJOINT_INCOMPATIBLE_PAIRS = {
    frozenset({"healthcare", "sustenance"}): "Hospital/clinic versus restaurant/cafe",
    frozenset({"healthcare", "financial"}): "Hospital/clinic versus bank/ATM",
    frozenset({"healthcare", "hospitality"}): "Hospital/clinic versus hotel/lodging",
    frozenset({"healthcare", "civic_religious"}): "Hospital/clinic versus place of worship",
    frozenset({"financial", "education"}): "Bank/ATM versus academic school/college",
    frozenset({"financial", "hospitality"}): "Bank/ATM versus hotel/lodging",
    frozenset({"financial", "civic_religious"}): "Bank/ATM versus place of worship",
    frozenset({"financial", "leisure_tourism"}): "Bank/ATM versus park/museum",
    frozenset({"education", "sustenance"}): "School/college versus restaurant/bar",
    frozenset({"education", "hospitality"}): "School/college versus hotel/lodging",
    frozenset({"civic_religious", "sustenance"}): "Place of worship versus restaurant/bar",
}


class CategoryCompatibilityClassifier:
    """Evaluates category compatibility between candidate POI pairs."""

    @staticmethod
    def evaluate(cat_a: str, cat_b: str) -> Tuple[CategoryCompatibility, str]:
        """Classify compatibility level between two canonical category strings.
        
        Returns (compatibility_level, reason).
        """
        ca = (cat_a or "other").strip().lower()
        cb = (cat_b or "other").strip().lower()

        # 1. Identical category match
        if ca == cb:
            if ca == "other":
                return (
                    CategoryCompatibility.COMPATIBLE_UNKNOWN,
                    "Both entities classified as unmapped/other category"
                )
            return (
                CategoryCompatibility.STRONGLY_COMPATIBLE,
                f"Exact canonical category agreement: {ca}"
            )

        # 2. Generic / Fallback category handling
        if ca == "other" or cb == "other":
            specific = cb if ca == "other" else ca
            return (
                CategoryCompatibility.COMPATIBLE_UNKNOWN,
                f"Retained for recall: one entity is '{specific}' and the other is unclassified 'other'"
            )

        pair_key = frozenset({ca, cb})

        # 3. Explicit potential compatibility
        if pair_key in POTENTIALLY_COMPATIBLE_PAIRS:
            return (
                CategoryCompatibility.POTENTIALLY_COMPATIBLE,
                POTENTIALLY_COMPATIBLE_PAIRS[pair_key]
            )

        # 4. Explicit incompatibility
        if pair_key in DISJOINT_INCOMPATIBLE_PAIRS:
            return (
                CategoryCompatibility.INCOMPATIBLE,
                DISJOINT_INCOMPATIBLE_PAIRS[pair_key]
            )

        # 5. Default conservative fallback for unlisted cross-category pairs
        # We classify as potentially compatible to avoid dropping genuine edge cases
        return (
            CategoryCompatibility.POTENTIALLY_COMPATIBLE,
            f"Cross-category pairing ({ca} ↔ {cb}) not strictly disjoint; retained for recall"
        )

    @classmethod
    def is_candidate_allowed(cls, cat_a: str, cat_b: str, allow_incompatible: bool = False) -> bool:
        """Predicate checking whether candidate pair passes category blocking filter."""
        comp, _ = cls.evaluate(cat_a, cat_b)
        if allow_incompatible:
            return True
        return comp != CategoryCompatibility.INCOMPATIBLE
