#!/usr/bin/env python3
"""Unified master runner for Exploratory Data Analysis, Spatial Proximity,
Kannada Naming Profiling, and Analytical Visualizations.
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.poi_conflation.analysis.eda import EDAAnalyzer
from src.poi_conflation.analysis.spatial_proximity import SpatialProximityAnalyzer
from src.poi_conflation.analysis.naming_profiler import NamingProfiler
from src.poi_conflation.analysis.visualizations import Visualizer


def main():
    t_start = time.time()
    print("=" * 70)
    print("BENGALURU POI EXPLORATORY DATA ANALYSIS & SPATIAL PROXIMITY")
    print("=" * 70)

    # 1. Exploratory Data Analysis
    eda_analyzer = EDAAnalyzer()
    eda_summary = eda_analyzer.run_full_eda()

    # 2. Spatial Proximity Analysis
    prox_analyzer = SpatialProximityAnalyzer()
    prox_summary = prox_analyzer.run_analysis()

    # 3. Kannada Naming & Transliteration Profiling
    naming_profiler = NamingProfiler()
    naming_summary = naming_profiler.run_full_profile()

    # 4. Generate Visualizations
    print("\n" + "=" * 70)
    print("GENERATING ANALYTICAL VISUALIZATIONS")
    print("=" * 70)
    viz = Visualizer()
    viz.generate_all()

    total_time = round(time.time() - t_start, 2)
    print("\n" + "=" * 70)
    print(f"ALL ANALYSES AND VISUALIZATIONS COMPLETE IN {total_time}s")
    print("Generated Artifacts:")
    print("  - reports/eda_summary.json")
    print("  - reports/spatial_proximity_summary.json")
    print("  - reports/naming_and_transliteration_summary.json")
    print("  - reports/candidate_pairs_50m_sample.csv")
    print("  - reports/figures/*.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
