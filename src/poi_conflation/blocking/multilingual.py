"""Multilingual and phonetic blocking module for Indic / Kannada POI names.

Provides:
- Native Kannada script (U+0C80–U+0CFF) to Latin transliteration via ISO 15919 / IAST.
- Diacritic removal and ASCII normalization.
- Common Indian English phonetic equivalence mapping (e.g. Sri / Shree, Udupi / Udapi).
- Strict provenance tracking for all generated transliterations.
"""

import re
import unicodedata
from typing import Optional, Tuple, Dict, Any, List

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


KANNADA_REGEX = re.compile(r"[\u0C80-\u0CFF]")

# Common commercial phonetic equivalence mapping in Indian POI names
PHONETIC_EQUIVALENCE_MAP = {
    # Auspicious honorific variants
    r"\bshree\b": "sri",
    r"\bshri\b": "sri",
    r"\bsree\b": "sri",
    r"\bshree\s+": "sri ",
    
    # Establishment suffixes / nouns
    r"\bbhavana\b": "bhavan",
    r"\bsagara\b": "sagar",
    r"\bnivasa\b": "nivas",
    r"\blayouta\b": "layout",
    r"\bcentera\b": "center",
    r"\bcentre\b": "center",
    
    # Regional place / city phonetic variants
    r"\budapi\b": "udupi",
    r"\bbangalore\b": "bengaluru",
    r"\bbengaluru\b": "bengaluru",
    
    # Common deity / personal name variants
    r"\blaxmi\b": "lakshmi",
    r"\blakshmy\b": "lakshmi",
    r"\bvigneswara\b": "vighneshwara",
    r"\bganesh\b": "ganesha",
}


def strip_accents_and_diacritics(text: str) -> str:
    """Normalize Unicode and strip combining diacritical marks from Latin transliterations."""
    if not text:
        return ""
    # Decompose accented characters into base + combining mark
    nfkd = unicodedata.normalize("NFKD", text)
    # Remove combining marks (e.g. macrons, dots, accents)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped


class MultilingualTransliterationEngine:
    """Handles Indic Kannada transliteration and Indian English phonetic normalization."""

    @staticmethod
    def contains_kannada_script(text: Optional[str]) -> bool:
        """Check if string contains native Kannada characters."""
        if not text:
            return False
        return bool(KANNADA_REGEX.search(text))

    @classmethod
    def transliterate_kannada_to_latin(cls, text: Optional[str]) -> Tuple[Optional[str], str]:
        """Transliterate native Kannada script into normalized Latin ASCII representation.
        
        Returns:
            (transliterated_string, method_provenance)
            If input contains no Kannada characters, returns (None, 'no_kannada_detected').
        """
        if not text or not cls.contains_kannada_script(text):
            return (None, "no_kannada_detected")

        try:
            # 1. Transliterate Kannada to IAST (International Alphabet of Sanskrit Transliteration)
            iast_raw = transliterate(text, sanscript.KANNADA, sanscript.IAST)
            
            # 2. Convert IAST diacritics into plain Latin (e.g., ś -> s, ī -> i, ṭ -> t)
            # Custom replacements for Kannada specific characters
            clean_iast = iast_raw.replace("ś", "sh").replace("ṣ", "sh").replace("ṛ", "ri")
            ascii_text = strip_accents_and_diacritics(clean_iast).lower()
            
            # 3. Clean punctuation and collapse whitespace
            tokens = [re.sub(r"[^\w]", "", t) for t in ascii_text.split()]
            normalized_latin = " ".join(t for t in tokens if t)

            return (normalized_latin, "indic_transliteration_iast_ascii")
        except Exception as e:
            return (None, f"transliteration_error: {str(e)}")

    @staticmethod
    def apply_phonetic_normalization(text: Optional[str]) -> Tuple[str, str]:
        """Apply deterministic phonetic equivalence classes for common Indian POI terms.
        
        Returns:
            (normalized_string, method_provenance)
        """
        if not text:
            return ("", "empty_input")

        normalized = text.lower()
        applied = False
        for pattern, replacement in PHONETIC_EQUIVALENCE_MAP.items():
            new_text, count = re.subn(pattern, replacement, normalized)
            if count > 0:
                normalized = new_text
                applied = True

        provenance = "phonetic_equivalence_map" if applied else "unmodified"
        return (normalized, provenance)
