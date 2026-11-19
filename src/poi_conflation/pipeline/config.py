"""Configuration models and defaults for the production POI conflation pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List


class PipelineMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


@dataclass
class PipelineConfig:
    """Configuration options for production conflation runs."""
    mode: PipelineMode = PipelineMode.FULL
    run_id: Optional[str] = None
    
    # Input paths
    osm_source_path: Path = Path("data/raw/osm/bengaluru_osm_pois.parquet")
    overture_source_path: Path = Path("data/raw/overture/bengaluru_overture_places.parquet")
    canonical_pois_h3_path: Path = Path("data/processed/canonical_pois_h3.parquet")
    candidate_pairs_path: Path = Path("data/processed/candidate_pairs/candidate_pairs_union.parquet")
    pairwise_features_path: Path = Path("data/processed/features/pairwise_features.parquet")
    supervised_model_path: Path = Path("models/supervised_poi_matcher_v1.joblib")
    predictions_path: Path = Path("data/processed/predictions/supervised_predictions_universe.parquet")

    # Output and staging directories
    production_dir: Path = Path("data/processed/canonical")
    staging_dir: Path = Path("data/processed/staging")
    snapshots_dir: Path = Path("data/processed/snapshots")
    reports_dir: Path = Path("reports")
    lineage_path: Path = Path("data/processed/canonical/canonical_entity_lineage.parquet")

    # Thresholds and parameters
    match_threshold: float = 0.55
    uncertain_threshold: float = 0.30
    dominance_margin_threshold: float = 0.15
    max_equivalence_distance: float = 50.0
    max_absolute_distance: float = 80.0
    enable_honorific_safeguard: bool = True
    batch_size: int = 50000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "run_id": self.run_id,
            "osm_source_path": str(self.osm_source_path),
            "overture_source_path": str(self.overture_source_path),
            "production_dir": str(self.production_dir),
            "staging_dir": str(self.staging_dir),
            "match_threshold": self.match_threshold,
            "uncertain_threshold": self.uncertain_threshold,
            "dominance_margin_threshold": self.dominance_margin_threshold,
            "enable_honorific_safeguard": self.enable_honorific_safeguard,
        }
