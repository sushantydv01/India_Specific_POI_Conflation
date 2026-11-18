#!/usr/bin/env python3
"""CLI script for running the explainable deterministic POI matching engine.

Scores the complete candidate universe (605,428 pairs) against transparent
engineering weights and contradiction guardrails. Produces comprehensive
diagnostic reports and representative evidence explanations.
"""

import argparse
import json
import logging
import math
import os
import resource
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import duckdb

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.matching.config import MatchingConfig
from src.poi_conflation.matching.engine import (
    ExplainableMatchingEngine,
    MatchingDecision,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_matching_baseline")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run explainable POI matching baseline across pairwise features."
    )
    parser.add_argument(
        "--features",
        default="data/processed/features/pairwise_features.parquet",
        help="Path to extracted pairwise features Parquet file.",
    )
    parser.add_argument(
        "--config",
        default="configs/matching_baseline.yaml",
        help="Path to matching configuration YAML file.",
    )
    parser.add_argument(
        "--report",
        default="reports/matching_baseline_report.json",
        help="Path for diagnostic evaluation report JSON.",
    )
    parser.add_argument(
        "--samples",
        default="reports/matching_sample_explanations.json",
        help="Path for sample evidence explanations JSON.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Batch size for streaming evaluation.",
    )
    return parser.parse_args()


def calculate_quantiles(values: List[float]) -> Dict[str, float]:
    """Calculate summary percentiles and moments for a list of floats."""
    if not values:
        return {}
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    variance = sum((x - mean) ** 2 for x in s) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    def p(q: float) -> float:
        idx = int(round(q * (n - 1)))
        return round(s[idx], 4)

    return {
        "min": round(s[0], 4),
        "p10": p(0.10),
        "p25": p(0.25),
        "p50_median": p(0.50),
        "p75": p(0.75),
        "p90": p(0.90),
        "max": round(s[-1], 4),
        "mean": round(mean, 4),
        "std_dev": round(std, 4),
    }


