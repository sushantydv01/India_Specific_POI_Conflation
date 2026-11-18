#!/usr/bin/env python3
"""CLI script for conservative canonical POI resolution and conflict ambiguity analysis.

Processes the bipartite conflation graph to resolve canonical entities,
isolates parent-child relationships, detects structural ambiguities,
and builds a prioritized human review queue.
"""

import argparse
import json
import logging
import os
import resource
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Set
from collections import defaultdict
import duckdb

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.poi_conflation.matching.config import MatchingConfig
from src.poi_conflation.matching.engine import ExplainableMatchingEngine
from src.poi_conflation.graph.schema import (
    GRAPH_SCHEMA_VERSION,
    CANONICAL_RESOLUTION_POLICY_VERSION,
    GraphNode,
    GraphEdge,
    CanonicalEntity,
    CanonicalResolutionDecision,
    PrioritizedReviewItem,
)
from src.poi_conflation.graph.edge_classifier import EdgeClassifier
from src.poi_conflation.graph.bipartite_graph import BipartiteConflationGraph
from src.poi_conflation.graph.canonical_resolver import (
    CanonicalEntityResolver,
    generate_canonical_uuid,
)
from src.poi_conflation.graph.ambiguity_analyzer import AmbiguityAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("resolve_canonical_entities")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute conservative canonical POI resolution and ambiguity analysis."
    )
    parser.add_argument(
        "--canonical-pois",
        default="data/processed/canonical_pois_h3.parquet",
        help="Path to canonical POIs Parquet file.",
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
        "--summary-report",
        default="reports/canonical_entities_summary.json",
        help="Path for canonical entity resolution summary report JSON.",
    )
    parser.add_argument(
        "--ambiguity-report",
        default="reports/graph_ambiguity_report.json",
        help="Path for graph ambiguity and conflict report JSON.",
    )
    parser.add_argument(
        "--review-queue",
        default="reports/review_prioritization_queue.json",
        help="Path for prioritized human review queue JSON.",
    )
    parser.add_argument(
        "--samples",
        default="reports/canonical_entities_sample.json",
        help="Path for representative canonical entity samples JSON.",
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

    logger.info("Initializing Canonical Entity Resolution Pipeline...")
    config = MatchingConfig.load(args.config)
    engine = ExplainableMatchingEngine(config=config)
    classifier = EdgeClassifier()
    graph = BipartiteConflationGraph()
    resolver = CanonicalEntityResolver()
    ambiguity_analyzer = AmbiguityAnalyzer()

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")

    # 1. Load canonical POI nodes
    logger.info(f"Loading canonical POIs from {args.canonical_pois}...")
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

    # 2. Stream and classify candidate edges
    logger.info(f"Streaming candidate edges from {args.features}...")
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

    # 3. Discover connected components
    logger.info("Discovering connected components across candidate match edges...")
    clusters = graph.find_connected_components(active_only=True)
    logger.info(f"Discovered {len(clusters):,} entity clusters")

    # 4. Resolve canonical entities from clusters
    logger.info("Executing conservative canonical entity resolution across clusters...")
    t_res = time.time()
    canonical_entities: List[CanonicalEntity] = []
    clustered_node_ids: Set[str] = set()

    decision_counts: Dict[str, int] = {
        CanonicalResolutionDecision.RESOLVED_EQUIVALENCE.value: 0,
        CanonicalResolutionDecision.PARENT_CHILD.value: 0,
        CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON.value: 0,
        CanonicalResolutionDecision.UNRESOLVED_AMBIGUOUS.value: 0,
    }

    for cluster in clusters:
        clustered_node_ids.update(cluster.osm_node_ids)
        clustered_node_ids.update(cluster.ov_node_ids)

        resolved_ents = resolver.resolve_cluster(cluster, graph.nodes, graph.edges)
        for ent in resolved_ents:
            canonical_entities.append(ent)
            decision_counts[ent.resolution_decision.value] += 1

    # 5. Account for all isolated / unclustered source POIs as singletons
    logger.info("Accounting for isolated and unclustered source POIs as singletons...")
    isolated_osm_count = 0
    isolated_ov_count = 0
    for node_id, node in graph.nodes.items():
        if node_id not in clustered_node_ids:
            singleton = resolver._create_singleton(node)
            canonical_entities.append(singleton)
            decision_counts[CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON.value] += 1
            if node.source == "OSM":
                isolated_osm_count += 1
            else:
                isolated_ov_count += 1

    logger.info(f"Resolved {len(canonical_entities):,} total canonical entities in {time.time() - t_res:.2f}s")
    for d_name, d_cnt in decision_counts.items():
        logger.info(f"  {d_name}: {d_cnt:,}")

    # 6. Analyze conflicts and ambiguities
    logger.info("Analyzing structural graph conflicts and building human review queue...")
    ambiguity_report, review_queue = ambiguity_analyzer.analyze_conflicts(clusters, graph.nodes, graph.edges)
    logger.info(f"Queued {len(review_queue):,} items for prioritized human review")

    elapsed_sec = time.time() - start_time
    peak_mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)

    # 7. Collect representative canonical entity samples
    samples_by_decision: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ent in canonical_entities:
        dec_val = ent.resolution_decision.value
        if len(samples_by_decision[dec_val]) < 10:
            samples_by_decision[dec_val].append(ent.to_dict())

    samples_flat = []
    for dec_val, s_list in samples_by_decision.items():
        samples_flat.extend(s_list)

    samples_path = Path(args.samples)
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    with open(samples_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": GRAPH_SCHEMA_VERSION,
                "policy_version": CANONICAL_RESOLUTION_POLICY_VERSION,
                "sample_count": len(samples_flat),
                "samples": samples_flat,
            },
            f,
            indent=2,
        )

    # 8. Save canonical entities summary report
    summary = {
        "metadata": {
            "canonical_schema_version": GRAPH_SCHEMA_VERSION,
            "resolution_policy_version": CANONICAL_RESOLUTION_POLICY_VERSION,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "study_area": "BBMP Bengaluru, Karnataka, India",
        },
        "universe_accounting": {
            "total_input_canonical_pois": len(graph.nodes),
            "osm_source_records": graph.osm_nodes_count,
            "overture_source_records": graph.overture_nodes_count,
            "total_candidate_edges": edge_count,
            "total_output_canonical_entities": len(canonical_entities),
            "execution_time_seconds": round(elapsed_sec, 2),
            "peak_memory_mb": round(peak_mem_mb, 2),
        },
        "resolution_decision_distribution": decision_counts,
        "singleton_accounting": {
            "total_singletons": decision_counts[CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON.value],
            "isolated_osm_singletons": isolated_osm_count,
            "isolated_overture_singletons": isolated_ov_count,
            "clustered_disambiguated_singletons": (
                decision_counts[CanonicalResolutionDecision.DISAMBIGUATED_SINGLETON.value]
                - isolated_osm_count
                - isolated_ov_count
            ),
        },
        "resolved_equivalence_metrics": {
            "total_merged_entities": decision_counts[CanonicalResolutionDecision.RESOLVED_EQUIVALENCE.value],
            "source_osm_records_conflated": sum(len(e.contributing_osm_ids) for e in canonical_entities if e.resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE),
            "source_overture_records_conflated": sum(len(e.contributing_ov_ids) for e in canonical_entities if e.resolution_decision == CanonicalResolutionDecision.RESOLVED_EQUIVALENCE),
        },
        "parent_child_metrics": {
            "total_parent_child_entities": decision_counts[CanonicalResolutionDecision.PARENT_CHILD.value],
        },
        "unresolved_ambiguity_metrics": {
            "total_unresolved_entities": decision_counts[CanonicalResolutionDecision.UNRESOLVED_AMBIGUOUS.value],
        },
        "resolution_policies": [
            "1:1 clean equivalence requires score >= 0.70, distance <= 50m, and mutually compatible categories.",
            "Star clusters (1:N, N:1) require score >= 0.75 and margin >= 0.25 over runner-up to resolve dominant match; runners-up remain distinct singletons.",
            "Parent-child relationships (shopping malls, hospitals, commercial plazas) are isolated from identity equivalence.",
            "All multi-node clusters with category contradictions, excessive spread (>100m), or close competing scores are conservatively preserved as UNRESOLVED_AMBIGUOUS without premature merging.",
            "100% of input source POIs are fully preserved in canonical entities with complete provenance."
        ],
    }

    summary_path = Path(args.summary_report)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # 9. Save ambiguity report
    amb_path = Path(args.ambiguity_report)
    amb_path.parent.mkdir(parents=True, exist_ok=True)
    with open(amb_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "schema_version": GRAPH_SCHEMA_VERSION,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                "ambiguity_analysis": ambiguity_report,
            },
            f,
            indent=2,
        )

    # 10. Save prioritized review queue
    rq_path = Path(args.review_queue)
    rq_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rq_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": GRAPH_SCHEMA_VERSION,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_items_in_queue": len(review_queue),
                "items": [item.to_dict() for item in review_queue],
            },
            f,
            indent=2,
        )

    logger.info("Canonical entity resolution and ambiguity analysis complete:")
    logger.info(f"  Summary report: {args.summary_report}")
    logger.info(f"  Ambiguity report: {args.ambiguity_report}")
    logger.info(f"  Review queue: {args.review_queue}")
    logger.info(f"  Entity samples: {args.samples}")


if __name__ == "__main__":
    main()
