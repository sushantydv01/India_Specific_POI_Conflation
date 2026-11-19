"""Script running geospatial intelligence analysis for Milestone 18.

Executes spatial coverage, distance analysis, H3 clustering, and visualization exports.
Produces reports/m18_geospatial_analysis.md and figures in reports/figures/.
"""

import logging
from src.poi_conflation.analysis.geospatial_intelligence import GeospatialIntelligenceAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_geospatial_intelligence")

if __name__ == "__main__":
    logger.info("Executing Geospatial Intelligence Pipeline...")
    analyzer = GeospatialIntelligenceAnalyzer()
    rep = analyzer.export_report()
    logger.info(f"Geospatial analysis complete: {rep}")
