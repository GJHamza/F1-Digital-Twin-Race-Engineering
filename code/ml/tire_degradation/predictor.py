# -*- coding: utf-8 -*-
"""
Pipeline Orchestrator for Phase G.4.4 Tire Degradation Modeling
Executes inspection, horizon target construction, feature extraction, temporal split,
multi-output model training & selection, physical validation, and Parquet/JSON exports.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ml.tire_degradation.config import TireDegradationConfig
from ml.tire_degradation.inspection import inspect_tire_telemetry
from ml.tire_degradation.dataset import construct_tire_degradation_dataset
from ml.tire_degradation.features import compute_tire_degradation_features
from ml.tire_degradation.preprocessing import prepare_tire_degradation_dataset
from ml.tire_degradation.baseline import ZeroDegradationBaseline, PreviousDegradationBaseline
from ml.tire_degradation.models import TireDegradationModel
from ml.tire_degradation.evaluation import evaluate_tire_degradation_models, validate_physical_bounds

from datalake.s3_client import get_s3_filesystem, ensure_bucket_exists, parse_s3_uri
from data_generator.generator_v2 import SyntheticGeneratorV2


def run_tire_degradation_pipeline(config=None, silver_source=None, output_dir=None, horizon_steps=None):
    """
    Executes end-to-end Tire Degradation Pipeline for Phase G.4.4.

    Args:
        config (TireDegradationConfig, optional): Configuration object.
        silver_source (str or DataFrame, optional): Telemetry source.
        output_dir (str, optional): Output directory or S3 URI.
        horizon_steps (int, optional): Horizon step count offset.

    Returns:
        dict: Execution summary, metrics table, best model name, feature importances, and timing.
    """
    t0 = time.time()

    if config is None:
        config = TireDegradationConfig(horizon_steps=horizon_steps)
    elif horizon_steps is not None:
        config.horizon_steps = horizon_steps

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
        raw_events = gen.generate_dataset("RACE_DRY", sessions_count=5, laps_per_session=10)
        df_silver = pd.DataFrame(raw_events)

    # 2. Telemetry Inspection
    inspection_report = inspect_tire_telemetry(df_silver, horizon_steps=config.horizon_steps)

    # 3. Supervised Dataset Construction & Feature Engineering
    df_train, df_val, df_test, preprocessor, feature_cols, split_info = prepare_tire_degradation_dataset(
        df_silver, config
    )

    df_sup, ds_summary = construct_tire_degradation_dataset(df_silver, horizon_steps=config.horizon_steps)
    df_featured = compute_tire_degradation_features(df_sup)

    # 4. Model Training
    target_cols = config.target_columns
    y_train = df_train[target_cols].values if not df_train.empty else np.zeros((0, 4))

    zero_base = ZeroDegradationBaseline()
    zero_base.fit(None, None)

    prev_base = PreviousDegradationBaseline(horizon_steps=config.horizon_steps)
    prev_base.fit(df_train, y_train)

    rf_model = TireDegradationModel("random_forest", random_state=config.random_state)
    gbr_model = TireDegradationModel("gradient_boosting", random_state=config.random_state)

    if not df_train.empty:
        X_train_scaled = preprocessor.transform(df_train)
        rf_model.fit(X_train_scaled, y_train)
        gbr_model.fit(X_train_scaled, y_train)

    models_dict = {
        "Zero Degradation Baseline": zero_base,
        "Previous Degradation Baseline": prev_base,
        "RandomForestRegressor": rf_model,
        "GradientBoostingRegressor": gbr_model
    }

    # 5. Model Evaluation & Selection
    eval_report = evaluate_tire_degradation_models(
        models_dict, df_train, df_val, df_test, preprocessor, feature_cols, target_cols
    )

    best_name = eval_report["best_model_name"]
    best_model = models_dict[best_name]

    # Feature importances for winning model
    if hasattr(best_model, "get_feature_importances"):
        df_importances = best_model.get_feature_importances(feature_cols)
    elif hasattr(rf_model, "get_feature_importances"):
        df_importances = rf_model.get_feature_importances(feature_cols)
    else:
        df_importances = pd.DataFrame()

    # 6. Prediction Export Generation
    ts_now = datetime.now(timezone.utc).isoformat()
    prediction_rows = []

    if not df_featured.empty:
        X_all_scaled = preprocessor.transform(df_featured)
        if "Baseline" in best_name:
            preds_deltas = best_model.predict(df_featured)
        else:
            preds_deltas = best_model.predict(X_all_scaled)

        wheels = ["fl", "fr", "rl", "rr"]
        for i in range(len(df_featured)):
            row = df_featured.iloc[i]
            row_dict = {
                "event_id": row.get("event_id", f"EVT-{i}"),
                "session_id": row.get("session_id", "SES-01"),
                "car_id": row.get("car_id", "SIM-CAR-01"),
                "driver_id": row.get("driver_id", "SIM-DRV-01"),
                "timestamp": row.get("timestamp", ts_now),
                "horizon_steps": config.horizon_steps,
            }

            for idx_w, pos in enumerate(wheels):
                curr_w = float(row[f"tire_wear_{pos}"])
                act_d = float(row[f"future_wear_delta_{pos}"])
                pred_d = float(preds_deltas[i, idx_w])
                pred_w = curr_w + pred_d

                row_dict[f"current_wear_{pos}"] = round(curr_w, 4)
                row_dict[f"actual_delta_{pos}"] = round(act_d, 4)
                row_dict[f"predicted_delta_{pos}"] = round(pred_d, 4)
                row_dict[f"predicted_wear_{pos}"] = round(pred_w, 4)

            row_dict["model_name"] = best_name
            row_dict["model_version"] = "v1.0.0"
            row_dict["prediction_timestamp"] = ts_now

            prediction_rows.append(row_dict)

    df_predictions = pd.DataFrame(prediction_rows)
    phys_report = validate_physical_bounds(df_predictions)

    # 7. Persist Output Datasets & Metadata
    metrics_payload = {
        "best_model_name": best_name,
        "metrics_by_model": eval_report["metrics_by_model"],
        "physical_validation": phys_report,
        "dataset_summary": ds_summary
    }

    metadata_payload = {
        "phase": "G.4.4",
        "module": "Tire Degradation Modeling",
        "horizon_steps": config.horizon_steps,
        "wheels": ["FL", "FR", "RL", "RR"],
        "random_state": config.random_state,
        "timestamp": ts_now,
        "split_info": split_info
    }

    if is_s3:
        bucket, subpath = parse_s3_uri(output_dir)
        ensure_bucket_exists(bucket, s3_fs)

        pred_path = f"{bucket}/{subpath}/tire_degradation_predictions.parquet".replace("//", "/")
        table = pa.Table.from_pandas(df_predictions)
        pq.write_table(table, pred_path, filesystem=s3_fs)
    else:
        os.makedirs(output_dir, exist_ok=True)
        pred_file = os.path.join(output_dir, "tire_degradation_predictions.parquet")
        table = pa.Table.from_pandas(df_predictions)
        pq.write_table(table, pred_file, compression="SNAPPY")

        # Write metrics.json & metadata.json locally
        with open(os.path.join(output_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics_payload, f, indent=2)

        with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata_payload, f, indent=2)

        # Save trained model artifact
        models_dir = os.path.join(output_dir, "models")
        if hasattr(best_model, "save"):
            best_model.save(
                os.path.join(models_dir, "best_model.joblib"),
                metadata={"best_model_name": best_name, "split_summary": split_info}
            )

    t1 = time.time()

    return {
        "inspection": inspection_report,
        "dataset_summary": ds_summary,
        "total_predictions": len(df_predictions),
        "split_summary": split_info,
        "comparison_table": eval_report["comparison_table"],
        "best_model_name": best_name,
        "feature_importances": df_importances,
        "physical_validation": phys_report,
        "output_dir": output_dir,
        "duration_sec": round(t1 - t0, 3)
    }
