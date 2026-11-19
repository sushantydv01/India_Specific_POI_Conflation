"""Script running review queue prioritization for Milestone 18.

Ranks the 2,842 unresolved pairs into explainable tiers and produces:
- data/processed/review/prioritized_unresolved_queue.parquet
- data/processed/review/prioritized_unresolved_queue.csv
- reports/m18_review_queue_analysis.md
"""

import logging
from src.poi_conflation.matching.review_prioritizer import ReviewQueuePrioritizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("prioritize_review_queue")

if __name__ == "__main__":
    logger.info("Executing Review Queue Prioritization Pipeline...")
    prioritizer = ReviewQueuePrioritizer()
    rep = prioritizer.export_report()
    logger.info(f"Review queue prioritization complete: {rep}")
