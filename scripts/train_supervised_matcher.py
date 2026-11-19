#!/usr/bin/env python3
"""Train the supervised POI matching classifier on component-isolated training partition.

Requirements:
1. Uses 44 pairwise features.
2. Trains on train_features.parquet (binary target pairs).
3. Tunes probability thresholds on validation_features.parquet.
4. Leaves frozen test partition strictly untouched.
5. Saves serialized model to models/supervised_poi_matcher_v1.joblib.
6. Saves feature importance report to reports/model_feature_importance.json.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.poi_conflation.matching.supervised_model import SupervisedPOIMatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_supervised_matcher")


def load_partition_data(parquet_path: Path):
    table = pq.read_table(parquet_path)
    df = table.to_pydict()

    # Identify feature columns
    feat_cols = [c for c in table.schema.names if c.startswith("feat_")]

    # Filter to binary records
    indices = [
        i for i, dec in enumerate(df["decision"])
        if dec in ("MATCH", "NON_MATCH")
    ]

    pair_ids = [df["pair_id"][i] for i in indices]
    y = np.array([1 if df["decision"][i] == "MATCH" else 0 for i in indices], dtype=int)

    # Feature matrix X
    X_rows = []
    for i in indices:
        row = [float(df[col][i]) for col in feat_cols]
        X_rows.append(row)
    X = np.array(X_rows, dtype=np.float32)

    return X, y, pair_ids, feat_cols


def main():
    root = Path(__file__).resolve().parent.parent
    supervised_dir = root / "data" / "processed" / "supervised"
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    config_path = root / "configs" / "supervised_matching_config.yaml"

    train_path = supervised_dir / "train_features.parquet"
    val_path = supervised_dir / "validation_features.parquet"

    logger.info(f"Loading training data from {train_path}")
    X_train, y_train, train_pids, feat_cols = load_partition_data(train_path)
    logger.info(f"Loaded {X_train.shape[0]} training samples ({np.sum(y_train==1)} MATCH, {np.sum(y_train==0)} NON_MATCH)")

    logger.info(f"Loading validation data from {val_path}")
    X_val, y_val, val_pids, val_feat_cols = load_partition_data(val_path)
    logger.info(f"Loaded {X_val.shape[0]} validation samples ({np.sum(y_val==1)} MATCH, {np.sum(y_val==0)} NON_MATCH)")

    # Initialize matcher
    matcher = SupervisedPOIMatcher(config_path=str(config_path))
    matcher.feature_columns = feat_cols

    # Fit model
    matcher.fit(X_train, y_train, feature_names=feat_cols)

    # Tune thresholds on validation partition
    tuned_thresholds = matcher.tune_thresholds_on_validation(X_val, y_val)
    logger.info(f"Tuned thresholds on validation partition: {tuned_thresholds}")

    # Compute feature importances
    importances = matcher.get_feature_importances()
    top_10 = list(importances.items())[:10]
    logger.info("Top 10 Most Predictive Features:")
    for rank, (name, val) in enumerate(top_10, 1):
        logger.info(f"  {rank}. {name}: {val['normalized_importance']:.4f} (raw: {val['raw_importance']:.2f})")

    # Save feature importance report
    importance_report = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_type": matcher.model_type,
            "n_train_samples": len(y_train),
            "n_features": len(feat_cols),
        },
        "top_10_features": [
            {"rank": i + 1, "feature": name, "normalized_importance": data["normalized_importance"], "raw_importance": data["raw_importance"]}
            for i, (name, data) in enumerate(top_10)
        ],
        "all_feature_importances": importances,
    }
    importance_report_path = reports_dir / "model_feature_importance.json"
    with open(importance_report_path, "w", encoding="utf-8") as f:
        json.dump(importance_report, f, indent=2)
    logger.info(f"Saved feature importance report to {importance_report_path}")

    # Save model
    model_save_path = models_dir / "supervised_poi_matcher_v1.joblib"
    metadata_save_path = models_dir / "supervised_poi_matcher_v1_metadata.json"
    matcher.save(model_save_path, metadata_save_path)

    print("--- Supervised Model Training Summary ---")
    print(f"Model Type: {matcher.model_type}")
    print(f"Training Samples: {len(y_train)} (MATCH={np.sum(y_train==1)}, NON_MATCH={np.sum(y_train==0)})")
    print(f"Validation Samples: {len(y_val)} (MATCH={np.sum(y_val==1)}, NON_MATCH={np.sum(y_val==0)})")
    print(f"Tuned Thresholds: {tuned_thresholds}")
    print("Top 5 Features:")
    for rank, (name, val) in enumerate(top_10[:5], 1):
        print(f"  {rank}. {name}: {val['normalized_importance']:.4f}")
    print(f"Artifacts saved to {model_save_path}")


if __name__ == "__main__":
    main()
