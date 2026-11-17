"""Kannada naming, bilingual distribution, and lexical similarity profiling.

Analyzes native Kannada script (U+0C80–U+0CFF) frequency, English coexistence,
commercial token distributions, transliteration patterns, and lexical similarity baselines.
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, Any, List

import duckdb
from rapidfuzz import fuzz


KANNADA_REGEX = re.compile(r"[\u0C80-\u0CFF]")
LATIN_REGEX = re.compile(r"[A-Za-z]")


def jaccard_similarity(s1: str, s2: str) -> float:
    """Compute token-based Jaccard similarity."""
    t1 = set(s1.lower().split())
    t2 = set(s2.lower().split())
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def char_ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Compute character n-gram Jaccard similarity."""
    def get_ngrams(s: str) -> set:
        clean = "".join(s.lower().split())
        if len(clean) < n:
            return {clean}
        return {clean[i:i+n] for i in range(len(clean) - n + 1)}

    g1 = get_ngrams(s1)
    g2 = get_ngrams(s2)
    if not g1 or not g2:
        return 0.0
    return len(g1 & g2) / len(g1 | g2)


class NamingProfiler:
    """Profiles script distributions and benchmarks lexical similarity across proximate pairs."""

    def __init__(
        self,
        indexed_dataset_path: str = "data/processed/canonical_pois_h3.parquet",
        output_dir: str = "reports"
    ):
        self.dataset_path = Path(indexed_dataset_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect()

    def run_script_distribution(self) -> Dict[str, Any]:
        """Analyze presence and coexistence of Kannada script and Latin/English names."""
        print("Analyzing script distributions across OSM and Overture...")
        query = f"""
        SELECT 
            poi_source,
            count(*) as total_records,
            count(CASE WHEN regexp_matches(name_original, '[\u0C80-\u0CFF]') OR (name_kn IS NOT NULL AND length(trim(name_kn)) > 0) THEN 1 END) as has_kannada_script,
            count(CASE WHEN regexp_matches(name_original, '[A-Za-z]') OR (name_en IS NOT NULL AND length(trim(name_en)) > 0) THEN 1 END) as has_english_latin,
            count(CASE WHEN (regexp_matches(name_original, '[\u0C80-\u0CFF]') OR (name_kn IS NOT NULL AND length(trim(name_kn)) > 0))
                        AND (regexp_matches(name_original, '[A-Za-z]') OR (name_en IS NOT NULL AND length(trim(name_en)) > 0)) THEN 1 END) as has_both_kannada_and_english,
            count(CASE WHEN (regexp_matches(name_original, '[\u0C80-\u0CFF]') OR (name_kn IS NOT NULL AND length(trim(name_kn)) > 0))
                        AND NOT (regexp_matches(name_original, '[A-Za-z]') OR (name_en IS NOT NULL AND length(trim(name_en)) > 0)) THEN 1 END) as kannada_only,
            count(CASE WHEN NOT (regexp_matches(name_original, '[\u0C80-\u0CFF]') OR (name_kn IS NOT NULL AND length(trim(name_kn)) > 0))
                        AND (regexp_matches(name_original, '[A-Za-z]') OR (name_en IS NOT NULL AND length(trim(name_en)) > 0)) THEN 1 END) as english_only,
            count(CASE WHEN name_original IS NULL OR length(trim(name_original)) = 0 THEN 1 END) as unnamed_or_empty
        FROM '{self.dataset_path}'
        GROUP BY poi_source
        """
        rows = self.con.execute(query).fetchall()
        cols = [c[0] for c in self.con.description]
        script_stats = {}
        for r in rows:
            src = r[0]
            d = dict(zip(cols, r))
            tot = d["total_records"]
            d["kannada_pct"] = round(100.0 * d["has_kannada_script"] / tot, 2)
            d["english_pct"] = round(100.0 * d["has_english_latin"] / tot, 2)
            d["bilingual_pct"] = round(100.0 * d["has_both_kannada_and_english"] / tot, 2)
            script_stats[src] = d

        return script_stats

    def run_token_and_pattern_profiling(self) -> Dict[str, Any]:
        """Profile high-frequency naming tokens, commercial prefixes, and honorifics."""
        print("Profiling naming tokens and honorific patterns...")
        # Common commercial honorifics / keywords in Indian POIs
        keywords = [
            "sri", "shri", "shree", "bhavan", "bhavana", "sagar",
            "store", "stores", "bakery", "hotel", "restaurant",
            "medical", "pharmacy", "clinic", "hospital",
            "enterprises", "traders", "supermarket", "provision",
            "cafe", "coffee", "tea", "point", "corner", "center", "centre"
        ]

        q = f"""
        SELECT name_normalized
        FROM '{self.dataset_path}'
        WHERE name_normalized IS NOT NULL AND length(name_normalized) > 0
        """
        rows = self.con.execute(q).fetchall()
        total_names = len(rows)

        token_freq = {}
        token_lengths = []
        name_char_lengths = []

        for (name,) in rows:
            tokens = name.split()
            token_lengths.append(len(tokens))
            name_char_lengths.append(len(name))
            for t in tokens:
                if len(t) > 2:
                    token_freq[t] = token_freq.get(t, 0) + 1

        top_tokens = sorted(token_freq.items(), key=lambda x: x[1], reverse=True)[:25]
        honorific_counts = {kw: token_freq.get(kw, 0) for kw in keywords if kw in token_freq}

        return {
            "total_analyzed_names": total_names,
            "avg_tokens_per_name": round(sum(token_lengths) / len(token_lengths), 2),
            "avg_chars_per_name": round(sum(name_char_lengths) / len(name_char_lengths), 2),
            "top_25_tokens": dict(top_tokens),
            "common_commercial_keywords": honorific_counts
        }

    def run_lexical_similarity_baseline(self, max_pairs: int = 5000) -> Dict[str, Any]:
        """Compute baseline lexical similarity metrics on a sample of proximate candidate pairs (<=50m)."""
        print(f"Evaluating lexical similarity baseline on {max_pairs:,} proximate candidate pairs...")
        t0 = time.time()

        sample_csv = self.output_dir / "candidate_pairs_50m_sample.csv"
        if not sample_csv.exists():
            # If not yet generated, fallback to DuckDB direct sample query
            q = f"""
            SELECT o.name_original as osm_name, v.name_original as ov_name,
                   o.name_normalized as osm_norm, v.name_normalized as ov_norm,
                   ST_Distance(
                       ST_Transform(ST_Point(o.longitude, o.latitude), 'EPSG:4326', 'EPSG:32643'),
                       ST_Transform(ST_Point(v.longitude, v.latitude), 'EPSG:4326', 'EPSG:32643')
                   ) as dist
            FROM '{self.dataset_path}' o, '{self.dataset_path}' v
            WHERE o.poi_source = 'OSM' AND v.poi_source = 'OVERTURE'
              AND o.h3_res9 = v.h3_res9
              AND abs(o.latitude - v.latitude) <= 0.0005
              AND abs(o.longitude - v.longitude) <= 0.0005
              AND dist <= 50.0
            LIMIT {max_pairs}
            """
            rows = self.con.execute(q).fetchall()
            pairs = [(r[0], r[1], r[2], r[3], r[4]) for r in rows]
        else:
            q = f"""
            SELECT osm_name, ov_name, 
                   lower(trim(osm_name)) as osm_norm, lower(trim(ov_name)) as ov_norm, distance_meters
            FROM '{sample_csv}'
            WHERE osm_name IS NOT NULL AND ov_name IS NOT NULL
            LIMIT {max_pairs}
            """
            rows = self.con.execute(q).fetchall()
            pairs = [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

        if not pairs:
            return {"status": "no_pairs_available"}

        jaccard_scores = []
        ngram3_scores = []
        rf_ratio_scores = []
        rf_token_sort_scores = []
        rf_token_set_scores = []

        plausible_matches = []  # High lexical similarity pairs
        spatial_noise_pairs = []  # Geographically close but completely different names

        for osm_raw, ov_raw, osm_norm, ov_norm, dist in pairs:
            if not osm_norm or not ov_norm:
                continue
            jac = jaccard_similarity(osm_norm, ov_norm)
            ng3 = char_ngram_similarity(osm_norm, ov_norm, n=3)
            ratio = fuzz.ratio(osm_norm, ov_norm) / 100.0
            tsort = fuzz.token_sort_ratio(osm_norm, ov_norm) / 100.0
            tset = fuzz.token_set_ratio(osm_norm, ov_norm) / 100.0

            jaccard_scores.append(jac)
            ngram3_scores.append(ng3)
            rf_ratio_scores.append(ratio)
            rf_token_sort_scores.append(tsort)
            rf_token_set_scores.append(tset)

            if tset >= 0.85:
                plausible_matches.append({
                    "osm_name": osm_raw,
                    "ov_name": ov_raw,
                    "distance_meters": dist,
                    "token_set_ratio": round(tset, 2),
                    "token_sort_ratio": round(tsort, 2)
                })
            elif tset <= 0.20 and len(spatial_noise_pairs) < 15:
                spatial_noise_pairs.append({
                    "osm_name": osm_raw,
                    "ov_name": ov_raw,
                    "distance_meters": dist,
                    "token_set_ratio": round(tset, 2)
                })

        def calc_stats(scores: List[float]) -> Dict[str, float]:
            if not scores:
                return {}
            s_sorted = sorted(scores)
            n = len(s_sorted)
            return {
                "mean": round(sum(scores) / n, 4),
                "median": round(s_sorted[n // 2], 4),
                "p25": round(s_sorted[int(n * 0.25)], 4),
                "p75": round(s_sorted[int(n * 0.75)], 4),
                "pct_above_80": round(100.0 * sum(1 for s in scores if s >= 0.80) / n, 2),
                "pct_below_30": round(100.0 * sum(1 for s in scores if s < 0.30) / n, 2),
            }

        return {
            "sample_size": len(jaccard_scores),
            "jaccard_similarity": calc_stats(jaccard_scores),
            "char_3gram_similarity": calc_stats(ngram3_scores),
            "rapidfuzz_ratio": calc_stats(rf_ratio_scores),
            "rapidfuzz_token_sort_ratio": calc_stats(rf_token_sort_scores),
            "rapidfuzz_token_set_ratio": calc_stats(rf_token_set_scores),
            "plausible_match_candidates_count": len(plausible_matches),
            "plausible_match_candidates_sample": plausible_matches[:10],
            "spatial_noise_sample": spatial_noise_pairs[:5],
            "evaluation_duration_seconds": round(time.time() - t0, 2)
        }

    def run_full_profile(self) -> Dict[str, Any]:
        """Execute full naming and transliteration profiling and save report."""
        t0 = time.time()
        print("=" * 70)
        print("KANNADA NAMING AND TRANSLITERATION PROFILING")
        print("=" * 70)

        results = {
            "analysis_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "script_distribution": self.run_script_distribution(),
            "token_and_pattern_profiling": self.run_token_and_pattern_profiling(),
            "lexical_similarity_baseline": self.run_lexical_similarity_baseline(),
            "execution_duration_seconds": round(time.time() - t0, 2)
        }

        out_json = self.output_dir / "naming_and_transliteration_summary.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print(f"\nNaming analysis complete in {results['execution_duration_seconds']}s")
        print(f"Summary saved to: {out_json}")
        return results
