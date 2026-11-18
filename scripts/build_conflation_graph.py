#!/usr/bin/env python3
"""CLI script for constructing the bipartite POI conflation graph.

Loads canonical source POIs and pairwise features, classifies candidate edges into
topological tiers, discovers connected components, evaluates structural patterns,
and persists machine-readable graph reports.
"""

import argparse
import json
import logging
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
from src.poi_conflation.matching.engine import ExplainableMatchingEngine
from src.poi_conflation.graph.schema import (
    GRAPH_SCHEMA_VERSION,
    GraphNode,
    GraphEdge,
    EntityCluster,
)
from src.poi_conflation.graph.edge_classifier import EdgeClassifier
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("build_conflation_graph")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Construct bipartite POI conflation graph and discover entity clusters."
    )
    parser.add_argument(
        "--canonical-pois",
        default="data/processed/canonical_pois_h3.parquet",
        help="Path to spatially indexed canonical POIs Parquet file.",
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
        default="reports/conflation_graph_report.json",
        help="Path for graph summary report JSON.",
    )
    parser.add_argument(
        "--clusters-sample",
        default="reports/conflation_graph_clusters_sample.json",
        help="Path for representative cluster samples JSON.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Batch size for memory-bounded streaming edge processing.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    start_time = time.time()

    logger.info("Initializing Bipartite Conflation Graph...")
    config = MatchingConfig.load(args.config)
    engine = ExplainableMatchingEngine(config=config)
    classifier = EdgeClassifier()
    graph = BipartiteConflationGraph()

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")

    # 1. Load canonical POI nodes
    logger.info(f"Loading canonical POI nodes from {args.canonical_pois}...")
    t_nodes = time.time()
    nodes_raw = con.execute(f"""
        SELECT 
            source_record_id,
            poi_source,
            name_original,
            name_normalized,
            category_normalized,
            latitude,
            longitude,
            ST_X(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_x,
            ST_Y(ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:32643')) as utm_y
        FROM '{args.canonical_pois}'
    """).fetchall()

    for r in nodes_raw:
        graph.add_node(
            GraphNode(
                node_id=r[0],
                source=r[1],
                source_record_id=r[0],
                name=r[2] or "",
                normalized_name=r[3] or "",
                category=r[4] or "",
                latitude=r[5],
                longitude=r[6],
                utm_x=r[7],
                utm_y=r[8],
            )
        )
    logger.info(f"Loaded {len(graph.nodes):,} nodes in {time.time() - t_nodes:.2f}s (OSM: {graph.osm_nodes_count:,}, Overture: {graph.overture_nodes_count:,})")

    # 2. Stream and classify candidate edges
    logger.info(f"Streaming and classifying candidate edges from {args.features}...")
    t_edges = time.time()
    rel = con.execute(f"SELECT * FROM '{args.features}'")
    cols = [d[0] for d in rel.description]

    edge_count = 0
    while True:
        rows = rel.fetchmany(args.batch_size)
        if not rows:
            break
        dicts = [dict(zip(cols, r)) for r in rows]
        for d in dicts:
            eval_res = engine.evaluate_pair(d)
            score = eval_res["final_score"]
            dec = eval_res["decision"]
            guards = eval_res["applied_guardrails"]
            cls = classifier.classify_edge(score, dec, guards, d)

            edge = GraphEdge(
                pair_id=d["candidate_pair_id"],
                osm_source_id=d["osm_source_id"],
                ov_source_id=d["ov_source_id"],
                matching_score=score,
                matching_decision=dec,
                classification=cls,
                distance_meters=d.get("feat_distance_meters", 0.0),
                name_similarity=d.get("feat_token_sort_ratio", 0.0),
                guardrails=guards,
                positive_evidence=eval_res.get("positive_evidence", []),
                negative_evidence=eval_res.get("negative_evidence", []),
            )
            graph.add_edge(edge)
            edge_count += 1

    con.close()
    logger.info(f"Loaded and classified {edge_count:,} edges in {time.time() - t_edges:.2f}s")
    class_counts = graph.get_edge_classification_counts()
    for c_name, c_cnt in class_counts.items():
        logger.info(f"  {c_name}: {c_cnt:,} ({c_cnt / edge_count * 100:.2f}%)")

    # 3. Discover connected components
    logger.info("Discovering connected components across candidate match edges...")
    t_comp = time.time()
    clusters = graph.find_connected_components(active_only=True)
    logger.info(f"Discovered {len(clusters):,} connected clusters in {time.time() - t_comp:.2f}s")

    # 4. Pattern and size distributions
    pattern_counts: Dict[str, int] = {}
    cluster_sizes = []
    spreads = []
    for c in clusters:
        pattern_counts[c.pattern.value] = pattern_counts.get(c.pattern.value, 0) + 1
        cluster_sizes.append(c.total_nodes)
        spreads.append(c.geographic_spread_meters)

    # Isolated nodes accounting
    connected_osm_nodes = set()
    connected_ov_nodes = set()
    for c in clusters:
        connected_osm_nodes.update(c.osm_node_ids)
        connected_ov_nodes.update(c.ov_node_ids)

    total_osm = graph.osm_nodes_count
    total_ov = graph.overture_nodes_count
    isolated_osm = total_osm - len(connected_osm_nodes)
    isolated_ov = total_ov - len(connected_ov_nodes)

    elapsed_sec = time.time() - start_time
    peak_mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

    # Construct representative sample clusters
    sample_clusters = []
    sample_patterns = set()
    for c in clusters:
        if c.pattern.value not in sample_patterns or len(sample_clusters) < 25:
            sample_patterns.add(c.pattern.value)
            c_dict = c.to_dict()
            c_dict["osm_details"] = [
                {"id": nid, "name": graph.nodes[nid].name, "category": graph.nodes[nid].category}
                for nid in c.osm_node_ids[:5]
            ]
            c_dict["ov_details"] = [
                {"id": nid, "name": graph.nodes[nid].name, "category": graph.nodes[nid].category}
                for nid in c.ov_node_ids[:5]
            ]
            sample_clusters.append(c_dict)

    # Save sample clusters JSON
    samples_path = Path(args.clusters_sample)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    with open(samples_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": GRAPH_SCHEMA_VERSION,
                "sample_count": len(sample_clusters),
                "clusters": sample_clusters,
            },
            f,
            indent=2,
        )

    # Construct report
    report = {
        "metadata": {
            "graph_schema_version": GRAPH_SCHEMA_VERSION,
            "policy_version": config.model_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "study_area": "BBMP Bengaluru, Karnataka, India",
        },
        "universe_summary": {
            "total_canonical_pois": len(graph.nodes),
            "osm_nodes_total": total_osm,
            "overture_nodes_total": total_ov,
            "total_candidate_edges": edge_count,
            "execution_time_seconds": round(elapsed_sec, 2),
            "peak_memory_mb": round(peak_mem_mb, 2),
        },
        "edge_classification_distribution": class_counts,
        "node_connectivity": {
            "osm_nodes_in_active_clusters": len(connected_osm_nodes),
            "osm_nodes_isolated": isolated_osm,
            "overture_nodes_in_active_clusters": len(connected_ov_nodes),
            "overture_nodes_isolated": isolated_ov,
        },
        "cluster_summary": {
            "total_active_clusters": len(clusters),
            "structural_patterns": pattern_counts,
            "cluster_size_stats": {
                "min": min(cluster_sizes) if cluster_sizes else 0,
                "max": max(cluster_sizes) if cluster_sizes else 0,
                "mean": round(sum(cluster_sizes) / len(cluster_sizes), 2) if cluster_sizes else 0,
            },
            "geographic_spread_stats_meters": {
                "min": round(min(spreads), 2) if spreads else 0,
                "max": round(max(spreads), 2) if spreads else 0,
                "mean": round(sum(spreads) / len(spreads), 2) if spreads else 0,
            },
            "ambiguous_cluster_count": sum(1 for c in clusters if c.is_ambiguous),
        },
        "methodological_safeguards": [
            "Candidate equivalence components are constructed from active match edges (STRONG + POSSIBLE), not the full Cartesian candidate list, preventing whole-city transitive collapse.",
            "All REJECTED and UNCERTAIN edges are preserved in graph adjacency for conflict and competing-edge detection.",
            "No entities are merged merely due to shared building footprint or identical brand names."
        ],
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Graph construction completed successfully:")
    logger.info(f"  Total clusters: {len(clusters):,}")
    logger.info(f"  1:1 clusters: {pattern_counts.get('ONE_TO_ONE', 0):,}")
    logger.info(f"  1:N clusters: {pattern_counts.get('ONE_TO_MANY', 0):,}")
    logger.info(f"  N:1 clusters: {pattern_counts.get('MANY_TO_ONE', 0):,}")
    logger.info(f"  N:M clusters: {pattern_counts.get('MANY_TO_MANY', 0):,}")
    logger.info(f"  Ambiguous clusters: {pattern_counts.get('AMBIGUOUS_CLUSTER', 0):,}")
    logger.info(f"  Report written to: {args.report}")
    logger.info(f"  Sample clusters written to: {args.clusters_sample}")


if __name__ == "__main__":
    main()
