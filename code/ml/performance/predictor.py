# -*- coding: utf-8 -*-
"""
End-to-End Performance Predictor Pipeline Orchestrator for Phase G.4.3
Executes target extraction, feature generation, temporal split, model training & evaluation,
prediction export, and artifact persistence to Local and MinIO S3A storage.
"""

import os
import sys
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ml.performance.config import PerformanceConfig
from ml.performance.target import construct_lap_target_dataset
from ml.performance.features import compute_pre_lap_features
from ml.performance.preprocessing import prepare_performance_dataset
from ml.performance.baseline import MeanBaselineModel, PreviousLapBaselineModel
from ml.performance.models import PerformanceRegressionModel
from ml.performance.evaluation import evaluate_regression_models

from datalake.s3_client import get_s3_filesystem, ensure_bucket_exists, parse_s3_uri
from data_generator.generator_v2 import SyntheticGeneratorV2
from etl.silver.silver_transformer import transform_silver


def run_performance_prediction_pipeline(config=None, silver_source=None, output_dir=None):
    """
    Executes end-to-end Lap Time / Performance Prediction Pipeline.

    Args:
        config (PerformanceConfig, optional): Configuration container.
        silver_source (str or DataFrame, optional): Path or DataFrame for Silver telemetry.
        output_dir (str, optional): Target output directory or S3 URI.

    Returns:
        dict: Execution report, metrics table, best model name, feature importances, and timing.
    """
    t0 = time.time()

    if config is None:
        config = PerformanceConfig()

    silver_source = config.silver_source if silver_source is None else silver_source
    output_dir = config.output_dir if output_dir is None else output_dir

    is_s3 = str(output_dir).startswith("s3a://") or str(output_dir).startswith("s3://")
    is_source_s3 = isinstance(silver_source, str) and (silver_source.startswith("s3a://") or silver_source.startswith("s3://"))
    s3_fs = None
    if is_s3 or is_source_s3:
        s3_fs = get_s3_filesystem()

    # 1. Load Silver Telemetry DataFrame
    if isinstance(silver_source, pd.DataFrame):
        df_silver = silver_source.copy()
    elif isinstance(silver_source, list):
        df_silver = pd.DataFrame(silver_source)
    elif isinstance(silver_source, str):
        if silver_source.startswith("s3a://") or silver_source.startswith("s3://"):
            bucket, subpath = parse_s3_uri(silver_source)
            target_path = f"{bucket}/{subpath}".rstrip("/")
            try:
                ds = pq.ParquetDataset(target_path, filesystem=s3_fs)
                df_silver = ds.read().to_pandas()
            except Exception:
                df_silver = pd.DataFrame()
        elif os.path.exists(silver_source):
            try:
                ds = pq.ParquetDataset(silver_source)
                df_silver = ds.read().to_pandas()
            except Exception:
                files = []
                if os.path.isfile(silver_source):
                    files = [silver_source]
                else:
                    for r, _, fns in os.walk(silver_source):
                        for fn in fns:
                            if fn.endswith('.parquet'):
                                files.append(os.path.join(r, fn))
                if not files:
                    df_silver = pd.DataFrame()
                else:
                    df_silver = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        else:
            df_silver = pd.DataFrame()
    else:
        df_silver = pd.DataFrame()

    # Fallback to synthetic generator if Silver source is empty
    if df_silver.empty:
        gen = SyntheticGeneratorV2(seed=config.random_state)
        raw_events = gen.generate_dataset("TIRE_OVERHEAT", sessions_count=5, laps_per_session=10)
        df_silver = pd.DataFrame(raw_events)

    # 2. Target Construction & Feature Engineering
    df_laps = construct_lap_target_dataset(df_silver)
    df_train, df_val, df_test, preprocessor, feature_cols, split_info = prepare_performance_dataset(
        df_silver, df_laps, config
    )

    df_featured = compute_pre_lap_features(df_silver, df_laps)

    # 3. Model Training
    mean_base = MeanBaselineModel()
    mean_base.fit(None, df_train[config.target_column].values if not df_train.empty else [])

    prev_base = PreviousLapBaselineModel()
    prev_base.fit(df_train, df_train[config.target_column].values if not df_train.empty else [])

    rf_model = PerformanceRegressionModel(model_type="random_forest", random_state=config.random_state)
    gbr_model = PerformanceRegressionModel(model_type="gradient_boosting", random_state=config.random_state)

    if not df_train.empty:
        X_train_scaled = preprocessor.transform(df_train)
        y_train = df_train[config.target_column].values
        rf_model.fit(X_train_scaled, y_train)
        gbr_model.fit(X_train_scaled, y_train)

    models_dict = {
        "Mean Baseline": mean_base,
        "Previous-Lap Baseline": prev_base,
        "RandomForestRegressor": rf_model,
        "GradientBoostingRegressor": gbr_model
    }

    # 4. Model Evaluation & Selection
    eval_report = evaluate_regression_models(
        models_dict, df_train, df_val, df_test, preprocessor, feature_cols, config.target_column
    )

    best_name = eval_report["best_model_name"]
    best_model = models_dict[best_name]

    # Feature Importance for winning model
    if hasattr(best_model, "get_feature_importances"):
        df_importances = best_model.get_feature_importances(feature_cols)
    elif hasattr(rf_model, "get_feature_importances"):
        df_importances = rf_model.get_feature_importances(feature_cols)
    else:
        df_importances = pd.DataFrame()

    # 5. Generate Predictions Dataset across all laps
    ts_now = datetime.now(timezone.utc).isoformat()
    prediction_rows = []

    if not df_featured.empty:
        X_all_scaled = preprocessor.transform(df_featured)
        y_all = df_featured[config.target_column].values

        if "Baseline" in best_name:
            preds_all = best_model.predict(df_featured)
        else:
            preds_all = best_model.predict(X_all_scaled)

        for i in range(len(df_featured)):
            actual = float(y_all[i])
            predicted = float(preds_all[i])
            err = round(predicted - actual, 4)
            abs_err = round(abs(err), 4)

            row = df_featured.iloc[i]
            prediction_rows.append({
                "lap_id": row["lap_id"],
                "session_id": row["session_id"],
                "car_id": row["car_id"],
                "driver_id": row["driver_id"],
                "lap_number": row["lap_number"],
                "actual_lap_time_sec": round(actual, 3),
                "predicted_lap_time_sec": round(predicted, 3),
                "prediction_error_sec": err,
                "absolute_error_sec": abs_err,
                "model_name": best_name,
                "model_version": "v1.0.0",
                "prediction_timestamp": ts_now
            })

    df_predictions = pd.DataFrame(prediction_rows)

    # 6. Persist Predictions and Model Artifact
    if is_s3:
        bucket, subpath = parse_s3_uri(output_dir)
        ensure_bucket_exists(bucket, s3_fs)
        
        pred_path = f"{bucket}/{subpath}/lap_predictions.parquet".replace("//", "/")
        table = pa.Table.from_pandas(df_predictions)
        pq.write_table(table, pred_path, filesystem=s3_fs)
    else:
        os.makedirs(output_dir, exist_ok=True)
        pred_file = os.path.join(output_dir, "lap_predictions.parquet")
        table = pa.Table.from_pandas(df_predictions)
        pq.write_table(table, pred_file, compression="SNAPPY")

        # Save model artifact locally
        models_dir = os.path.join(output_dir, "models")
        if hasattr(best_model, "save"):
            best_model.save(
                os.path.join(models_dir, "best_model.joblib"),
                metadata={"best_model_name": best_name, "split_summary": split_info}
            )

    t1 = time.time()

    return {
        "total_laps": len(df_laps),
        "total_predictions": len(df_predictions),
        "split_summary": split_info,
        "comparison_table": eval_report["comparison_table"],
        "best_model_name": best_name,
        "feature_importances": df_importances,
        "output_dir": output_dir,
        "duration_sec": round(t1 - t0, 3)
    }
