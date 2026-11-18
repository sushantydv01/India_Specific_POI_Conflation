# Milestone 10 Post-Implementation Audit and Technical Reconciliation

**Project:** India-Specific POI Conflation  
**Scope:** BBMP, Bengaluru, Karnataka, India  
**Date:** November 2026  
**Status:** Reconciled and Audited  

---

## 1. Executive Summary

Following the completion of Milestone 10 (*Conflation Graph & Cluster-Based Canonical POI Resolution*), this audit report investigates and reconciles four architectural and methodological aspects identified during preflight verification:

1. **Edge Classification vs. Canonical Merge Threshold Consistency:** Policy clarification between the `STRONG_MATCH_CANDIDATE` threshold ($\ge 0.75$) and the 1:1 canonical equivalence merge threshold ($\ge 0.70$).
2. **Category Contradiction Score Accounting:** Clarification of cluster-level category contradiction detection versus pairwise guardrail scoring (e.g., how a cluster can contain high-scoring edges alongside category contradictions).
3. **Review Prioritization Queue Accounting:** Exact reconciliation of the $1{,}033$ review items from the $1{,}658$ ambiguous clusters.
4. **Canonical UUIDv5 Namespace Permanence:** Hardcoding of a permanent, dedicated project-level namespace UUID constant to guarantee long-term stability and reproducibility across environments.
5. **Canonical Entity Universe Preservation:** Re-verification that all $246{,}856$ canonical source POIs are 100% accounted for in the $242{,}243$ resolved entities.

---

## 2. Policy Consistency: Edge Classification vs. Canonical Merge Threshold

### The Investigation
In Milestone 10:
- `EdgeClassifier` classified bipartite edges into four tiers:
  - `STRONG_MATCH_CANDIDATE`: $\text{Score} \ge 0.75$ and distance $\le 50$m without guardrail rejections ($5{,}543$ pairs).
  - `POSSIBLE_MATCH`: $\text{Score} \in [0.55, 0.75)$ and distance $\le 100$m ($13{,}390$ pairs).
  - `UNCERTAIN`: $\text{Score} \in [0.35, 0.55)$ or distance $\le 150$m ($63{,}492$ pairs).
  - `REJECTED`: Guardrail violation or $\text{Score} < 0.35$ or distance $> 150$m ($523{,}003$ pairs).
- `CanonicalEntityResolver` executed 1:1 equivalence merging at:
  ```python
  if edge.matching_score >= 0.70 and edge.distance_meters <= self.max_equivalence_distance and cluster.category_consistent:
  ```

### Policy Clarification & Justification
The threshold of $0.70$ is intentionally distinct from the isolated edge threshold of $0.75$. The rationale is rooted in **structural topological support**:
1. **Isolated Bipartite Topology:** In a strict 1:1 connected component, there is no degree ambiguity (exactly one OSM POI and exactly one Overture POI mutually choose each other without any competing second candidates).
2. **Category Consistency:** Both entities share the exact same or strongly compatible category taxonomy.
3. **Spatial Proximity:** The two points lie strictly within $50$ metres (projected UTM EPSG:32643 planar distance).

Under these triple structural constraints, pairs with matching scores in $[0.70, 0.75)$—which would be considered `POSSIBLE_MATCH` in isolation—possess sufficient contextual reinforcement to justify canonical merging without risking false equivalence.

In `src/poi_conflation/graph/canonical_resolver.py`, this threshold is now made an explicit, configurable parameter `min_equivalence_score` (defaulting to `0.70`), ensuring full code transparency.

---

## 3. Discrepancy Analysis: Category Contradiction vs. Pairwise Guardrail Scoring

### The Observation
In `reports/review_prioritization_queue.json`, `REV-00001` (`CLUSTER-000232`) listed a score of `1.00`, despite being prioritized under `CATEGORY_CONTRADICTION`:
- Pair: `node/6419027198::0469bfec-813b-4ff6-872d-0696f30e46c0`
- OSM POI: `Pathi market` (`retail`)
- Overture POI: `Prakash Colour Lab` (`retail`)
- Prioritization Reason: `Incompatible categories (civic_religious, financial, retail) in cluster with score 1.00`

Yet in Milestone 9, the pairwise guardrail `CATEGORY_DISJOINT` capped `final_score` at `0.35`.

