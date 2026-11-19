"""Supervised POI matching model using gradient-boosted trees (LightGBM) and Random Forest fallback.

Provides:
- Model training with class imbalance handling.
- Calibrated 3-way decision boundaries (MATCH, UNCERTAIN, NON_MATCH).
- Feature importance extraction.
- Serialization and metadata tracking.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import joblib
import numpy as np
import yaml

from src.poi_conflation.matching.engine import MatchingDecision

logger = logging.getLogger("supervised_poi_matcher")


class SupervisedPOIMatcher:
    """Supervised classifier for pairwise POI entity matching."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        if config is not None:
            self.config = config
        elif config_path is not None and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            default_cfg_path = Path("configs/supervised_matching_config.yaml")
            if default_cfg_path.exists():
                with open(default_cfg_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            else:
                self.config = {
                    "model_type": "lightgbm",
                    "hyperparameters": {
                        "max_depth": 4,
                        "learning_rate": 0.05,
                        "n_estimators": 100,
                        "min_child_samples": 5,
                        "class_weight": "balanced",
                        "random_state": 42,
                        "verbose": -1,
                    },
                    "thresholds": {
                        "match_threshold": 0.70,
                        "uncertain_lower_threshold": 0.35,
                    },
                    "feature_columns": [],
                }

        self.model_type = self.config.get("model_type", "lightgbm")
        self.hyperparameters = self.config.get("hyperparameters", {})
        self.thresholds = self.config.get("thresholds", {
            "match_threshold": 0.70,
            "uncertain_lower_threshold": 0.35,
        })
        self.feature_columns = self.config.get("feature_columns", [])
        self.estimator = None
        self.feature_names: List[str] = []
        self.training_metadata: Dict[str, Any] = {}

    def _init_estimator(self):
        """Instantiate model estimator based on configured model_type."""
        if self.model_type == "lightgbm":
            try:
                import lightgbm as lgb
                params = dict(self.hyperparameters)
                # Ensure verbose is negative
                params["verbose"] = -1
                return lgb.LGBMClassifier(**params)
            except Exception as e:
                logger.warning(f"LightGBM initialization failed: {e}. Falling back to RandomForestClassifier.")
                self.model_type = "random_forest"
                return self._init_random_forest()
        elif self.model_type == "random_forest":
            return self._init_random_forest()
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _init_random_forest(self):
        from sklearn.ensemble import RandomForestClassifier
        params = self.config.get("fallback_hyperparameters", {
            "n_estimators": 100,
            "max_depth": 6,
            "min_samples_split": 4,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
            "random_state": 42,
        })
        return RandomForestClassifier(**params)

    def fit(
        self,
        X: Union[np.ndarray, List[List[float]]],
        y: Union[np.ndarray, List[int]],
        feature_names: Optional[List[str]] = None,
        val_data: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ):
        """Fit the supervised classifier on training features X and binary targets y."""
        X_arr = np.asarray(X, dtype=np.float32)
        y_arr = np.asarray(y, dtype=np.int32)

        if feature_names:
            self.feature_names = list(feature_names)
        elif self.feature_columns:
            self.feature_names = list(self.feature_columns)
        else:
            self.feature_names = [f"f_{i}" for i in range(X_arr.shape[1])]

        self.estimator = self._init_estimator()

        logger.info(
            f"Fitting {self.model_type} on {X_arr.shape[0]} samples with {X_arr.shape[1]} features (Pos={np.sum(y_arr==1)}, Neg={np.sum(y_arr==0)})"
        )
        self.estimator.fit(X_arr, y_arr)

        self.training_metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model_type": self.model_type,
            "n_train_samples": int(X_arr.shape[0]),
            "n_train_positives": int(np.sum(y_arr == 1)),
            "n_train_negatives": int(np.sum(y_arr == 0)),
            "n_features": int(X_arr.shape[1]),
            "feature_names": self.feature_names,
            "hyperparameters": self.hyperparameters,
            "thresholds": self.thresholds,
        }
        return self

    def predict_proba(self, X: Union[np.ndarray, List[List[float]]]) -> np.ndarray:
        """Predict match probabilities (returns array of shape (N,) with probability of MATCH)."""
        if self.estimator is None:
            raise RuntimeError("Model has not been fitted. Call fit() or load() first.")
        X_arr = np.asarray(X, dtype=np.float32)
        proba = self.estimator.predict_proba(X_arr)
        # Binary classification: return class 1 probability
        if proba.shape[1] == 2:
            return proba[:, 1]
        return proba.squeeze()

    def predict_decision(
        self,
        X: Union[np.ndarray, List[List[float]]],
        match_threshold: Optional[float] = None,
        uncertain_threshold: Optional[float] = None,
    ) -> List[MatchingDecision]:
        """Classify into 3-way operational decisions: MATCH, UNCERTAIN, NON_MATCH."""
        m_thresh = match_threshold if match_threshold is not None else self.thresholds.get("match_threshold", 0.70)
        u_thresh = uncertain_threshold if uncertain_threshold is not None else self.thresholds.get("uncertain_lower_threshold", 0.35)

        probas = self.predict_proba(X)
        decisions: List[MatchingDecision] = []

        for p in probas:
            if p >= m_thresh:
                decisions.append(MatchingDecision.MATCH)
            elif p >= u_thresh:
                decisions.append(MatchingDecision.UNCERTAIN)
            else:
                decisions.append(MatchingDecision.NON_MATCH)
        return decisions

    def predict_binary(self, X: Union[np.ndarray, List[List[float]]], threshold: float = 0.5) -> np.ndarray:
        """Standard binary 0/1 prediction based on cutoff threshold."""
        probas = self.predict_proba(X)
        return (probas >= threshold).astype(int)

    def get_feature_importances(self) -> Dict[str, float]:
        """Return feature importances dictionary sorted by importance descending."""
        if self.estimator is None:
            raise RuntimeError("Model has not been fitted.")

        if hasattr(self.estimator, "feature_importances_"):
            raw_importances = self.estimator.feature_importances_
        else:
            return {}

        total = np.sum(raw_importances) if np.sum(raw_importances) > 0 else 1.0
        normalized = raw_importances / total

        imp_dict = {}
        for name, imp, norm in zip(self.feature_names, raw_importances, normalized):
            imp_dict[name] = {
                "raw_importance": float(imp),
                "normalized_importance": float(norm),
            }

        # Sort by normalized importance descending
        sorted_items = sorted(imp_dict.items(), key=lambda item: item[1]["normalized_importance"], reverse=True)
        return dict(sorted_items)

    def tune_thresholds_on_validation(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        target_metric: str = "f1",
    ) -> Dict[str, float]:
        """Tune decision thresholds on validation data to optimize classification performance."""
        probas = self.predict_proba(X_val)
        y_arr = np.asarray(y_val, dtype=int)

        best_f1 = -1.0
        best_threshold = 0.50

        # Sweep candidate binary thresholds from 0.20 to 0.85
        for t in np.linspace(0.20, 0.85, 66):
            preds = (probas >= t).astype(int)
            tp = int(np.sum((preds == 1) & (y_arr == 1)))
            fp = int(np.sum((preds == 1) & (y_arr == 0)))
            fn = int(np.sum((preds == 0) & (y_arr == 1)))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = float(t)

        # Set conservative match threshold and uncertain band
        match_thresh = max(0.55, min(0.80, round(best_threshold, 2)))
        uncertain_thresh = max(0.25, round(match_thresh - 0.25, 2))

        self.thresholds["match_threshold"] = match_thresh
        self.thresholds["uncertain_lower_threshold"] = uncertain_thresh
        self.training_metadata["tuned_thresholds"] = {
            "match_threshold": match_thresh,
            "uncertain_lower_threshold": uncertain_thresh,
            "best_validation_binary_threshold": round(best_threshold, 3),
            "best_validation_f1": round(best_f1, 4),
        }
        return self.thresholds

    def save(self, model_path: Union[str, Path], metadata_path: Optional[Union[str, Path]] = None):
        """Serialize model artifact to disk."""
        m_path = Path(model_path)
        m_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.estimator, m_path)

        meta_p = Path(metadata_path) if metadata_path else m_path.with_suffix(".json")
        metadata = {
            **self.training_metadata,
            "model_path": str(m_path),
            "config": self.config,
        }
        with open(meta_p, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved model to {m_path} and metadata to {meta_p}")

    @classmethod
    def load(cls, model_path: Union[str, Path], metadata_path: Optional[Union[str, Path]] = None) -> "SupervisedPOIMatcher":
        """Load serialized model and metadata."""
        m_path = Path(model_path)
        meta_p = Path(metadata_path) if metadata_path else m_path.with_suffix(".json")
        if not meta_p.exists():
            candidate_meta = m_path.parent / (m_path.stem + "_metadata.json")
            if candidate_meta.exists():
                meta_p = candidate_meta

        config = {}
        if meta_p.exists():
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f)
                config = meta.get("config", {})

        matcher = cls(config=config)
        matcher.estimator = joblib.load(m_path)
        if meta_p.exists():
            with open(meta_p, "r", encoding="utf-8") as f:
                matcher.training_metadata = json.load(f)
                matcher.feature_names = matcher.training_metadata.get("feature_names", [])
                matcher.thresholds = matcher.training_metadata.get("thresholds", matcher.thresholds)
                matcher.model_type = matcher.training_metadata.get("model_type", "lightgbm")
        return matcher
