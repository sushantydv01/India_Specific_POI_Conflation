"""Name similarity and lexical feature extraction.

Computes string similarity metrics, token overlap ratios, n-gram Jaccard similarity,
length ratios, generic name flags, and empty name indicators.
"""

import re
from typing import Dict, Any, List, Set, Tuple, Optional
from rapidfuzz import distance, fuzz

# Generic commercial, urban, and POI terms in Indian English
GENERIC_POI_TERMS: Set[str] = {
    "shop", "store", "hotel", "restaurant", "bakery", "cafe",
    "atm", "bank", "hospital", "clinic", "pharmacy", "medical",
    "school", "college", "temple", "church", "mosque", "office",
    "supermarket", "center", "centre", "complex", "mall",
    "enterprise", "enterprises", "agency", "services", "commercial",
    "building", "point", "corner", "stall", "bazaar", "mart",
    "dhaba", "canteen", "darshini", "bhavan", "sagar"
}


def compute_char_3gram_jaccard(s1: str, s2: str) -> float:
    """Compute character 3-gram Jaccard similarity between two strings."""
    if not s1 or not s2:
        return 0.0
    c1 = re.sub(r"\s+", "", s1)
    c2 = re.sub(r"\s+", "", s2)
    if not c1 or not c2:
        return 0.0
    if len(c1) < 3 or len(c2) < 3:
        return 1.0 if c1 == c2 else 0.0
    g1 = {c1[i:i+3] for i in range(len(c1) - 2)}
    g2 = {c2[i:i+3] for i in range(len(c2) - 2)}
    intersection = len(g1 & g2)
    union = len(g1 | g2)
    return float(intersection) / float(union) if union > 0 else 0.0


def is_generic_name(name: Optional[str]) -> bool:
    """Check if name consists entirely of generic business/POI terms."""
    if not name:
        return False
    tokens = [t for t in re.findall(r"\b\w+\b", name.lower()) if t]
    if not tokens:
        return False
    return all(t in GENERIC_POI_TERMS for t in tokens)


def is_empty_name(name: Optional[str]) -> bool:
    """Check if name is missing, empty, or whitespace-only."""
    if name is None:
        return True
    return len(name.strip()) == 0


def extract_name_features(osm_norm_name: Optional[str], ov_norm_name: Optional[str]) -> Dict[str, float]:
    """Extract all 10 name similarity features for a pair of normalized names."""
    s1 = (osm_norm_name or "").strip()
    s2 = (ov_norm_name or "").strip()

    empty_1 = is_empty_name(s1)
    empty_2 = is_empty_name(s2)
    empty_flag = 1.0 if (empty_1 or empty_2) else 0.0

    if empty_flag == 1.0:
        return {
            "feat_exact_name_match": 0.0,
            "feat_jaro_winkler": 0.0,
            "feat_levenshtein_sim": 0.0,
            "feat_token_sort_ratio": 0.0,
            "feat_token_set_ratio": 0.0,
            "feat_char_3gram_jaccard": 0.0,
            "feat_name_length_ratio": 0.0,
            "feat_token_count_diff": 0.0,
            "feat_is_generic_name": 0.0,
            "feat_is_empty_name": 1.0,
        }

    exact_match = 1.0 if s1 == s2 else 0.0
    jw = float(distance.JaroWinkler.similarity(s1, s2))
    lev = float(distance.Levenshtein.normalized_similarity(s1, s2))
    tsort = float(fuzz.token_sort_ratio(s1, s2) / 100.0)
    tset = float(fuzz.token_set_ratio(s1, s2) / 100.0)
    c3gram = compute_char_3gram_jaccard(s1, s2)

    l1, l2 = len(s1), len(s2)
    len_ratio = float(min(l1, l2)) / float(max(l1, l2)) if max(l1, l2) > 0 else 0.0

    t1 = re.findall(r"\b\w+\b", s1)
    t2 = re.findall(r"\b\w+\b", s2)
    tok_diff = float(abs(len(t1) - len(t2)))

    generic_flag = 1.0 if (is_generic_name(s1) or is_generic_name(s2)) else 0.0

    return {
        "feat_exact_name_match": exact_match,
        "feat_jaro_winkler": jw,
        "feat_levenshtein_sim": lev,
        "feat_token_sort_ratio": tsort,
        "feat_token_set_ratio": tset,
        "feat_char_3gram_jaccard": c3gram,
        "feat_name_length_ratio": len_ratio,
        "feat_token_count_diff": tok_diff,
        "feat_is_generic_name": generic_flag,
        "feat_is_empty_name": 0.0,
    }
