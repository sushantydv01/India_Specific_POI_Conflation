"""Domain-specific entity name normalization and qualifier extraction for POI conflation.

Implements modular handling of:
1. Corporate legal entity suffixes (Limited, Ltd, Pvt Ltd, LLP, PLC, Inc, etc.).
2. Locality and branch qualifiers in urban India (e.g. Bangalore-Marathalli, Rajarajeshwarinagar).
3. Temporal and event qualifiers (e.g. Annual show 2017, Exhibition 2022).
4. Banking domain generics (Small Finance Bank, Co-operative Bank, Retail Banking Branch).
5. ATM versus Bank facility indicators.
"""

import re
from typing import Dict, Any, Tuple, Optional, Set

# Corporate suffixes in Indian business registry and international listings
CORPORATE_SUFFIX_PATTERNS = [
    r"\bprivate\s+limited\b",
    r"\bpvt\.?\s*ltd\.?\b",
    r"\bpvt\b",
    r"\blimited\b",
    r"\bltd\.?\b",
    r"\bllp\b",
    r"\bllc\b",
    r"\bplc\b",
    r"\binc\.?\b",
    r"\bco\.?\s*ltd\.?\b",
    r"\bcorp\.?\b",
    r"\bcorporation\b",
]

# Temporal and ephemeral event patterns
EVENT_TEMPORAL_PATTERNS = [
    r"\bannual\s+show\s+\d{4}\b",
    r"\bannual\s+day\s+\d{4}\b",
    r"\bexhibition\s+\d{4}\b",
    r"\bfestival\s+\d{4}\b",
    r"\bfair\s+\d{4}\b",
    r"\bexpo\s+\d{4}\b",
    r"\bmela\s+\d{4}\b",
    r"\b\d{4}\s+edition\b",
    r"\b\d{4}\b",  # Standalone 4-digit years (1900-2099)
]

# Major Bengaluru localities and administrative divisions often appended as qualifiers
KNOWN_BENGALURU_LOCALITIES = [
    "rajarajeshwarinagar", "rr nagar", "marathahalli", "marathalli",
    "indiranagar", "koramangala", "whitefield", "jayanagar", "jp nagar",
    "malleshwaram", "malleswaram", "bannerghatta", "bannergatta",
    "hebbal", "yelahanka", "banashankari", "basavanagudi", "shivajinagar",
    "btm layout", "btm", "bellandur", "electronic city", "ecity",
    "domlur", "sarjapur", "sarjapura", "rajajinagar", "vijayanagar",
    "sadashivanagar", "frazer town", "richmond town", "mg road",
    "commercial street", "brigade road", "hosur road", "outer ring road",
    "orr", "harlur", "kasavanahalli", "kadugodi", "kundalahalli",
    "hitec city", "vimanapura", "hal", "ulsoor", "halasuru",
    "bangalore", "bengaluru",
]


