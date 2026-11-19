"""Script running Indic language and transliteration intelligence analysis for Milestone 18.

Outputs reports/m18_indic_language_analysis.md and data/processed/benchmark/evaluation_views/queue_kannada_expansion.csv.
"""

import logging
from src.poi_conflation.analysis.indic_language_intelligence import IndicLanguageIntelligenceAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_indic_language_analysis")

if __name__ == "__main__":
    logger.info("Executing Indic Language Intelligence Pipeline...")
    analyzer = IndicLanguageIntelligenceAnalyzer()
    rep = analyzer.export_report()
    logger.info(f"Indic language analysis complete: {rep}")
