# Final Repository Inventory & Asset Catalog

**Audit Timestamp:** 2026-11-19T17:00:00Z  
**Total Tracked/Audited Files:** 342  
**Repository Root:** `India_Specific_POI_Conflation`  

## 1. Classification Summary

| Classification Category | File Count | Approximate Size (KB) |
| :--- | :---: | :---: |
| **Documentation** | 93 | 1658.6 KB |
| **Essential production code** | 78 | 603.0 KB |
| **Generated artifacts** | 64 | 386715.2 KB |
| **Supporting code** | 48 | 406.1 KB |
| **Tests** | 26 | 253.7 KB |
| **Historical development material** | 22 | 228.7 KB |
| **Configurations** | 7 | 398.1 KB |
| **Reproducibility assets** | 4 | 195.0 KB |

---

## 2. Exhaustive File-by-File Catalog

| Path | Size | Category | Actively Used | Referenced | Gen | Exec | Test | Repro | Decision |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gitignore` | 1.4 KB | Configurations | YES | 4 refs | NO | YES | YES | YES | **KEEP** |
| `PROJECT_STATE.md` | 67.9 KB | Documentation | YES | 3 refs | NO | YES | YES | YES | **KEEP** |
| `README.md` | 21.6 KB | Documentation | YES | 5 refs | NO | YES | YES | YES | **KEEP** |
| `pyproject.toml` | 676 B | Configurations | YES | 4 refs | NO | YES | YES | YES | **KEEP** |
| `tests/test_ai_assisted_annotation.py` | 17.7 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_auto_adopt_ai_pilot.py` | 24.7 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_benchmark.py` | 16.5 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_benchmark_expansion.py` | 9.4 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_boundary.py` | 1.7 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_candidate_blocking.py` | 7.2 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_canonical_resolution.py` | 11.4 KB | Tests | YES | 3 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_canonical_schema.py` | 3.0 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_categories.py` | 2.4 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_conflation_audit_m16_1.py` | 8.6 KB | Tests | YES | 4 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_conflation_graph.py` | 10.1 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_conflation_quality_m18.py` | 12.1 KB | Tests | YES | 4 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_eda_and_proximity.py` | 3.1 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_evaluation_audit_m15_1.py` | 5.0 KB | Tests | YES | 3 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_h3_indexing.py` | 3.1 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_human_adjudication.py` | 11.7 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_matching_engine.py` | 6.3 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_milestone_13_audit_and_optimization.py` | 12.1 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_pairwise_features.py` | 8.1 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_pipeline_integration.py` | 2.4 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_production_pipeline_audit_m17_1.py` | 18.3 KB | Tests | YES | 4 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_production_pipeline_m17.py` | 22.3 KB | Tests | YES | 8 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_sampling_integrity_m14.py` | 7.5 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_supervised_graph_conflation_m16.py` | 18.3 KB | Tests | YES | 4 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_supervised_matching_m15.py` | 8.7 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `tests/test_validation.py` | 2.2 KB | Tests | YES | 2 refs | NO | NO | YES | YES | **KEEP** |
| `models/supervised_poi_matcher_v1.joblib` | 94.4 KB | Reproducibility assets | YES | 18 refs | YES | YES | YES | YES | **KEEP** |
| `models/supervised_poi_matcher_v1_metadata.json` | 4.3 KB | Reproducibility assets | YES | 5 refs | YES | YES | YES | YES | **KEEP** |
| `models/supervised_rf_poi_matcher_v1.joblib` | 92.8 KB | Reproducibility assets | YES | 4 refs | YES | YES | YES | YES | **KEEP** |
| `models/supervised_rf_poi_matcher_v1.json` | 3.5 KB | Reproducibility assets | YES | 1 refs | YES | YES | YES | YES | **KEEP** |
| `docs/ai_assisted_annotation.md` | 12.6 KB | Documentation | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `docs/annotation_pilot.md` | 5.5 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/annotation_workflow.md` | 3.6 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/benchmark_lifecycle.md` | 2.7 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/benchmark_sampling_methodology.md` | 5.9 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/benchmark_validation.md` | 19.3 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/blocking_strategy_evaluation.md` | 6.0 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/candidate_generation.md` | 9.5 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/canonical_entity_resolution.md` | 7.6 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/conflation_graph.md` | 6.4 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/data_dictionary.md` | 9.6 KB | Documentation | YES | 1 refs | NO | NO | NO | YES | **KEEP** |
| `docs/data_feasibility_report.md` | 23.7 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/eda_report.md` | 10.1 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/graph_conflation_and_entity_resolution.md` | 13.1 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/ground_truth_benchmark.md` | 7.1 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/human_annotation_protocol.md` | 15.7 KB | Documentation | YES | 6 refs | NO | NO | NO | YES | **KEEP** |
| `docs/licensing_and_attribution.md` | 8.5 KB | Documentation | YES | 1 refs | NO | NO | NO | YES | **KEEP** |
| `docs/m10_audit_and_reconciliation.md` | 8.3 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/matching_baseline_evaluation.md` | 9.9 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/missed_match_audit.md` | 5.0 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/multilingual_blocking.md` | 5.3 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/name_and_transliteration_analysis.md` | 7.6 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/pairwise_features.md` | 9.8 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/project_scope.md` | 9.8 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/spatial_indexing.md` | 5.0 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `docs/supervised_matching_system.md` | 12.3 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `configs/bbmp_boundary.geojson` | 388.9 KB | Configurations | YES | 18 refs | NO | YES | YES | YES | **KEEP** |
| `configs/data_sources.yaml` | 1.6 KB | Configurations | YES | 1 refs | NO | YES | YES | YES | **KEEP** |
| `configs/geography.yaml` | 922 B | Configurations | YES | 1 refs | NO | YES | YES | YES | **KEEP** |
| `configs/matching_baseline.yaml` | 2.9 KB | Configurations | YES | 7 refs | NO | YES | YES | YES | **KEEP** |
| `configs/supervised_matching_config.yaml` | 1.8 KB | Configurations | YES | 7 refs | NO | YES | YES | YES | **KEEP** |
| `scripts/acquire_boundary.py` | 867 B | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/acquire_osm.py` | 609 B | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/acquire_overture.py` | 675 B | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/annotate.py` | 19.9 KB | Supporting code | YES | 8 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/assess_benchmark_readiness.py` | 11.2 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/assess_model_readiness.py` | 7.9 KB | Supporting code | YES | 3 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/assess_readiness_final.py` | 11.9 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/assess_readiness_m14.py` | 8.0 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_baseline_evaluation_integrity_m14.py` | 7.3 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_baseline_evaluator.py` | 8.5 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_benchmark_sampling.py` | 8.6 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_conflation_m16_1.py` | 21.9 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_dataset_integrity.py` | 8.5 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_representative_annotations_m14.py` | 5.2 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_sampling_integrity_m14.py` | 9.5 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_second_review_qc_m14.py` | 5.3 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/audit_supervised_evaluation_m15_1.py` | 24.1 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/build_conflation_graph.py` | 10.9 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/build_supervised_training_dataset.py` | 10.3 KB | Supporting code | YES | 3 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/consolidate_operational_benchmark.py` | 15.9 KB | Supporting code | YES | 4 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/design_leakage_safe_split_m14.py` | 7.0 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/evaluate_conflation_quality.py` | 11.6 KB | Supporting code | YES | 6 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/evaluate_matching_baseline.py` | 3.2 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/evaluate_supervised_matcher.py` | 14.0 KB | Supporting code | YES | 3 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/extract_pairwise_features.py` | 3.1 KB | Supporting code | YES | 5 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/generate_ai_suggestions.py` | 4.6 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/generate_final_audit_artifacts.py` | 10.7 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/generate_iaa_final_report.py` | 7.5 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/partition_dataset.py` | 2.6 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/prepare_human_review_queue.py` | 4.8 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/prioritize_review_queue.py` | 883 B | Supporting code | YES | 6 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/reconcile_benchmark_provenance.py` | 10.0 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/resolve_canonical_entities.py` | 13.7 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_batch_inference.py` | 2.1 KB | Supporting code | YES | 3 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_benchmark_setup.py` | 3.0 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_candidate_generation.py` | 6.9 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_eda_analysis.py` | 1.8 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_geospatial_intelligence.py` | 833 B | Supporting code | YES | 6 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_graph_conflation_pipeline.py` | 32.8 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_h3_indexing.py` | 918 B | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_human_adjudication_benchmark.py` | 22.5 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_indic_language_analysis.py` | 832 B | Supporting code | YES | 6 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_ingestion_pipeline.py` | 2.2 KB | Supporting code | YES | 1 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_m18_error_analysis.py` | 10.9 KB | Supporting code | YES | 4 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_matching_baseline.py` | 11.3 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/run_supervised_error_analysis.py` | 13.4 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/train_supervised_matcher.py` | 5.0 KB | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `scripts/transform_canonical.py` | 809 B | Supporting code | YES | 2 refs | NO | OPTIONAL | NO | YES | **KEEP_AND_IMPROVE** |
| `data/processed/canonical_metadata.json` | 337 B | Generated artifacts | YES | 3 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical_pois.parquet` | 25340.9 KB | Generated artifacts | YES | 30 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical_pois_h3.parquet` | 30935.9 KB | Generated artifacts | YES | 38 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical_pois_h3_metadata.json` | 612 B | Generated artifacts | YES | 3 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/adjudication_queue.csv` | 1.8 KB | Generated artifacts | YES | 15 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotation_queue.csv` | 155.3 KB | Generated artifacts | YES | 26 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/benchmark_metadata.json` | 2.9 KB | Generated artifacts | YES | 8 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/missed_match_audit.csv` | 46.7 KB | Generated artifacts | YES | 8 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/pilot_annotations_adopted.csv` | 30.8 KB | Generated artifacts | YES | 10 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/pilot_batch_50.csv` | 15.8 KB | Generated artifacts | YES | 15 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/review_queue_pilot_50.csv` | 16.2 KB | Generated artifacts | YES | 6 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/queue_kannada_expansion.csv` | 12.1 KB | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_challenge_difficulty.csv` | 7.5 KB | Generated artifacts | YES | 1 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_challenge_difficulty.parquet` | 11.9 KB | Generated artifacts | YES | 2 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_consolidated_operational.csv` | 43.9 KB | Generated artifacts | YES | 1 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_consolidated_operational.parquet` | 27.4 KB | Generated artifacts | YES | 2 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_gold_human.csv` | 23.8 KB | Generated artifacts | YES | 1 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_gold_human.parquet` | 18.5 KB | Generated artifacts | YES | 2 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_unreviewed_pool.csv` | 153.7 KB | Generated artifacts | YES | 3 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/evaluation_views/view_unreviewed_pool.parquet` | 81.3 KB | Generated artifacts | YES | 2 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/partitions/test_partition.csv` | 23.8 KB | Generated artifacts | YES | 9 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/partitions/train_partition.csv` | 94.4 KB | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/partitions/validation_partition.csv` | 54.7 KB | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotations/annotations_ai_auto_adopter.csv` | 31.0 KB | Generated artifacts | YES | 7 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotations/annotations_human_reviewer_1.csv` | 24.9 KB | Generated artifacts | YES | 10 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotations/annotations_human_reviewer_2.csv` | 9.6 KB | Generated artifacts | YES | 10 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotations/annotations_reviewer_1.csv` | 764 B | Generated artifacts | YES | 7 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotations/assigned_representative_qc_representative_reviewer_2.csv` | 31.5 KB | Generated artifacts | YES | 13 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/annotations/audit_trail.csv` | 13.8 KB | Generated artifacts | YES | 10 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/operational/operational_benchmark_consolidated.csv` | 62.1 KB | Generated artifacts | YES | 2 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/operational/operational_benchmark_consolidated.parquet` | 37.9 KB | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/operational/operational_benchmark_full_pool.csv` | 254.9 KB | Generated artifacts | YES | 8 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/ai_suggestions/pilot_ai_suggestions.jsonl` | 37.9 KB | Generated artifacts | YES | 8 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/human_verified/benchmark_human_verified_v1.csv` | 25.2 KB | Generated artifacts | YES | 21 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/human_verified/benchmark_human_verified_v1.parquet` | 19.0 KB | Generated artifacts | YES | 7 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/benchmark/adjudicated/adjudication_records.jsonl` | 2.3 KB | Generated artifacts | YES | 8 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical/canonical_pois.geojson` | 87784.8 KB | Generated artifacts | YES | 14 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical/canonical_pois.parquet` | 23924.6 KB | Generated artifacts | YES | 30 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical/conflation_edges.parquet` | 31862.5 KB | Generated artifacts | YES | 14 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical/poi_relationships.parquet` | 137.1 KB | Generated artifacts | YES | 20 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/canonical/unresolved_pairs.parquet` | 219.5 KB | Generated artifacts | YES | 18 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/candidate_pairs/candidate_pairs_union.parquet` | 41033.4 KB | Generated artifacts | YES | 27 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/features/pairwise_features.parquet` | 72088.5 KB | Generated artifacts | YES | 24 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/supervised/test_features.parquet` | 40.0 KB | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/supervised/train_features.parquet` | 89.2 KB | Generated artifacts | YES | 6 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/supervised/validation_features.parquet` | 60.3 KB | Generated artifacts | YES | 7 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/review/prioritized_unresolved_queue.csv` | 1062.5 KB | Generated artifacts | YES | 4 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/review/prioritized_unresolved_queue.parquet` | 381.7 KB | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/processed/predictions/supervised_predictions_universe.parquet` | 11702.6 KB | Generated artifacts | YES | 16 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/raw/osm/bengaluru_bbmp.osm.pbf` | 33769.1 KB | Generated artifacts | YES | 3 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/raw/osm/bengaluru_osm_pois.parquet` | 3936.1 KB | Generated artifacts | YES | 14 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/raw/osm/extraction_metadata.json` | 392 B | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/raw/overture/bengaluru_overture_places.parquet` | 19614.0 KB | Generated artifacts | YES | 14 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `data/raw/overture/extraction_metadata.json` | 549 B | Generated artifacts | YES | 5 refs | YES | YES | YES | YES | **KEEP (GITIGNORE)** |
| `reports/adjudication_summary.json` | 1.9 KB | Documentation | YES | 6 refs | YES | NO | NO | YES | **KEEP** |
| `reports/baseline_error_analysis.json` | 8.8 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/baseline_evaluation.json` | 5.0 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/baseline_evaluation_integrity_m14.json` | 4.8 KB | Historical development material | YES | 6 refs | YES | NO | NO | YES | **KEEP** |
| `reports/baseline_evaluator_audit.json` | 5.3 KB | Documentation | YES | 7 refs | YES | NO | NO | YES | **KEEP** |
| `reports/baseline_v1_final_evaluation.json` | 4.9 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/baseline_v2_experimental_evaluation.json` | 4.9 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/benchmark_metadata.json` | 2.9 KB | Documentation | YES | 8 refs | YES | NO | NO | YES | **KEEP** |
| `reports/benchmark_readiness_assessment.json` | 4.8 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/benchmark_readiness_assessment_final.json` | 4.3 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/benchmark_readiness_assessment_m14.json` | 5.5 KB | Historical development material | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/benchmark_sampling_audit.json` | 6.3 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/benchmark_sampling_report.json` | 3.0 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/blocking_strategy_comparison.json` | 910 B | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/candidate_generation_summary.json` | 1.2 KB | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/candidate_pairs_50m_sample.csv` | 57.4 KB | Documentation | YES | 4 refs | NO | NO | NO | YES | **KEEP** |
| `reports/candidate_review_sample.csv` | 73.8 KB | Documentation | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `reports/canonical_entities_sample.json` | 40.2 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/canonical_entities_summary.json` | 1.9 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/category_pruned_sample.csv` | 25.1 KB | Documentation | YES | 4 refs | NO | NO | NO | YES | **KEEP** |
| `reports/category_pruning_audit_summary.json` | 1.2 KB | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/conflation_graph_clusters_sample.json` | 51.9 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/conflation_graph_report.json` | 1.6 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/dataset_integrity_audit.json` | 6.4 KB | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/eda_summary.json` | 10.2 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/feature_extraction_summary.json` | 599 B | Documentation | YES | 2 refs | YES | NO | NO | YES | **KEEP** |
| `reports/final_architecture_audit.md` | 7.5 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/final_cleanup_plan.md` | 2.8 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/final_cleanup_summary.md` | 4.9 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/final_repository_inventory.md` | 45.0 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/final_system_validation.md` | 6.3 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/graph_ambiguity_report.json` | 683 B | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/human_benchmark_summary.json` | 1.1 KB | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/inference_performance_report.json` | 1.7 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/inter_annotator_agreement.json` | 2.4 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/inter_annotator_agreement_expanded.json` | 4.1 KB | Documentation | YES | 2 refs | YES | NO | NO | YES | **KEEP** |
| `reports/inter_annotator_agreement_final.json` | 3.9 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/leakage_audit_report.json` | 1.0 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/leakage_safe_split_design_m14.json` | 3.8 KB | Historical development material | YES | 7 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m15_1_evaluation_audit.json` | 36.8 KB | Historical development material | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m15_1_independent_evaluation_audit.md` | 20.6 KB | Historical development material | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m16_1_conflation_audit.json` | 17.2 KB | Historical development material | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m16_1_independent_conflation_audit.md` | 14.0 KB | Historical development material | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m16_conflation_summary.json` | 2.4 KB | Historical development material | YES | 6 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m16_conflation_validation_report.md` | 5.3 KB | Historical development material | YES | 5 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m17_1_audit_preflight.md` | 4.3 KB | Historical development material | YES | 1 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m17_1_audit_summary.json` | 1.6 KB | Historical development material | YES | 2 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m17_1_flagged_honorific_pairs.json` | 50.9 KB | Historical development material | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m17_1_independent_audit.md` | 13.6 KB | Historical development material | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m17_architecture_assessment.md` | 12.6 KB | Historical development material | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m17_implementation_report.md` | 10.5 KB | Historical development material | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m17_run_summary.json` | 1.0 KB | Historical development material | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m17_validation_report.json` | 2.3 KB | Historical development material | YES | 2 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m17_validation_report.md` | 7.5 KB | Historical development material | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_benchmark_manifest.json` | 792 B | Documentation | YES | 1 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m18_benchmark_methodology.md` | 6.1 KB | Documentation | YES | 1 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_error_analysis.md` | 7.1 KB | Documentation | YES | 3 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_evaluation_preflight.md` | 11.4 KB | Documentation | YES | 1 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_geospatial_analysis.md` | 6.1 KB | Documentation | YES | 4 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_indic_language_analysis.md` | 4.4 KB | Documentation | YES | 4 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_label_provenance_audit.md` | 5.5 KB | Documentation | YES | 1 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_matching_quality_report.md` | 8.1 KB | Documentation | YES | 4 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_review_queue_analysis.md` | 6.0 KB | Documentation | YES | 4 refs | NO | NO | NO | YES | **KEEP** |
| `reports/m18_run_summary.json` | 2.1 KB | Documentation | YES | 2 refs | YES | NO | NO | YES | **KEEP** |
| `reports/m18_validation_report.md` | 6.0 KB | Documentation | YES | 2 refs | NO | NO | NO | YES | **KEEP** |
| `reports/matching_baseline_report.json` | 2.4 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/matching_sample_explanations.json` | 24.2 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/missed_match_audit_summary.json` | 766 B | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/model_feature_importance.json` | 6.4 KB | Documentation | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/model_readiness_assessment_m15.json` | 3.8 KB | Historical development material | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/naming_and_transliteration_summary.json` | 6.2 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/operational_benchmark_audit.json` | 1.8 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/pilot_ai_suggestions_summary.json` | 1.4 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/pilot_auto_adoption_report.json` | 9.2 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/representative_annotation_status_m14.json` | 3.1 KB | Historical development material | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/representative_benchmark_completion.json` | 3.8 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/representative_benchmark_reconciliation.json` | 56.6 KB | Documentation | YES | 6 refs | YES | NO | NO | YES | **KEEP** |
| `reports/representative_benchmark_summary.json` | 3.3 KB | Documentation | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/review_prioritization_queue.json` | 662.6 KB | Documentation | YES | 9 refs | YES | NO | NO | YES | **KEEP** |
| `reports/rule_engine_error_analysis_v2.json` | 10.3 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/sampling_integrity_audit_m14.json` | 5.1 KB | Historical development material | YES | 7 refs | YES | NO | NO | YES | **KEEP** |
| `reports/second_review_qc_audit_m14.json` | 2.0 KB | Historical development material | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/spatial_proximity_summary.json` | 3.1 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/supervised_dataset_leakage_audit.json` | 3.9 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/supervised_error_analysis.json` | 25.3 KB | Documentation | YES | 5 refs | YES | NO | NO | YES | **KEEP** |
| `reports/supervised_model_evaluation.json` | 38.2 KB | Documentation | YES | 6 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/attribute_completeness_matrix.png` | 250.1 KB | Generated artifacts | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/category_distribution_comparison.png` | 138.0 KB | Generated artifacts | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/cross_source_proximity_candidate_distribution.png` | 233.2 KB | Generated artifacts | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/distance_distribution_nearby_pairs.png` | 119.1 KB | Generated artifacts | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/h3_res8_density_hotspots.png` | 135.3 KB | Generated artifacts | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/kannada_english_naming_coverage.png` | 128.3 KB | Generated artifacts | YES | 3 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/m18_fig1_distance_distributions.png` | 98.4 KB | Generated artifacts | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/m18_fig2_category_coverage.png` | 108.7 KB | Generated artifacts | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/m18_fig3_score_calibration_bands.png` | 81.1 KB | Generated artifacts | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `reports/figures/m18_fig4_h3_density_hotspots.png` | 65.0 KB | Generated artifacts | YES | 4 refs | YES | NO | NO | YES | **KEEP** |
| `src/__init__.py` | 35 B | Documentation | YES | 1 refs | NO | YES | YES | YES | **KEEP** |
| `src/poi_conflation/__init__.py` | 69 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/__init__.py` | 2.1 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/adjudication.py` | 7.7 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/agreement.py` | 9.7 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/ai_analyzer.py` | 19.0 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/ai_schema.py` | 8.8 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/category_audit.py` | 8.7 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/expansion.py` | 8.4 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/metadata.py` | 7.7 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/missed_match.py` | 15.4 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/partitioner.py` | 8.5 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/provenance.py` | 14.9 KB | Essential production code | YES | 5 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/sampling.py` | 13.6 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/schema.py` | 6.9 KB | Essential production code | YES | 6 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/benchmark/workflow.py` | 27.1 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/__init__.py` | 1.0 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/batch_inference.py` | 8.9 KB | Essential production code | YES | 5 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/config.py` | 1.8 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/engine.py` | 9.7 KB | Essential production code | YES | 3 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/engine_v2.py` | 10.4 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/evaluator.py` | 15.9 KB | Essential production code | YES | 11 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/explainability.py` | 8.9 KB | Essential production code | YES | 3 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/normalization.py` | 6.9 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/quality_evaluator.py` | 12.3 KB | Essential production code | YES | 6 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/review_prioritizer.py` | 15.1 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/matching/supervised_model.py` | 11.4 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/delta/__init__.py` | 683 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/delta/detector.py` | 8.1 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/delta/snapshot.py` | 6.1 KB | Essential production code | YES | 3 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/pipeline/__init__.py` | 421 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/pipeline/__main__.py` | 4.1 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/pipeline/config.py` | 2.4 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/pipeline/orchestrator.py` | 29.4 KB | Essential production code | YES | 8 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/ingestion/__init__.py` | 67 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/ingestion/boundary.py` | 2.4 KB | Essential production code | YES | 3 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/ingestion/osm.py` | 10.2 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/ingestion/overture.py` | 4.0 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/__init__.py` | 356 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/eda.py` | 9.5 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/geospatial_intelligence.py` | 19.8 KB | Essential production code | YES | 6 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/indic_language_intelligence.py` | 12.1 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/naming_profiler.py` | 11.4 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/spatial_proximity.py` | 10.3 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/analysis/visualizations.py` | 11.2 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/blocking/__init__.py` | 660 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/blocking/candidate_engine.py` | 20.3 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/blocking/category.py` | 5.5 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/blocking/lexical.py` | 4.6 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/blocking/multilingual.py` | 4.3 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/blocking/spatial.py` | 5.7 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/transformation/__init__.py` | 39 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/transformation/canonical_transformer.py` | 9.0 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/__init__.py` | 1.5 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/category_features.py` | 1.6 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/extractor.py` | 8.0 KB | Essential production code | YES | 4 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/name_features.py` | 3.8 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/schema.py` | 2.6 KB | Essential production code | YES | 6 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/spatial_features.py` | 2.3 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/strategy_features.py` | 1.3 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/features/translit_features.py` | 3.8 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/__init__.py` | 2.0 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/ambiguity_analyzer.py` | 8.3 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/bipartite_graph.py` | 9.6 KB | Essential production code | YES | 3 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/canonical_resolver.py` | 15.3 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/edge_classifier.py` | 2.6 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/safeguards.py` | 20.6 KB | Essential production code | YES | 11 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/schema.py` | 8.5 KB | Essential production code | YES | 6 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/graph/supervised_resolver.py` | 19.1 KB | Essential production code | YES | 5 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/models/__init__.py` | 31 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/models/canonical.py` | 3.0 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/models/categories.py` | 7.3 KB | Essential production code | YES | 2 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/lineage/__init__.py` | 254 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/lineage/ledger.py` | 6.5 KB | Essential production code | YES | 5 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/indexing/__init__.py` | 176 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/indexing/h3_indexer.py` | 6.1 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/validation/__init__.py` | 419 B | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/validation/conflation_validator.py` | 11.7 KB | Essential production code | YES | 6 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
| `src/poi_conflation/validation/validators.py` | 3.8 KB | Essential production code | YES | 1 refs | NO | YES | YES | YES | **KEEP_AND_IMPROVE** |
