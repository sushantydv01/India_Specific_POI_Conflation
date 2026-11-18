"""Candidate blocking strategy feature extraction.

Captures which blocking channels contributed to candidate generation:
spatial 50m, token containment, exact name, transliteration, phonetic,
and multi-strategy overlap metrics.
"""

from typing import Dict, Any, List, Optional, Sequence


def extract_strategy_features(blocking_strategies: Optional[Sequence[str]]) -> Dict[str, float]:
    """Extract all 7 candidate generation strategy features."""
    strats = set(blocking_strategies or [])
    strat_count = float(len(strats))
    multi_overlap = 1.0 if strat_count > 1.0 else 0.0

    spatial_50m = 1.0 if "spatial_50m" in strats else 0.0
    tok_containment = 1.0 if ("token_containment" in strats or "token_containment_100m" in strats) else 0.0
    exact_name = 1.0 if "exact_name" in strats else 0.0
    translit = 1.0 if ("transliteration" in strats or "transliteration_phonetic" in strats) else 0.0
    phonetic = 1.0 if ("phonetic" in strats or "transliteration_phonetic" in strats) else 0.0

    return {
        "feat_strat_spatial_50m": spatial_50m,
        "feat_strat_token_containment": tok_containment,
        "feat_strat_exact_name": exact_name,
        "feat_strat_translit": translit,
        "feat_strat_phonetic": phonetic,
        "feat_multi_strategy_overlap": multi_overlap,
        "feat_strategy_count": strat_count,
    }
