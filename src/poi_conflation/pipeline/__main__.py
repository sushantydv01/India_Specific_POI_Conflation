"""CLI entry point for the production POI conflation pipeline."""

import argparse
import logging
from pathlib import Path
import sys

from src.poi_conflation.pipeline.config import PipelineConfig, PipelineMode
from src.poi_conflation.pipeline.orchestrator import ProductionPipelineOrchestrator
from src.poi_conflation.validation.conflation_validator import (
    ContinuousConflationValidator,
    ValidationStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("conflation_pipeline_cli")


def main():
    parser = argparse.ArgumentParser(
        description="Production POI Conflation Pipeline CLI",
        prog="python -m src.poi_conflation.pipeline",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Pipeline subcommand")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run POI conflation pipeline")
    run_parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="Pipeline execution mode (default: full)",
    )
    run_parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional custom identifier for the pipeline run",
    )
    run_parser.add_argument(
        "--production-dir",
        type=Path,
        default=Path("data/processed/canonical"),
        help="Directory to publish validated production datasets",
    )
    run_parser.add_argument(
        "--staging-dir",
        type=Path,
        default=Path("data/processed/staging"),
        help="Directory for temporary staged run outputs",
    )
    run_parser.add_argument(
        "--match-threshold",
        type=float,
        default=0.55,
        help="Supervised model match threshold (default: 0.55)",
    )
    run_parser.add_argument(
        "--disable-honorific-safeguard",
        action="store_true",
        help="Disable the SHARED_HONORIFIC_DISJOINT_BRAND safeguard",
    )

    # Command: validate
    val_parser = subparsers.add_parser("validate", help="Validate existing production conflation outputs")
    val_parser.add_argument(
        "--canonical-pois",
        type=Path,
        default=Path("data/processed/canonical/canonical_pois.parquet"),
        help="Path to canonical POIs Parquet file",
    )
    val_parser.add_argument(
        "--poi-relationships",
        type=Path,
        default=Path("data/processed/canonical/poi_relationships.parquet"),
        help="Path to POI relationships Parquet file",
    )
    val_parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("reports/m17_validation_report.json"),
        help="Path to output validation JSON report",
    )

    args = parser.parse_args()

    if args.subcommand == "run":
        mode = PipelineMode.FULL if args.mode == "full" else PipelineMode.INCREMENTAL
        config = PipelineConfig(
            mode=mode,
            run_id=args.run_id,
            production_dir=args.production_dir,
            staging_dir=args.staging_dir,
            match_threshold=args.match_threshold,
            enable_honorific_safeguard=not args.disable_honorific_safeguard,
        )
        orchestrator = ProductionPipelineOrchestrator(config)
        manifest = orchestrator.run()
        logger.info(f"Pipeline finished with status: {manifest.status} (Manifest: reports/m17_run_manifest_{manifest.run_id}.json)")
        if manifest.status != "SUCCESS":
            sys.exit(1)

    elif args.subcommand == "validate":
        validator = ContinuousConflationValidator()
        report = validator.validate_production_outputs(
            canonical_pois_path=args.canonical_pois,
            poi_relationships_path=args.poi_relationships,
            run_id="manual_validation",
        )
        report.save(args.report_out)
        logger.info(f"Validation completed. Status: {report.overall_status.value}. Checks passed: {report.passed_count}/{report.total_checks}")
        if report.overall_status == ValidationStatus.FAILED:
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
