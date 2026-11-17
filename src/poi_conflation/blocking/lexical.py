"""Lexical, token-based, and n-gram candidate blocking strategies.

Implements:
1. Exact normalized name blocking.
2. Distinctive token-based blocking (inverted index).
3. Character 3-gram similarity blocking.
4. Token-prefix blocking (4-character prefix matching).
5. Name containment blocking (subset / superset).
6. Alternate-name and alias blocking.
"""

import re
from typing import Dict, Any, List, Set, Tuple, Optional
import duckdb
from rapidfuzz import fuzz

# Common Indian urban & commercial stopwords that lack distinctive blocking power
STOPWORDS = {
    "the", "and", "for", "with", "from",
    "bangalore", "bengaluru", "karnataka", "india",
    "road", "street", "cross", "main", "avenue", "lane",
    "near", "opp", "opposite", "behind", "beside", "next",
    "layout", "stage", "phase", "block", "sector", "nagar",
    "pvt", "ltd", "limited", "private", "enterprise", "enterprises",
    "co", "corp", "corporation", "branch", "shop", "center", "centre"
}


def extract_distinctive_tokens(name: Optional[str]) -> List[str]:
    """Extract informative non-stopword tokens of length >= 4."""
    if not name:
        return []
    tokens = re.findall(r"\b\w+\b", name.lower())
    return [t for t in tokens if len(t) >= 4 and t not in STOPWORDS]


def generate_char_ngrams(text: str, n: int = 3) -> Set[str]:
    """Generate set of character n-grams from string."""
    clean = re.sub(r"\s+", "", text.lower())
    if len(clean) < n:
        return {clean} if clean else set()
    return {clean[i:i+n] for i in range(len(clean) - n + 1)}


class LexicalBlocker:
    """Manages lexical, token-based, and n-gram candidate blocking."""

    def __init__(self, dataset_path: str = "data/processed/canonical_pois_h3.parquet"):
        self.dataset_path = dataset_path
        self.con = duckdb.connect()

    def evaluate_exact_name_blocking(self) -> Dict[str, Any]:
        """Evaluate exact normalized name candidate pairs across providers."""
        query = f"""
        SELECT 
            count(*) as pair_count,
            count(distinct o.source_record_id) as matched_osm,
            count(distinct v.source_record_id) as matched_ov
        FROM '{self.dataset_path}' o
        JOIN '{self.dataset_path}' v 
          ON o.name_normalized = v.name_normalized
        WHERE o.poi_source = 'OSM' 
          AND v.poi_source = 'OVERTURE'
          AND length(trim(o.name_normalized)) >= 4
          AND o.name_normalized NOT IN ('bank of india', 'state bank of india', 'icici bank', 'hdfc bank', 'axis bank', 'atm', 'temple', 'church', 'mosque');
        """
        r = self.con.execute(query).fetchone()
        return {
            "strategy": "exact_normalized_name",
            "candidate_pairs": r[0],
            "unique_osm_records": r[1],
            "unique_overture_records": r[2],
            "description": "Exact match on normalized name (excluding generic national banking chains)"
        }

    def check_name_containment(self, name_a: str, name_b: str) -> bool:
        """Check whether one normalized name is completely contained in the other."""
        if not name_a or not name_b:
            return False
        na = name_a.strip().lower()
        nb = name_b.strip().lower()
        if len(na) < 4 or len(nb) < 4:
            return False
        if na == nb:
            return True
        return (f" {na} " in f" {nb} ") or (f" {nb} " in f" {na} ")

    def compute_lexical_similarity_metrics(
        self,
        name_a: Optional[str],
        name_b: Optional[str]
    ) -> Dict[str, Any]:
        """Compute full suite of lexical similarities between two names."""
        if not name_a or not name_b:
            return {
                "exact_match": False,
                "token_overlap_count": 0,
                "char_3gram_similarity": 0.0,
                "token_set_ratio": 0.0,
                "name_containment": False,
            }

        na = name_a.strip().lower()
        nb = name_b.strip().lower()

        exact = (na == nb)
        tokens_a = set(extract_distinctive_tokens(na))
        tokens_b = set(extract_distinctive_tokens(nb))
        overlap = len(tokens_a & tokens_b)

        ng1 = generate_char_ngrams(na, 3)
        ng2 = generate_char_ngrams(nb, 3)
        ngram_sim = len(ng1 & ng2) / len(ng1 | ng2) if (ng1 and ng2) else 0.0

        containment = self.check_name_containment(na, nb)
        tset = fuzz.token_set_ratio(na, nb) / 100.0

        return {
            "exact_match": exact,
            "token_overlap_count": overlap,
            "char_3gram_similarity": round(ngram_sim, 3),
            "token_set_ratio": round(tset, 3),
            "name_containment": containment,
        }
