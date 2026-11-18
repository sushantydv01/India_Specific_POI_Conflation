"""Configuration data models and loader for the matching baseline engine."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml


@dataclass
class MatchingConfig:
    """Configuration parameters for explainable deterministic POI matching."""
    version: str = "1.0.0"
    model_name: str = "explainable_rule_baseline_v1"
    description: str = "Deterministic transparent weighted scoring baseline with contradiction guardrails"
    feature_group_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "name": 0.35,
            "transliteration": 0.15,
            "spatial": 0.30,
            "category": 0.15,
            "strategy": 0.05,
        }
    )
    group_subweights: Dict[str, Dict[str, float]] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "match_min_score": 0.75,
            "uncertain_min_score": 0.40,
        }
    )
    guardrails: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str = "configs/matching_baseline.yaml") -> "MatchingConfig":
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            version=data.get("version", "1.0.0"),
            model_name=data.get("model_name", "explainable_rule_baseline_v1"),
            description=data.get("description", ""),
            feature_group_weights=data.get("feature_group_weights", {}),
            group_subweights=data.get("group_subweights", {}),
            thresholds=data.get("thresholds", {}),
            guardrails=data.get("guardrails", {}),
        )
