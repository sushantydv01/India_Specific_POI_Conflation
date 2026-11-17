"""Analytical visualization generator for Bengaluru POI conflation research.

Generates reproducible figures for spatial density, category distribution,
attribute completeness, cross-source proximity, and naming script coverage.
Saved to reports/figures/.
"""

import json
from pathlib import Path
from typing import Dict, Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


class Visualizer:
    """Generates publication-quality charts from EDA, proximity, and naming analysis outputs."""

    def __init__(
        self,
        reports_dir: str = "reports",
        figures_dir: str = "reports/figures"
    ):
        self.reports_dir = Path(reports_dir)
        self.figures_dir = Path(figures_dir)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        # Apply standard style parameters
        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.autolayout": True,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linestyle": "--"
        })

    def plot_category_distribution(self, eda_data: Dict[str, Any]):
        """Plot cross-source category share comparison."""
        categories_data = eda_data.get("category_analysis", {}).get("canonical_categories", [])
        if not categories_data:
            return

        cats = [c["category"] for c in categories_data][::-1]
        ov_counts = [c["overture_count"] for c in categories_data][::-1]
        osm_counts = [c["osm_count"] for c in categories_data][::-1]

        y = np.arange(len(cats))
        height = 0.35

        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
        ax.barh(y + height/2, ov_counts, height, label="Overture (197.8k total)", color="#1f77b4", alpha=0.9)
        ax.barh(y - height/2, osm_counts, height, label="OSM (49.0k total)", color="#ff7f0e", alpha=0.9)

        ax.set_xlabel("Record Count (Log Scale)")
        ax.set_xscale("log")
        ax.set_title("Canonical Category Distribution: OSM vs Overture (Bengaluru BBMP)")
        ax.set_yticks(y)
        ax.set_yticklabels(cats)
        ax.legend(loc="lower right")

        out_path = self.figures_dir / "category_distribution_comparison.png"
        fig.savefig(out_path)
        plt.close(fig)
        print(f"Saved figure: {out_path}")

    def plot_attribute_completeness(self, eda_data: Dict[str, Any]):
        """Plot attribute completeness matrix comparison."""
        matrix = eda_data.get("attribute_completeness_matrix", {})
        if not matrix:
            return

        attrs = list(matrix.keys())[::-1]
        ov_pcts = [matrix[a].get("OVERTURE_pct", 0) for a in attrs]
        osm_pcts = [matrix[a].get("OSM_pct", 0) for a in attrs]

        y = np.arange(len(attrs))
        height = 0.35

        fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
        ax.barh(y + height/2, ov_pcts, height, label="Overture Places", color="#2ca02c", alpha=0.85)
        ax.barh(y - height/2, osm_pcts, height, label="OpenStreetMap POIs", color="#9467bd", alpha=0.85)

        ax.set_xlabel("Field Completeness Percentage (%)")
        ax.set_xlim(0, 105)
        ax.set_title("Attribute Completeness Comparison: OSM vs Overture")
        ax.set_yticks(y)
        ax.set_yticklabels(attrs)
        ax.legend(loc="lower right")

        for i, (ov, osm) in enumerate(zip(ov_pcts, osm_pcts)):
            ax.text(ov + 1, i + height/2, f"{ov:.1f}%", va="center", fontsize=8, color="#1b6d1b")
            ax.text(osm + 1, i - height/2, f"{osm:.1f}%", va="center", fontsize=8, color="#5e3c7a")

        out_path = self.figures_dir / "attribute_completeness_matrix.png"
        fig.savefig(out_path)
        plt.close(fig)
        print(f"Saved figure: {out_path}")

    def plot_proximity_candidate_distribution(self, prox_data: Dict[str, Any]):
        """Plot candidate pairs and matched OSM record counts across distance thresholds."""
        thresholds = prox_data.get("distance_thresholds", [])
        if not thresholds:
            return

        dists = [t["distance_threshold_meters"] for t in thresholds]
        pairs = [t["total_candidate_pairs"] for t in thresholds]
        osm_matched = [t["osm_records_with_candidates"] for t in thresholds]
        osm_cov_pct = [t["osm_coverage_pct"] for t in thresholds]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

        # Plot 1: Total Candidate Pairs (Growth with distance)
        ax1.plot(dists, pairs, marker="o", color="#d62728", linewidth=2, markersize=6)
        ax1.set_xlabel("Distance Threshold (meters)")
        ax1.set_ylabel("Total Nearby Cross-Source Pairs")
        ax1.set_title("Cross-Source Candidate Pair Volume Growth")
        for x, y in zip(dists, pairs):
            ax1.annotate(f"{y:,}", (x, y), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)

        # Plot 2: Matched OSM Records Coverage
        ax2.bar([str(int(d)) + "m" for d in dists], osm_cov_pct, color="#1f77b4", alpha=0.85, width=0.5)
        ax2.set_xlabel("Distance Threshold")
        ax2.set_ylabel("OSM Records with >=1 Candidate (%)")
        ax2.set_title("OSM Candidate Reachability Across Distance")
        ax2.set_ylim(0, 100)
        for i, (cnt, pct) in enumerate(zip(osm_matched, osm_cov_pct)):
            ax2.text(i, pct + 2, f"{pct}%\n({cnt:,})", ha="center", fontsize=8)

        out_path = self.figures_dir / "cross_source_proximity_candidate_distribution.png"
        fig.savefig(out_path)
        plt.close(fig)
        print(f"Saved figure: {out_path}")

    def plot_kannada_naming_coverage(self, naming_data: Dict[str, Any]):
        """Plot script coverage and bilingual coexistence."""
        scripts = naming_data.get("script_distribution", {})
        if not scripts:
            return

        sources = ["OSM", "OVERTURE"]
        eng_only = [scripts[s]["english_only"] for s in sources]
        bilingual = [scripts[s]["has_both_kannada_and_english"] for s in sources]
        kan_only = [scripts[s]["kannada_only"] for s in sources]
        unnamed = [scripts[s]["unnamed_or_empty"] for s in sources]

        totals = [scripts[s]["total_records"] for s in sources]
        eng_pct = [100.0 * v / t for v, t in zip(eng_only, totals)]
        bi_pct = [100.0 * v / t for v, t in zip(bilingual, totals)]
        kan_pct = [100.0 * v / t for v, t in zip(kan_only, totals)]
        un_pct = [100.0 * v / t for v, t in zip(unnamed, totals)]

        x = np.arange(len(sources))
        width = 0.45

        fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
        ax.bar(x, eng_pct, width, label="English / Latin Only", color="#3b528b")
        ax.bar(x, bi_pct, width, bottom=eng_pct, label="Bilingual (Kannada + Latin)", color="#5ec962")
        bottom_kan = [e + b for e, b in zip(eng_pct, bi_pct)]
        ax.bar(x, kan_pct, width, bottom=bottom_kan, label="Kannada Script Only", color="#fde725")
        bottom_un = [e + b + k for e, b, k in zip(eng_pct, bi_pct, kan_pct)]
        ax.bar(x, un_pct, width, bottom=bottom_un, label="Unnamed / Empty", color="#d3d3d3")

        ax.set_ylabel("Proportion of Records (%)")
        ax.set_ylim(0, 105)
        ax.set_title("Script Distribution & Vernacular Coexistence: Bengaluru POIs")
        ax.set_xticks(x)
        ax.set_xticklabels([f"OSM\n({totals[0]:,} records)", f"Overture\n({totals[1]:,} records)"])
        ax.legend(loc="upper right")

        out_path = self.figures_dir / "kannada_english_naming_coverage.png"
        fig.savefig(out_path)
        plt.close(fig)
        print(f"Saved figure: {out_path}")

    def plot_h3_spatial_density(self, eda_data: Dict[str, Any]):
        """Plot top 10 H3 Resolution 8 density hotspots."""
        hotspots = eda_data.get("spatial_distribution", {}).get("top_hotspots_res8", [])[:10]
        if not hotspots:
            return

        cells = [h["h3_res8"] for h in hotspots][::-1]
        ov_pois = [h["overture_pois"] for h in hotspots][::-1]
        osm_pois = [h["osm_pois"] for h in hotspots][::-1]

        y = np.arange(len(cells))
        height = 0.35

        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
        ax.barh(y + height/2, ov_pois, height, label="Overture POIs", color="#1f77b4", alpha=0.9)
        ax.barh(y - height/2, osm_pois, height, label="OSM POIs", color="#ff7f0e", alpha=0.9)

        ax.set_xlabel("POIs per H3 Resolution 8 Cell (~0.74 km²)")
        ax.set_title("Top 10 High-Density Commercial Hotspots (H3 Resolution 8)")
        ax.set_yticks(y)
        ax.set_yticklabels([f"Cell {c[-6:]}" for c in cells])
        ax.legend(loc="lower right")

        out_path = self.figures_dir / "h3_res8_density_hotspots.png"
        fig.savefig(out_path)
        plt.close(fig)
        print(f"Saved figure: {out_path}")

    def plot_distance_histogram(self, prox_data: Dict[str, Any]):
        """Plot distance percentile distribution of nearby candidate pairs."""
        stats = prox_data.get("distance_distribution_200m", {})
        if not stats:
            return

        percentiles = ["p10", "p25", "p50 (median)", "p75", "p90"]
        values = [
            stats.get("p10_meters", 0),
            stats.get("p25_meters", 0),
            stats.get("p50_median_meters", 0),
            stats.get("p75_meters", 0),
            stats.get("p90_meters", 0),
        ]

        fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
        bars = ax.bar(percentiles, values, color="#8c564b", alpha=0.85, width=0.5)
        ax.set_ylabel("Geodesic Metric Distance (meters)")
        ax.set_title("Distance Quantiles for Cross-Source Pairs within 200m")
        ax.set_ylim(0, 220)

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{height:.1f}m",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha="center", va="bottom", fontsize=9)

        ax.axhline(stats.get("mean_meters", 0), color="#1f77b4", linestyle="--", label=f"Mean: {stats.get('mean_meters', 0):.1f}m")
        ax.legend(loc="upper left")

        out_path = self.figures_dir / "distance_distribution_nearby_pairs.png"
        fig.savefig(out_path)
        plt.close(fig)
        print(f"Saved figure: {out_path}")

    def generate_all(self):
        """Load JSON summaries and render all figures."""
        eda_file = self.reports_dir / "eda_summary.json"
        prox_file = self.reports_dir / "spatial_proximity_summary.json"
        naming_file = self.reports_dir / "naming_and_transliteration_summary.json"

        if eda_file.exists():
            with open(eda_file) as f:
                eda = json.load(f)
            self.plot_category_distribution(eda)
            self.plot_attribute_completeness(eda)
            self.plot_h3_spatial_density(eda)

        if prox_file.exists():
            with open(prox_file) as f:
                prox = json.load(f)
            self.plot_proximity_candidate_distribution(prox)
            self.plot_distance_histogram(prox)

        if naming_file.exists():
            with open(naming_file) as f:
                naming = json.load(f)
            self.plot_kannada_naming_coverage(naming)
