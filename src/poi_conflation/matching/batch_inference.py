"""Scalable batch inference pipeline for scoring POI candidate universe.

Features:
- Streaming parquet chunking (e.g., 50,000 pairs per batch) for 8 GB RAM constraints.
- Vectorized probability evaluation and 3-way triage (MATCH, UNCERTAIN, NON_MATCH).
- Incremental Parquet writing.
- Peak memory (RSS) and throughput tracking.
"""

import logging
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from src.poi_conflation.matching.supervised_model import SupervisedPOIMatcher

logger = logging.getLogger("batch_inference")


class BatchInferencePipeline:
    """Memory-conscious batch inference pipeline for universe scoring."""

    def __init__(
        self,
        model_path: str = "models/supervised_poi_matcher_v1.joblib",
        batch_size: int = 50000,
    ):
        self.matcher = SupervisedPOIMatcher.load(model_path)
        self.batch_size = batch_size
        self.feature_cols = self.matcher.feature_names
        self.match_threshold = self.matcher.thresholds.get("match_threshold", 0.55)
        self.uncertain_threshold = self.matcher.thresholds.get("uncertain_lower_threshold", 0.30)

    @staticmethod
    def _get_peak_memory_mb() -> float:
        """Get peak memory (RSS) in MB. Handles macOS bytes vs Linux KB."""
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return ru / (1024 * 1024)
        return ru / 1024

    def run(
        self,
        input_parquet: str = "data/processed/features/pairwise_features.parquet",
        output_parquet: str = "data/processed/predictions/supervised_predictions_universe.parquet",
    ) -> Dict[str, Any]:
        """Execute chunked streaming inference across the universe."""
        in_path = Path(input_parquet)
        out_path = Path(output_parquet)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not in_path.exists():
            raise FileNotFoundError(f"Input features parquet not found: {in_path}")

        pf = pq.ParquetFile(in_path)
        total_rows = pf.metadata.num_rows
        logger.info(f"Starting batch inference over {total_rows} candidate pairs with batch size {self.batch_size}...")

        # Output schema
        out_schema = pa.schema([
            ("candidate_pair_id", pa.string()),
            ("match_probability", pa.float32()),
            ("pred_decision", pa.string()),
            ("explanation_summary", pa.string()),
        ])

        writer = pq.ParquetWriter(out_path, out_schema, compression="zstd")

        total_processed = 0
        match_count = 0
        uncertain_count = 0
        non_match_count = 0
        prob_sum = 0.0
        prob_sq_sum = 0.0

        start_time = time.perf_counter()

        try:
            for batch_idx, record_batch in enumerate(pf.iter_batches(batch_size=self.batch_size)):
                b_len = len(record_batch)
                pid_col = "candidate_pair_id" if "candidate_pair_id" in record_batch.schema.names else "pair_id"
                pair_ids = record_batch[pid_col].to_pylist()

                # Extract feature matrix X
                X = np.column_stack([record_batch[c].to_numpy() for c in self.feature_cols]).astype(np.float32)

                # Vectorized probability prediction
                probas = self.matcher.predict_proba(X)
                probas_f32 = probas.astype(np.float32)

                # Fast vectorized decision categorization
                decisions = []
                explanations = []

                # Compute vectors for explanation summaries
                dist_v = record_batch["feat_distance_meters"].to_numpy()
                jw_v = record_batch["feat_jaro_winkler"].to_numpy()

                for p, d, j in zip(probas, dist_v, jw_v):
                    if p >= self.match_threshold:
                        dec = "MATCH"
                        match_count += 1
                        exp = f"High match probability ({p:.2f}) | Dist: {d:.1f}m | Name Sim: {j:.2f}"
                    elif p >= self.uncertain_threshold:
                        dec = "UNCERTAIN"
                        uncertain_count += 1
                        exp = f"Borderline probability ({p:.2f}) | Dist: {d:.1f}m | Name Sim: {j:.2f} — Needs adjudication"
                    else:
                        dec = "NON_MATCH"
                        non_match_count += 1
                        exp = f"Low match probability ({p:.2f}) | Dist: {d:.1f}m | Name Sim: {j:.2f}"
                    decisions.append(dec)
                    explanations.append(exp)

                prob_sum += float(np.sum(probas))
                prob_sq_sum += float(np.sum(probas ** 2))
                total_processed += b_len

                # Write out batch
                out_batch = pa.RecordBatch.from_arrays(
                    [
                        pa.array(pair_ids, type=pa.string()),
                        pa.array(probas_f32, type=pa.float32()),
                        pa.array(decisions, type=pa.string()),
                        pa.array(explanations, type=pa.string()),
                    ],
                    schema=out_schema,
                )
                writer.write_batch(out_batch)

                if (batch_idx + 1) % 4 == 0 or total_processed == total_rows:
                    elapsed = time.perf_counter() - start_time
                    fps = total_processed / max(1e-6, elapsed)
                    logger.info(f"Processed {total_processed}/{total_rows} pairs ({total_processed/total_rows*100:.1f}%) in {elapsed:.2f}s ({fps:.0f} pairs/sec)")
        finally:
            writer.close()

        total_elapsed = time.perf_counter() - start_time
        peak_mem_mb = self._get_peak_memory_mb()
        overall_throughput = total_processed / max(1e-6, total_elapsed)

        mean_prob = prob_sum / max(1, total_processed)
        std_prob = float(np.sqrt(max(0.0, (prob_sq_sum / max(1, total_processed)) - (mean_prob ** 2))))

        metrics = {
            "metadata": {
                "inference_timestamp": datetime.now(timezone.utc).isoformat(),
                "milestone": "Milestone 15",
                "model_identifier": self.matcher.model_type,
                "input_features": str(in_path),
                "output_predictions": str(out_path),
                "batch_size": self.batch_size,
                "thresholds": {
                    "match_threshold": self.match_threshold,
                    "uncertain_threshold": self.uncertain_threshold,
                },
            },
            "performance": {
                "total_candidate_pairs": total_processed,
                "execution_time_seconds": round(total_elapsed, 3),
                "throughput_pairs_per_sec": round(overall_throughput, 1),
                "peak_memory_mb": round(peak_mem_mb, 2),
                "latency_microsec_per_pair": round((total_elapsed / max(1, total_processed)) * 1e6, 2),
            },
            "decision_distribution": {
                "MATCH": {
                    "count": match_count,
                    "percentage": round(match_count / max(1, total_processed) * 100, 2),
                },
                "UNCERTAIN": {
                    "count": uncertain_count,
                    "percentage": round(uncertain_count / max(1, total_processed) * 100, 2),
                },
                "NON_MATCH": {
                    "count": non_match_count,
                    "percentage": round(non_match_count / max(1, total_processed) * 100, 2),
                },
            },
            "score_statistics": {
                "mean_match_probability": round(mean_prob, 4),
                "std_match_probability": round(std_prob, 4),
            },
            "comparison_against_m9_baseline": {
                "m9_rule_v1_matches": 5543,
                "supervised_matches": match_count,
                "m9_rule_v1_uncertain": 76882,
                "supervised_uncertain": uncertain_count,
                "m9_rule_v1_non_matches": 523003,
                "supervised_non_matches": non_match_count,
                "conflation_precision_gain": "Supervised model provides continuous calibrated probabilities instead of discrete heuristic sums",
            },
        }

        return metrics