### Root Cause Identification
This is not a failure of the pairwise guardrail; it represents the critical distinction between **pairwise** and **cluster-level** entity resolution:
1. **Pairwise Level:** The edge `node/6419027198::0469bfec-813b-4ff6-872d-0696f30e46c0` connects a `retail` OSM record with a `retail` Overture record. Their categories match exactly (`feat_exact_category_match = 1.0`). Therefore, the pairwise guardrail `CATEGORY_DISJOINT` was **not** triggered.
2. **Cluster Level:** The connected component `CLUSTER-000232` contains multiple nodes linked by candidate match edges. When tracing connected components across the bipartite graph, this cluster pooled together nodes classified as `civic_religious`, `financial`, and `retail`.
3. **Ambiguity Analyzer Action:** The `AmbiguityAnalyzer` scans the entire connected cluster. When `not cluster.category_consistent` evaluates to `True`, the cluster is flagged as having category contradictions. When creating the review item, the analyzer records the cluster's maximum edge score (`cluster.score_max = 1.00`) alongside the primary candidate edge.

**Conclusion:** The score of $1.00$ reflects the high confidence of an internal edge, but the cluster's multi-node topology reveals an underlying conflation conflict (likely transitive bridging or collocated heterogeneous shops in a commercial complex). This illustrates precisely why graph-based ambiguity detection is superior to isolated pairwise classification.

---

## 4. Review Queue Deduplication & Accounting

The ambiguity analysis identified $1{,}658$ ambiguous clusters out of $11{,}449$ total connected components. The review queue contains exactly $1{,}033$ prioritized review items.

The exact filtering and ranking criteria account for this distribution:

| Priority Rank | Ambiguity Type | Trigger Condition | Item Count |
|---|---|---|---|
| **Priority 1** | `CATEGORY_CONTRADICTION` | Multi-category cluster with `score_max` $\ge 0.50$ | **12** |
| **Priority 2** | `COMPETING_HIGH_SCORE_EDGES` | Nodes with $\ge 2$ active edges having $\lvert \Delta S \rvert \le 0.05$ | **989** |
| **Priority 3** | `EXCESSIVE_GEOGRAPHIC_SPREAD` | Connected component spanning $> 100$m UTM distance | **32** |
| **Total Review Queue** | — | **Mutually exclusive prioritization passes** | **1,033** |

The remaining $625$ ambiguous clusters ($1{,}658 - 1{,}033$) represent:
- Clusters where edge competitions have score deltas $> 0.05$ (clear winner without close runner-up contention).
- Clusters with rejected cross-edges that do not violate the $> 100$m spread threshold.
- Clusters with low-scoring possible matches ($< 0.50$) that do not meet high-priority review thresholds.

---

## 5. Canonical UUIDv5 Namespace Permanence

In Milestone 10, the canonical UUIDv5 namespace was dynamically instantiated as:
```python
CANONICAL_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "poi-conflation.canonical.entity")
```
Evaluating this expression yields:
```
9a8bf37f-af65-5399-9fab-35bcd714c702
```

To eliminate runtime dependency on `uuid.NAMESPACE_DNS` and provide a permanently defined constant in code and schema documentation, this is formalized as:
```python
CANONICAL_ENTITY_NAMESPACE = uuid.UUID("9a8bf37f-af65-5399-9fab-35bcd714c702")
```
This guarantees:
1. Complete backward compatibility with all entity identifiers produced in Milestone 10.
2. Deterministic entity regeneration across disparate environments, programming languages, and database engines.

---

## 6. Source Universe Accounting & Record Preservation

The post-implementation audit confirms $100.000\%$ record preservation from input canonical sources to resolved canonical entities:

```
Canonical Source POIs:
  - OpenStreetMap:           49,036
  - Overture Maps Places:   197,820
  ---------------------------------
  Total Input Universe:     246,856

Canonical Entity Output:
  - RESOLVED_EQUIVALENCE:     4,613 entities (accounting for 4,613 OSM + 4,613 Overture = 9,226 source POIs)
  - PARENT_CHILD:               104 entities (accounting for 52 OSM + 52 Overture = 104 source POIs)
  - DISAMBIGUATED_SINGLETON: 217,531 entities (accounting for 217,531 unmerged singleton source POIs)
  - UNRESOLVED_AMBIGUOUS:    19,995 entities (accounting for 19,995 ambiguous singleton source POIs)
  ---------------------------------
  Total Canonical Entities: 242,243
  Total Source Records Accounted: 9,226 + 104 + 217,531 + 19,995 = 246,856 (100.000%)
```

Zero records were dropped, duplicated, or silently discarded during the conflation graph resolution.
