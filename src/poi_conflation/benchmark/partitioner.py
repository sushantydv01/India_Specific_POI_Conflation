"""Component-blocked and spatially isolated dataset partitioner for POI conflation.

Implements graph connected component clustering precedence with spatial H3 resolution 7 grouping
to prevent optimistic data leakage across Training, Validation, and Test sets.

Guarantees:
1. Component Isolation: No bipartite connected component appears in more than one partition.
2. Node Disjointness: No OSM node or Overture node is shared between train, validation, or test.
3. Spatial Separation: Spatial clusters are anchored via H3 Resolution 7 hexagonal cells (~1.2 km radius).
"""

import csv
import hashlib
import json
import logging
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
import h3

logger = logging.getLogger("dataset_partitioner")


class ComponentBlockedPartitioner:
    """Partitions POI candidate pairs into leakage-safe Train, Validation, and Test sets."""

    def __init__(
        self,
        h3_resolution: int = 7,
        train_ratio: float = 0.60,
        val_ratio: float = 0.20,
        test_ratio: float = 0.20,
        seed: int = 42,
    ):
        assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-6, "Ratios must sum to 1.0"
        self.h3_resolution = h3_resolution
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

    def _build_connected_components(
        self,
        pairs: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, int], Dict[int, List[Dict[str, Any]]]]:
        """Compute bipartite connected components (transitive closures) over candidate pairs."""
        # Adjacency list: node -> set of pair indices
        node_to_pairs = defaultdict(set)
        for idx, p in enumerate(pairs):
            osm_id = p["osm_source_id"]
            ov_id = p["ov_source_id"]
            node_to_pairs[osm_id].add(idx)
            node_to_pairs[ov_id].add(idx)

        # BFS / DFS to find connected components of pair indices
        visited_pairs: Set[int] = set()
        component_map: Dict[str, int] = {}  # pair_id -> comp_id
        components: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        comp_counter = 0

        for idx, p in enumerate(pairs):
            if idx in visited_pairs:
                continue

            comp_counter += 1
            queue = [idx]
            visited_pairs.add(idx)

            while queue:
                curr_idx = queue.pop(0)
                curr_pair = pairs[curr_idx]
                pid = curr_pair["pair_id"]
                component_map[pid] = comp_counter
                components[comp_counter].append(curr_pair)

                # Expand to all pairs sharing either OSM or Overture node
                osm_id = curr_pair["osm_source_id"]
                ov_id = curr_pair["ov_source_id"]
                neighbor_pair_indices = node_to_pairs[osm_id] | node_to_pairs[ov_id]

                for n_idx in neighbor_pair_indices:
                    if n_idx not in visited_pairs:
                        visited_pairs.add(n_idx)
                        queue.append(n_idx)

        return component_map, components

    def _assign_component_to_split(
        self,
        comp_pairs: List[Dict[str, Any]]
    ) -> Tuple[str, str]:
        """Assign an entire connected component to a split via its spatial H3-7 anchor."""
        # Compute centroid coordinates across all pairs in the component
        lats = []
        lons = []
        for p in comp_pairs:
            lats.append(float(p["osm_latitude"]))
            lons.append(float(p["osm_longitude"]))
            lats.append(float(p["ov_latitude"]))
            lons.append(float(p["ov_longitude"]))

        mean_lat = sum(lats) / len(lats)
        mean_lon = sum(lons) / len(lons)

        h3_cell = h3.latlng_to_cell(mean_lat, mean_lon, self.h3_resolution)

        # Hash cell + seed to get deterministic uniform bucket [0, 1)
        h = hashlib.sha256(f"{h3_cell}::{self.seed}".encode()).hexdigest()
        hash_val = int(h[:8], 16) / 0xFFFFFFFF

        if hash_val < self.train_ratio:
            split = "TRAIN"
        elif hash_val < (self.train_ratio + self.val_ratio):
            split = "VALIDATION"
        else:
            split = "TEST"

        return split, h3_cell

    def partition(
        self,
        pairs: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        """Execute component-blocked spatial partitioning and return partitioned pairs & audit."""
        component_map, components = self._build_connected_components(pairs)

        split_pairs: Dict[str, List[Dict[str, Any]]] = {
            "TRAIN": [],
            "VALIDATION": [],
            "TEST": [],
        }

        component_split_assignment: Dict[int, str] = {}
        component_h3_assignment: Dict[int, str] = {}

        for comp_id, comp_items in components.items():
            split, h3_cell = self._assign_component_to_split(comp_items)
            component_split_assignment[comp_id] = split
            component_h3_assignment[comp_id] = h3_cell

            for item in comp_items:
                item_with_split = dict(item)
                item_with_split["partition_split"] = split
                item_with_split["graph_component_id"] = f"COMP-{comp_id:05d}"
                item_with_split["h3_spatial_anchor_res7"] = h3_cell
                split_pairs[split].append(item_with_split)

        # Audit Leakage: ensure zero components and zero nodes cross splits
        train_osm = set(p["osm_source_id"] for p in split_pairs["TRAIN"])
        val_osm = set(p["osm_source_id"] for p in split_pairs["VALIDATION"])
        test_osm = set(p["osm_source_id"] for p in split_pairs["TEST"])

        train_ov = set(p["ov_source_id"] for p in split_pairs["TRAIN"])
        val_ov = set(p["ov_source_id"] for p in split_pairs["VALIDATION"])
        test_ov = set(p["ov_source_id"] for p in split_pairs["TEST"])

        leakage_osm = (train_osm & val_osm) | (train_osm & test_osm) | (val_osm & test_osm)
        leakage_ov = (train_ov & val_ov) | (train_ov & test_ov) | (val_ov & test_ov)

        comp_train = set(p["graph_component_id"] for p in split_pairs["TRAIN"])
        comp_val = set(p["graph_component_id"] for p in split_pairs["VALIDATION"])
        comp_test = set(p["graph_component_id"] for p in split_pairs["TEST"])

        leakage_comps = (comp_train & comp_val) | (comp_train & comp_test) | (comp_val & comp_test)

        audit_report = {
            "partitioning_metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_pairs": len(pairs),
                "total_connected_components": len(components),
                "h3_resolution": self.h3_resolution,
                "target_ratios": {"TRAIN": self.train_ratio, "VALIDATION": self.val_ratio, "TEST": self.test_ratio},
                "random_seed": self.seed,
            },
            "split_distribution": {
                "TRAIN": {
                    "pair_count": len(split_pairs["TRAIN"]),
                    "pair_percentage": round(len(split_pairs["TRAIN"]) / max(1, len(pairs)) * 100.0, 2),
                    "component_count": len(comp_train),
                    "unique_osm_nodes": len(train_osm),
                    "unique_ov_nodes": len(train_ov),
                },
                "VALIDATION": {
                    "pair_count": len(split_pairs["VALIDATION"]),
                    "pair_percentage": round(len(split_pairs["VALIDATION"]) / max(1, len(pairs)) * 100.0, 2),
                    "component_count": len(comp_val),
                    "unique_osm_nodes": len(val_osm),
                    "unique_ov_nodes": len(val_ov),
                },
                "TEST": {
                    "pair_count": len(split_pairs["TEST"]),
                    "pair_percentage": round(len(split_pairs["TEST"]) / max(1, len(pairs)) * 100.0, 2),
                    "component_count": len(comp_test),
                    "unique_osm_nodes": len(test_osm),
                    "unique_ov_nodes": len(test_ov),
                    "status": "FROZEN",
                },
            },
            "leakage_verification": {
                "cross_split_connected_components_leakage_count": len(leakage_comps),
                "cross_split_osm_nodes_leakage_count": len(leakage_osm),
                "cross_split_ov_nodes_leakage_count": len(leakage_ov),
                "is_strictly_leakage_free": (len(leakage_comps) == 0 and len(leakage_osm) == 0 and len(leakage_ov) == 0),
            },
        }

        return split_pairs, audit_report