def main():
    args = parse_args()
    start_time = time.time()

    logger.info("Initializing Explainable POI Matching Engine...")
    config = MatchingConfig.load(args.config)
    engine = ExplainableMatchingEngine(config=config)

    logger.info(f"Features dataset: {args.features}")
    logger.info(f"Model configuration: {args.config} (v{config.version})")

    con = duckdb.connect()

    # Query all features joined with candidate pair metadata
    rel = con.execute(f"SELECT * FROM '{args.features}'")
    col_names = [d[0] for d in rel.description]

    total_pairs = 0
    decision_counts = {MatchingDecision.MATCH: 0, MatchingDecision.NON_MATCH: 0, MatchingDecision.UNCERTAIN: 0}
    guardrail_counts: Dict[str, int] = {}
    strategy_decisions: Dict[str, Dict[str, int]] = {
        "spatial_50m": {MatchingDecision.MATCH: 0, MatchingDecision.NON_MATCH: 0, MatchingDecision.UNCERTAIN: 0},
        "exact_name": {MatchingDecision.MATCH: 0, MatchingDecision.NON_MATCH: 0, MatchingDecision.UNCERTAIN: 0},
        "token_containment": {MatchingDecision.MATCH: 0, MatchingDecision.NON_MATCH: 0, MatchingDecision.UNCERTAIN: 0},
        "transliteration_phonetic": {MatchingDecision.MATCH: 0, MatchingDecision.NON_MATCH: 0, MatchingDecision.UNCERTAIN: 0},
        "multi_strategy": {MatchingDecision.MATCH: 0, MatchingDecision.NON_MATCH: 0, MatchingDecision.UNCERTAIN: 0},
    }

    # Reservoir / sample collectors for representative explanations
    sample_explanations: List[Dict[str, Any]] = []
    category_disjoint_samples: List[Dict[str, Any]] = []
    same_brand_branch_samples: List[Dict[str, Any]] = []
    same_bldg_diff_biz_samples: List[Dict[str, Any]] = []
    translit_match_samples: List[Dict[str, Any]] = []
    high_match_samples: List[Dict[str, Any]] = []
    uncertain_samples: List[Dict[str, Any]] = []

    all_scores: List[float] = []

    batch_idx = 0
    while True:
        rows = rel.fetchmany(args.batch_size)
        if not rows:
            break

        batch_dicts = [dict(zip(col_names, r)) for r in rows]

        for d in batch_dicts:
            eval_res = engine.evaluate_pair(d)
            score = eval_res["final_score"]
            decision = eval_res["decision"]
            applied_guards = eval_res["applied_guardrails"]

            total_pairs += 1
            decision_counts[decision] += 1
            all_scores.append(score)

            for g in applied_guards:
                guardrail_counts[g] = guardrail_counts.get(g, 0) + 1

            # Strategy breakdowns
            if d.get("feat_strat_spatial_50m", 0.0) == 1.0:
                strategy_decisions["spatial_50m"][decision] += 1
            if d.get("feat_strat_exact_name", 0.0) == 1.0:
                strategy_decisions["exact_name"][decision] += 1
            if d.get("feat_strat_token_containment", 0.0) == 1.0:
                strategy_decisions["token_containment"][decision] += 1
            if d.get("feat_strat_translit", 0.0) == 1.0 or d.get("feat_strat_phonetic", 0.0) == 1.0:
                strategy_decisions["transliteration_phonetic"][decision] += 1
            if d.get("feat_multi_strategy_overlap", 0.0) == 1.0:
                strategy_decisions["multi_strategy"][decision] += 1

            # Sample collection
            sample_entry = {
                "candidate_pair_id": d["candidate_pair_id"],
                "osm_source_id": d["osm_source_id"],
                "ov_source_id": d["ov_source_id"],
                "evaluation": eval_res,
            }

            if "CATEGORY_DISJOINT" in applied_guards and len(category_disjoint_samples) < 5:
                category_disjoint_samples.append(sample_entry)
            elif "SAME_BRAND_DIFFERENT_BRANCH" in applied_guards and len(same_brand_branch_samples) < 5:
                same_brand_branch_samples.append(sample_entry)
            elif "SAME_BUILDING_DIFFERENT_BUSINESS" in applied_guards and len(same_bldg_diff_biz_samples) < 5:
                same_bldg_diff_biz_samples.append(sample_entry)
            elif d.get("feat_translit_available", 0.0) == 1.0 and decision == MatchingDecision.MATCH and len(translit_match_samples) < 5:
                translit_match_samples.append(sample_entry)
            elif decision == MatchingDecision.MATCH and len(high_match_samples) < 5:
                high_match_samples.append(sample_entry)
            elif decision == MatchingDecision.UNCERTAIN and len(uncertain_samples) < 5:
                uncertain_samples.append(sample_entry)

        batch_idx += 1

    con.close()
    elapsed_sec = time.time() - start_time
    peak_mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

    quantiles = calculate_quantiles(all_scores)

    # Consolidate 30 representative explanations
    representative_samples = (
        high_match_samples
        + uncertain_samples
        + category_disjoint_samples
        + same_brand_branch_samples
        + same_bldg_diff_biz_samples
        + translit_match_samples
    )

    # Write sample explanations JSON
    samples_path = Path(args.samples)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    with open(samples_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": "1.0.0",
                "sample_count": len(representative_samples),
                "samples": representative_samples,
            },
            f,
            indent=2,
        )

    # Construct comprehensive report
    report = {
        "metadata": {
            "model_identifier": config.model_name,
            "version": config.version,
            "description": config.description,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "evaluation_universe": "BBMP Bengaluru OSM-Overture Conflation Candidate Pairs",
            "weights": config.feature_group_weights,
            "thresholds": config.thresholds,
        },
        "universe_summary": {
            "total_candidate_pairs_evaluated": total_pairs,
            "execution_time_seconds": round(elapsed_sec, 2),
            "throughput_pairs_per_sec": round(total_pairs / elapsed_sec, 1) if elapsed_sec > 0 else 0,
            "peak_memory_mb": round(peak_mem_mb, 2),
        },
        "decision_distribution": {
            "MATCH": {
                "count": decision_counts[MatchingDecision.MATCH],
                "percentage": round(decision_counts[MatchingDecision.MATCH] / total_pairs * 100, 2),
            },
            "NON_MATCH": {
                "count": decision_counts[MatchingDecision.NON_MATCH],
                "percentage": round(decision_counts[MatchingDecision.NON_MATCH] / total_pairs * 100, 2),
            },
            "UNCERTAIN": {
                "count": decision_counts[MatchingDecision.UNCERTAIN],
                "percentage": round(decision_counts[MatchingDecision.UNCERTAIN] / total_pairs * 100, 2),
            },
        },
        "score_statistics": quantiles,
        "guardrail_overrides": {
            "total_guardrail_triggers": sum(guardrail_counts.values()),
            "by_guardrail": guardrail_counts,
        },
        "decisions_by_blocking_strategy": strategy_decisions,
        "methodological_caveats": [
            "Baseline weights represent transparent engineering hypotheses, NOT statistically learned or calibrated probabilities.",
            "Decision distributions reflect candidate-pair universe properties (candidate generation recall-oriented expansion), not random sampling prevalence.",
            "Zero false precision/recall/F1 claims are made: no large-scale verified ground truth exists yet for independent supervised evaluation."
        ],
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Matching baseline execution completed successfully:")
    logger.info(f"  Total pairs evaluated: {total_pairs:,}")
    logger.info(f"  MATCH: {decision_counts[MatchingDecision.MATCH]:,} ({report['decision_distribution']['MATCH']['percentage']}%)")
    logger.info(f"  NON_MATCH: {decision_counts[MatchingDecision.NON_MATCH]:,} ({report['decision_distribution']['NON_MATCH']['percentage']}%)")
    logger.info(f"  UNCERTAIN: {decision_counts[MatchingDecision.UNCERTAIN]:,} ({report['decision_distribution']['UNCERTAIN']['percentage']}%)")
    logger.info(f"  Median Score: {quantiles['p50_median']}, Mean: {quantiles['mean']}")
    logger.info(f"  Guardrails triggered: {sum(guardrail_counts.values()):,}")
    logger.info(f"  Execution time: {elapsed_sec:.2f}s ({report['universe_summary']['throughput_pairs_per_sec']:,} pairs/s)")
    logger.info(f"  Report written to: {args.report}")
    logger.info(f"  Sample explanations written to: {args.samples}")


if __name__ == "__main__":
    main()
