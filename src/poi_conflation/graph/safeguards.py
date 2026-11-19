"""Domain-specific safeguards for bipartite POI conflation graph.

Implements rigorous domain guardrails preventing erroneous pairwise merges:
1. ATM_VS_BANK_FACILITY_DISTINCTION: Prevents merging standalone ATM kiosks with bank branches.
2. PARENT_CHILD_CONTAINER: Identifies commercial container relationships (malls, tech parks, hospitals, campuses).
3. SAME_BRAND_DIFFERENT_BRANCH: Distinguishes separate physical branch locations of the same chain.
4. GENERIC_NAME_COLLISION: Prevents merging generic establishment descriptors based on proximity alone.
5. CATEGORY_INCOMPATIBLE: Rejects cross-domain contradictory taxonomies.
6. EXCESSIVE_SPATIAL_SEPARATION: Rejects candidate pairs separated by unacceptable geographic displacement.
7. MISSING_OR_EMPTY_NAME: Prevents merging unverified anonymous POIs.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.poi_conflation.graph.schema import (
    EdgeDisposition,
    POIRelationshipType,
    SafeguardType,
)
from src.poi_conflation.blocking.category import (
    CategoryCompatibilityClassifier,
    CategoryCompatibility,
)

# Regex patterns for ATM vs Bank detection
ATM_PATTERN = re.compile(
    r"\b(atm|cdm|cash\s*point|cash\s*deposit|cash\s*machine|cash\s*recycler|automated\s*teller\s*machine)\b",
    re.IGNORECASE,
)
BANK_PATTERN = re.compile(
    r"\b(bank|branch|banking\s*unit|cooperative\s*bank|grameena\s*bank|regional\s*rural\s*bank)\b",
    re.IGNORECASE,
)

# Parent Container keywords
CONTAINER_KEYWORDS = {
    "mall", "complex", "plaza", "center", "centre", "arcade", "bazaar",
    "campus", "towers", "tower", "enclave", "tech park", "techpark",
    "it park", "business park", "hospital", "university", "college",
    "station", "airport", "apartments", "residency", "heights",
    "marketcity", "forum", "galleria", "building"
}

# Child facility / tenant keywords
CHILD_FACILITY_KEYWORDS = {
    "cafeteria", "canteen", "food court", "bakery", "pharmacy", "medical store",
    "clinic", "store", "shop", "branch", "block a", "block b", "block c",
    "wing a", "wing b", "gate 1", "gate 2", "library", "hostel", "court",
    "ground", "kiosk", "mess", "lab", "laboratory", "diagnostic"
}

# Generic urban establishment descriptors
GENERIC_BUSINESS_NAMES = {
    "hotel", "restaurant", "medical store", "pharmacy", "cafe", "coffee shop",
    "tea stall", "tea point", "bakery", "supermarket", "store", "shop",
    "provision store", "general store", "salon", "beauty parlour", "clinic",
    "hospital", "temple", "church", "mosque", "tailor", "xerox", "bar",
    "gym", "fitness centre", "atm", "school", "college", "office"
}

# Honorific and generic Indian business prefixes
HONORIFIC_PREFIX_PATTERN = re.compile(
    r"^(sri|shree|shri|sree|the|dr\.?|saint|st\.?|hotel|m/s|smt)\b",
    re.IGNORECASE,
)

# Standardized Bengaluru urban locality tokens for branch distinction
LOCALITY_MAPPINGS: Dict[str, str] = {
    "koramangala": "koramangala",
    "indiranagar": "indiranagar",
    "jayanagar": "jayanagar",
    "whitefield": "whitefield",
    "marathahalli": "marathahalli",
    "marathalli": "marathahalli",
    "hsr": "hsr_layout",
    "hsr layout": "hsr_layout",
    "electronic city": "electronic_city",
    "electronics city": "electronic_city",
    "rajajinagar": "rajajinagar",
    "malleshwaram": "malleshwaram",
    "malleswaram": "malleshwaram",
    "hebbal": "hebbal",
    "banashankari": "banashankari",
    "btm": "btm_layout",
    "btm layout": "btm_layout",
    "yelahanka": "yelahanka",
    "basavanagudi": "basavanagudi",
    "bellandur": "bellandur",
    "domlur": "domlur",
    "ulsoor": "ulsoor",
    "halasuru": "ulsoor",
    "frazer town": "frazer_town",
    "sadashivanagar": "sadashivanagar",
    "vijayanagar": "vijayanagar",
    "nagarbhavi": "nagarbhavi",
    "kengeri": "kengeri",
    "jp nagar": "jp_nagar",
    "mg road": "mg_road",
    "brigade road": "brigade_road",
    "commercial street": "commercial_street",
    "residency road": "residency_road",
    "richmond road": "richmond_road",
    "bannerghatta": "bannerghatta",
    "sarjapur": "sarjapur",
}


@dataclass
class SafeguardResult:
    """Outcome of domain-specific safeguard validation for a candidate edge."""
    safeguards_triggered: List[SafeguardType] = field(default_factory=list)
    disposition: EdgeDisposition = EdgeDisposition.ACCEPTED_EQUIVALENCE
    disposition_reason: str = "Accepted equivalence"
    relationship_type: Optional[POIRelationshipType] = None
    parent_source: Optional[str] = None   # 'OSM' or 'OVERTURE'
    evidence_notes: List[str] = field(default_factory=list)


class ConflationSafeguardValidator:
    """Validates candidate pairs against domain-specific POI conflation rules."""

    def __init__(
        self,
        max_equivalence_distance: float = 50.0,
        max_absolute_distance: float = 80.0,
        uncertain_threshold: float = 0.30,
        match_threshold: float = 0.55,
        enable_honorific_safeguard: bool = True,
    ):
        self.max_equivalence_distance = max_equivalence_distance
        self.max_absolute_distance = max_absolute_distance
        self.uncertain_threshold = uncertain_threshold
        self.match_threshold = match_threshold
        self.enable_honorific_safeguard = enable_honorific_safeguard
        self.cat_classifier = CategoryCompatibilityClassifier()

    def validate_candidate_edge(
        self,
        osm_name: str,
        ov_name: str,
        osm_category: str,
        ov_category: str,
        distance_meters: float,
        supervised_model_score: float,
        supervised_decision: str,
        features: Optional[Dict[str, float]] = None,
    ) -> SafeguardResult:
        """Validate candidate edge against all domain safeguards."""
        features = features or {}
        norm_osm = (osm_name or "").strip().lower()
        norm_ov = (ov_name or "").strip().lower()
        osm_cat = (osm_category or "").strip().lower()
        ov_cat = (ov_category or "").strip().lower()

        result = SafeguardResult()

        # 1. Check Missing / Empty Name
        is_empty = features.get("feat_is_empty_name", 0.0) == 1.0 or not norm_osm or not norm_ov
        if is_empty:
            result.safeguards_triggered.append(SafeguardType.MISSING_OR_EMPTY_NAME)
            result.disposition = EdgeDisposition.REJECTED
            result.disposition_reason = "Prohibited merge: missing or empty name attribute prevents identity verification"
            result.evidence_notes.append("Empty name on OSM or Overture record")
            return result

        # 2. Check Supervised Non-Match Decision
        if supervised_decision == "NON_MATCH" or supervised_model_score < self.uncertain_threshold:
            result.disposition = EdgeDisposition.REJECTED
            result.disposition_reason = f"Rejected: supervised model score {supervised_model_score:.4f} below uncertain threshold ({self.uncertain_threshold})"
            return result

        # 3. Check Category Incompatibility
        cat_compat, cat_reason = self.cat_classifier.evaluate(osm_cat, ov_cat)
        is_incompat = (cat_compat == CategoryCompatibility.INCOMPATIBLE) or (features.get("feat_category_incompatible", 0.0) == 1.0)
        if is_incompat:
            result.safeguards_triggered.append(SafeguardType.CATEGORY_INCOMPATIBLE)
            result.disposition = EdgeDisposition.REJECTED
            result.disposition_reason = f"Prohibited merge: strictly incompatible POI categories ('{osm_cat}' vs '{ov_cat}')"
            result.evidence_notes.append(f"Incompatible taxonomy pairing: {osm_cat} vs {ov_cat}")
            return result

        # 4. Check ATM vs Bank Branch Distinction
        osm_is_atm = bool(ATM_PATTERN.search(norm_osm)) or (osm_cat == "atm")
        ov_is_atm = bool(ATM_PATTERN.search(norm_ov)) or (ov_cat == "atm")

        if osm_is_atm != ov_is_atm:
            # One is an ATM and the other is a bank branch / non-ATM entity
            result.safeguards_triggered.append(SafeguardType.ATM_VS_BANK_FACILITY_DISTINCTION)
            if distance_meters <= 100.0 and self._check_brand_sharing(norm_osm, norm_ov):
                result.disposition = EdgeDisposition.PARENT_CHILD
                result.relationship_type = POIRelationshipType.FACILITY_ATM
                result.parent_source = "OVERTURE" if osm_is_atm else "OSM"
                result.disposition_reason = "ATM facility distinction: separate ATM kiosk associated with parent bank branch"
                result.evidence_notes.append(f"Bank branch / ATM pair sharing brand within {distance_meters:.1f}m")
            else:
                result.disposition = EdgeDisposition.REJECTED
                result.disposition_reason = "Prohibited merge: ATM kiosk vs bank facility distinction"
                result.evidence_notes.append("ATM vs non-ATM mismatch without shared brand proximity")
            return result

        # 5. Check Parent-Child Commercial Containers
        is_parent_child, p_source, p_type, p_reason = self._detect_parent_child(
            norm_osm, norm_ov, osm_cat, ov_cat, distance_meters
        )
        if is_parent_child:
            result.safeguards_triggered.append(SafeguardType.PARENT_CHILD_CONTAINER)
            result.disposition = EdgeDisposition.PARENT_CHILD
            result.relationship_type = p_type
            result.parent_source = p_source
            result.disposition_reason = f"Prohibited merge: {p_reason}"
            result.evidence_notes.append(p_reason)
            return result

        # 6. Check Same-Brand Different Branches (Conflicting Localities)
        is_diff_branch, branch_reason = self._detect_different_branches(
            norm_osm, norm_ov, distance_meters
        )
        if is_diff_branch:
            result.safeguards_triggered.append(SafeguardType.SAME_BRAND_DIFFERENT_BRANCH)
            result.disposition = EdgeDisposition.REJECTED
            result.disposition_reason = f"Prohibited merge: {branch_reason}"
            result.evidence_notes.append(branch_reason)
            return result

        # 7. Check Generic Name Collision
        is_generic, gen_reason = self._detect_generic_collision(
            norm_osm, norm_ov, distance_meters, features
        )
        if is_generic:
            result.safeguards_triggered.append(SafeguardType.GENERIC_NAME_COLLISION)
            result.disposition = EdgeDisposition.REVIEW
            result.disposition_reason = f"Prohibited merge: {gen_reason}"
            result.evidence_notes.append(gen_reason)
            return result

        # 8. Check Shared Honorific Prefix with Disjoint Brand
        if self.enable_honorific_safeguard:
            is_honorific_disjoint, honorific_reason = self._detect_shared_honorific_disjoint_brand(
                norm_osm, norm_ov
            )
            if is_honorific_disjoint:
                result.safeguards_triggered.append(SafeguardType.SHARED_HONORIFIC_DISJOINT_BRAND)
                result.disposition = EdgeDisposition.REVIEW
                result.disposition_reason = f"Prohibited merge: {honorific_reason}"
                result.evidence_notes.append(honorific_reason)
                return result

        # 9. Check Excessive Spatial Separation
        exact_match = (norm_osm == norm_ov) or (features.get("feat_exact_name_match", 0.0) == 1.0)
        if distance_meters > self.max_absolute_distance:
            result.safeguards_triggered.append(SafeguardType.EXCESSIVE_SPATIAL_SEPARATION)
            result.disposition = EdgeDisposition.REJECTED
            result.disposition_reason = f"Prohibited merge: spatial displacement {distance_meters:.1f}m exceeds absolute threshold ({self.max_absolute_distance}m)"
            result.evidence_notes.append(f"Excessive distance: {distance_meters:.1f}m")
            return result

        if distance_meters > self.max_equivalence_distance and not exact_match:
            result.safeguards_triggered.append(SafeguardType.EXCESSIVE_SPATIAL_SEPARATION)
            result.disposition = EdgeDisposition.REJECTED
            result.disposition_reason = f"Prohibited merge: spatial displacement {distance_meters:.1f}m exceeds non-exact threshold ({self.max_equivalence_distance}m)"
            result.evidence_notes.append(f"Distance {distance_meters:.1f}m without exact name match")
            return result

        # 9. Supervised Uncertain Decision
        if supervised_decision == "UNCERTAIN" or supervised_model_score < self.match_threshold:
            result.disposition = EdgeDisposition.REVIEW
            result.disposition_reason = f"Review required: score {supervised_model_score:.4f} in uncertain decision band [{self.uncertain_threshold}, {self.match_threshold})"
            result.evidence_notes.append("Uncertain model decision band")
            return result

        # 10. All checks passed: Accepted Equivalence
        result.disposition = EdgeDisposition.ACCEPTED_EQUIVALENCE
        result.disposition_reason = f"Accepted equivalence: score {supervised_model_score:.4f} >= {self.match_threshold} without safeguard violations"
        result.evidence_notes.append(f"High-confidence match: distance={distance_meters:.1f}m, score={supervised_model_score:.4f}")
        return result

    def _check_brand_sharing(self, name_a: str, name_b: str) -> bool:
        """Check if two names share a major bank or commercial brand root."""
        clean_a = ATM_PATTERN.sub("", name_a).strip()
        clean_b = ATM_PATTERN.sub("", name_b).strip()
        tokens_a = set(re.findall(r"\w+", clean_a))
        tokens_b = set(re.findall(r"\w+", clean_b))
        common = tokens_a.intersection(tokens_b)
        # Check if significant brand token is shared
        meaningful_common = {t for t in common if len(t) >= 3 and t not in {"the", "and", "for", "bank", "ltd", "limited"}}
        return len(meaningful_common) >= 1 or clean_a in clean_b or clean_b in clean_a

    def _detect_parent_child(
        self,
        name_osm: str,
        name_ov: str,
        cat_osm: str,
        cat_ov: str,
        dist_m: float,
    ) -> Tuple[bool, Optional[str], Optional[POIRelationshipType], Optional[str]]:
        """Identify container parent-child relations."""
        if dist_m > 75.0:
            return False, None, None, None

        osm_has_container = any(k in name_osm for k in CONTAINER_KEYWORDS)
        ov_has_container = any(k in name_ov for k in CONTAINER_KEYWORDS)

        # Case A: OSM is container, Overture is internal tenant/facility
        if osm_has_container and not ov_has_container:
            if name_osm != name_ov and not self._is_exact_equivalent(name_osm, name_ov):
                rel_type = POIRelationshipType.CAMPUS_FACILITY if any(k in name_osm for k in {"campus", "university", "college", "tech park", "hospital"}) else POIRelationshipType.PARENT_CHILD
                return True, "OSM", rel_type, f"Child establishment '{name_ov}' located within OSM container '{name_osm}'"

        # Case B: Overture is container, OSM is internal tenant/facility
        if ov_has_container and not osm_has_container:
            if name_osm != name_ov and not self._is_exact_equivalent(name_osm, name_ov):
                rel_type = POIRelationshipType.CAMPUS_FACILITY if any(k in name_ov for k in {"campus", "university", "college", "tech park", "hospital"}) else POIRelationshipType.PARENT_CHILD
                return True, "OVERTURE", rel_type, f"Child establishment '{name_osm}' located within Overture container '{name_ov}'"

        return False, None, None, None

    def _detect_different_branches(
        self,
        name_osm: str,
        name_ov: str,
        dist_m: float,
    ) -> Tuple[bool, Optional[str]]:
        """Identify distinct physical branches of same chain."""
        # Find locality markers in each name
        osm_locs = {LOCALITY_MAPPINGS[k] for k in LOCALITY_MAPPINGS if k in name_osm}
        ov_locs = {LOCALITY_MAPPINGS[k] for k in LOCALITY_MAPPINGS if k in name_ov}

        if osm_locs and ov_locs and osm_locs != ov_locs:
            # Conflicting explicit localities
            return True, f"Distinct branch locations with conflicting localities: {', '.join(osm_locs)} vs {', '.join(ov_locs)}"

        # Phase / Block qualifier conflicts (e.g. 4th block vs 9th block)
        block_re = re.compile(r"\b(\d+)(?:st|nd|rd|th)?\s*(block|phase|stage|cross|sector)\b", re.IGNORECASE)
        osm_blocks = block_re.findall(name_osm)
        ov_blocks = block_re.findall(name_ov)
        if osm_blocks and ov_blocks and osm_blocks != ov_blocks:
            return True, f"Distinct branch units with conflicting block/phase qualifiers ({osm_blocks} vs {ov_blocks})"

        return False, None

    def _detect_generic_collision(
        self,
        name_osm: str,
        name_ov: str,
        dist_m: float,
        features: Dict[str, float],
    ) -> Tuple[bool, Optional[str]]:
        """Detect generic descriptor collisions without distinctive names."""
        clean_osm = re.sub(r"[^\w\s]", "", name_osm).strip()
        clean_ov = re.sub(r"[^\w\s]", "", name_ov).strip()

        # Exact match is not a collision
        if clean_osm == clean_ov and dist_m <= 15.0:
            return False, None

        # Check if name consists solely of generic business terms
        is_osm_pure_generic = clean_osm in GENERIC_BUSINESS_NAMES
        is_ov_pure_generic = clean_ov in GENERIC_BUSINESS_NAMES

        if is_osm_pure_generic and is_ov_pure_generic:
            return True, f"Both records have purely generic names ('{name_osm}' vs '{name_ov}')"

        if (is_osm_pure_generic or is_ov_pure_generic) and dist_m > 15.0:
            return True, f"Generic name descriptor ('{name_osm}' vs '{name_ov}') at distance {dist_m:.1f}m > 15m"

        # Check if root distinctive token is completely different despite shared generic prefix
        # e.g., 'hotel sagar' vs 'hotel green orchid'
        tokens_osm = [t for t in clean_osm.split() if t not in GENERIC_BUSINESS_NAMES and len(t) >= 3]
        tokens_ov = [t for t in clean_ov.split() if t not in GENERIC_BUSINESS_NAMES and len(t) >= 3]

        if tokens_osm and tokens_ov and not set(tokens_osm).intersection(set(tokens_ov)):
            # Both have generic words (e.g. hotel), but distinctive names share zero words!
            if any(g in clean_osm for g in GENERIC_BUSINESS_NAMES) and any(g in clean_ov for g in GENERIC_BUSINESS_NAMES):
                return True, f"Distinct establishments sharing generic descriptor prefix but disjoint brands: '{clean_osm}' vs '{clean_ov}'"

        return False, None

    def _is_exact_equivalent(self, a: str, b: str) -> bool:
        """Check if names are string equivalents modulo punctuation/whitespace."""
        ca = re.sub(r"[^\w]", "", a.lower())
        cb = re.sub(r"[^\w]", "", b.lower())
        return ca == cb

    def _detect_shared_honorific_disjoint_brand(
        self,
        name_osm: str,
        name_ov: str,
    ) -> Tuple[bool, Optional[str]]:
        """Detect pairs with shared honorific/generic prefix but disjoint brand cores."""
        clean_osm = name_osm.strip().lower()
        clean_ov = name_ov.strip().lower()

        # If identical, not a disjoint brand
        if self._is_exact_equivalent(clean_osm, clean_ov):
            return False, None

        m_osm = HONORIFIC_PREFIX_PATTERN.match(clean_osm)
        m_ov = HONORIFIC_PREFIX_PATTERN.match(clean_ov)

        if m_osm and m_ov:
            p_osm = m_osm.group(0).rstrip(".")
            p_ov = m_ov.group(0).rstrip(".")
            # Normalize religious honorific variants
            norm_a = "sri" if p_osm in {"sri", "shri", "shree", "sree"} else p_osm
            norm_b = "sri" if p_ov in {"sri", "shri", "shree", "sree"} else p_ov

            if norm_a == norm_b:
                core_osm = clean_osm[len(m_osm.group(0)):].strip()
                core_ov = clean_ov[len(m_ov.group(0)):].strip()

                if len(core_osm) >= 3 and len(core_ov) >= 3:
                    # Normalize punctuation to detect shared brand words
                    c_osm = re.sub(r"[^\w\s]", " ", core_osm).strip()
                    c_ov = re.sub(r"[^\w\s]", " ", core_ov).strip()
                    tokens_osm = {t for t in c_osm.split() if len(t) >= 3}
                    tokens_ov = {t for t in c_ov.split() if len(t) >= 3}
                    common = tokens_osm & tokens_ov

                    # If significant brand token is shared, or one is substring of other, not disjoint
                    if common or c_osm in c_ov or c_ov in c_osm:
                        return False, None

                    from rapidfuzz import fuzz
                    r1 = fuzz.ratio(core_osm, core_ov)
                    r2 = fuzz.token_set_ratio(core_osm, core_ov)

                    if (len(common) == 0 and r2 < 65.0) or (r1 < 50.0 and r2 < 60.0):
                        return True, f"Distinct establishments sharing honorific prefix '{m_osm.group(0)}' but disjoint brand cores ('{core_osm}' vs '{core_ov}')"

        return False, None
