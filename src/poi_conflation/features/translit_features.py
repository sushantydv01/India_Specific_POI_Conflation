"""Indic language, Kannada transliteration, and phonetic feature extraction.

Detects Kannada and Latin scripts, transliterates Kannada names via ISO 15919,
and computes transliterated similarity and Indian English phonetic similarity.
"""

import re
from typing import Dict, Any, Optional
from rapidfuzz import fuzz, distance

from src.poi_conflation.blocking.multilingual import (
    MultilingualTransliterationEngine,
    KANNADA_REGEX,
)

LATIN_REGEX = re.compile(r"[a-zA-Z]")


def has_kannada(text: Optional[str]) -> bool:
    """Check if string contains Kannada script."""
    if not text:
        return False
    return bool(KANNADA_REGEX.search(text))


def has_latin(text: Optional[str]) -> bool:
    """Check if string contains Latin alphabet characters."""
    if not text:
        return False
    return bool(LATIN_REGEX.search(text))


def extract_translit_features(
    osm_raw_name: Optional[str],
    ov_raw_name: Optional[str],
    osm_kn_name: Optional[str] = None,
    ov_kn_name: Optional[str] = None,
    osm_norm_name: Optional[str] = None,
    ov_norm_name: Optional[str] = None,
) -> Dict[str, float]:
    """Extract all 8 Indic transliteration and phonetic features."""
    # Check script presence in raw names or dedicated kn field
    osm_has_kn = 1.0 if (has_kannada(osm_raw_name) or has_kannada(osm_kn_name)) else 0.0
    ov_has_kn = 1.0 if (has_kannada(ov_raw_name) or has_kannada(ov_kn_name)) else 0.0
    osm_has_lat = 1.0 if has_latin(osm_raw_name) else 0.0
    ov_has_lat = 1.0 if has_latin(ov_raw_name) else 0.0

    # Determine transliteration availability and transliterated strings
    osm_translit = None
    ov_translit = None

    if osm_has_kn == 1.0:
        kn_src = osm_kn_name if has_kannada(osm_kn_name) else osm_raw_name
        osm_translit, _ = MultilingualTransliterationEngine.transliterate_kannada_to_latin(kn_src)

    if ov_has_kn == 1.0:
        kn_src = ov_kn_name if has_kannada(ov_kn_name) else ov_raw_name
        ov_translit, _ = MultilingualTransliterationEngine.transliterate_kannada_to_latin(kn_src)

    translit_avail = 1.0 if (osm_translit is not None or ov_translit is not None) else 0.0
    translit_sim = 0.0
    translit_exact = 0.0

    s1_norm = (osm_norm_name or "").strip()
    s2_norm = (ov_norm_name or "").strip()

    if translit_avail == 1.0:
        candidates_osm = [s for s in [s1_norm, osm_translit] if s]
        candidates_ov = [s for s in [s2_norm, ov_translit] if s]
        best_sim = 0.0
        exact_found = False

        for c_osm in candidates_osm:
            for c_ov in candidates_ov:
                if c_osm == c_ov and len(c_osm) > 0:
                    exact_found = True
                    best_sim = 1.0
                    break
                sim = float(distance.JaroWinkler.similarity(c_osm, c_ov))
                if sim > best_sim:
                    best_sim = sim
            if exact_found:
                break

        translit_sim = best_sim
        translit_exact = 1.0 if exact_found else 0.0

    # Phonetic normalization similarity
    phonetic_osm, _ = MultilingualTransliterationEngine.apply_phonetic_normalization(s1_norm)
    phonetic_ov, _ = MultilingualTransliterationEngine.apply_phonetic_normalization(s2_norm)

    if not phonetic_osm or not phonetic_ov:
        phonetic_sim = 0.0
    elif phonetic_osm == phonetic_ov:
        phonetic_sim = 1.0
    else:
        # Use token sort ratio for phonetic similarity
        phonetic_sim = float(fuzz.token_sort_ratio(phonetic_osm, phonetic_ov) / 100.0)

    return {
        "feat_osm_has_kannada": osm_has_kn,
        "feat_ov_has_kannada": ov_has_kn,
        "feat_osm_has_latin": osm_has_lat,
        "feat_ov_has_latin": ov_has_lat,
        "feat_translit_available": translit_avail,
        "feat_translit_sim": translit_sim,
        "feat_translit_exact_match": translit_exact,
        "feat_indic_phonetic_sim": phonetic_sim,
    }