class EnhancedNameNormalizer:
    """Extracts qualifiers while preserving underlying commercial entity identity."""

    def __init__(self):
        self.corp_regex = re.compile("|".join(CORPORATE_SUFFIX_PATTERNS), re.IGNORECASE)
        self.event_regex = re.compile("|".join(EVENT_TEMPORAL_PATTERNS), re.IGNORECASE)

    def normalize_and_extract(self, raw_name: Optional[str]) -> Dict[str, Any]:
        """Normalize raw POI name and extract structured components.

        Returns:
            Dict containing:
                - raw_name: unmodified input string
                - core_name: entity name stripped of corporate, temporal, and isolated locality tokens
                - corporate_suffix: extracted corporate suffix if found
                - event_qualifier: extracted temporal / event qualifier if found
                - locality_qualifier: extracted branch / locality qualifier if found
                - is_atm: whether the entity name explicitly indicates an ATM
                - is_bank: whether the entity name explicitly indicates a bank
        """
        if not raw_name or not isinstance(raw_name, str):
            return {
                "raw_name": raw_name or "",
                "core_name": "",
                "corporate_suffix": None,
                "event_qualifier": None,
                "locality_qualifier": None,
                "is_atm": False,
                "is_bank": False,
            }

        name = raw_name.strip()
        lower = name.lower()

        # Check ATM vs Bank facility semantics
        is_atm = bool(re.search(r"\b(atm|automated\s+teller\s+machine|cash\s+point|cash\s+dispenser)\b", lower))
        is_bank = bool(re.search(r"\b(bank|banking|branch)\b", lower)) and not is_atm

        # Extract temporal / event qualifiers
        event_match = self.event_regex.search(lower)
        event_qualifier = event_match.group(0).strip() if event_match else None
        cleaned_text = self.event_regex.sub(" ", lower)

        # Extract corporate suffixes
        corp_match = self.corp_regex.search(cleaned_text)
        corporate_suffix = corp_match.group(0).strip() if corp_match else None
        cleaned_text = self.corp_regex.sub(" ", cleaned_text)

        # Extract locality qualifiers often appended after comma, hyphen, or in parentheses
        locality_qualifier = None
        # Pattern like: "ICICI Bank, Bangalore-Rajarajeshwarinagar" or "ICICI Bank Bangalore-Marathalli"
        loc_pattern = r"[\,\(\/\-]\s*([a-z\s\-]+)$"
        m_loc = re.search(loc_pattern, cleaned_text)
        if m_loc:
            candidate_loc = m_loc.group(1).strip()
            for loc in KNOWN_BENGALURU_LOCALITIES:
                if loc in candidate_loc:
                    locality_qualifier = candidate_loc
                    cleaned_text = cleaned_text[:m_loc.start()]
                    break

        # Also check for space-separated "Bangalore-<locality>" or "<locality>" at the end
        if not locality_qualifier:
            bangalore_loc_pat = r"\b(bangalore|bengaluru)[\-\s]+([a-z\s]+)$"
            m_b_loc = re.search(bangalore_loc_pat, cleaned_text)
            if m_b_loc:
                locality_qualifier = m_b_loc.group(0).strip()
                cleaned_text = cleaned_text[:m_b_loc.start()]

        # Also check for trailing locality tokens directly if not separated by punctuation
        if not locality_qualifier:
            for loc in KNOWN_BENGALURU_LOCALITIES:
                if loc in ("bangalore", "bengaluru"):
                    continue
                trailing_pat = rf"\b{re.escape(loc)}\b\s*$"
                if re.search(trailing_pat, cleaned_text) and len(re.sub(trailing_pat, "", cleaned_text).strip()) > 3:
                    locality_qualifier = loc
                    cleaned_text = re.sub(trailing_pat, " ", cleaned_text)
                    break

        # Also clean any dangling "bangalore" / "bengaluru" from end of business name
        cleaned_text = re.sub(r"\b(bangalore|bengaluru)\b\s*$", "", cleaned_text)

        # Standard banking domain expansions: "small finance bank" -> "bank"
        cleaned_text = re.sub(r"\bsmall\s+finance\s+bank\b", "bank", cleaned_text)

        # Clean remaining punctuation and whitespace
        cleaned_core = re.sub(r"[^\w\s]", " ", cleaned_text)
        cleaned_core = re.sub(r"\s+", " ", cleaned_core).strip()

        # If core becomes empty (e.g. name was literally just "Limited" or a locality), revert to basic alphanumeric
        if not cleaned_core:
            cleaned_core = re.sub(r"[^\w\s]", " ", lower).strip()

        return {
            "raw_name": raw_name,
            "core_name": cleaned_core,
            "corporate_suffix": corporate_suffix,
            "event_qualifier": event_qualifier,
            "locality_qualifier": locality_qualifier,
            "is_atm": is_atm,
            "is_bank": is_bank,
        }
