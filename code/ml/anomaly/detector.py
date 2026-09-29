# -*- coding: utf-8 -*-
"""
End-to-End Telemetry Anomaly Detection Orchestrator for Phase G.4.2
Orchestrates preprocessing, model training on Train, threshold calibration on Validation,
anomaly scoring and explainability on Test, and Parquet output storage.
"""

import os
import sys
import time
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ml.anomaly.config import AnomalyConfig
from ml.anomaly.preprocessing import AnomalyPreprocessor
from ml.anomaly.baseline import ZScoreBaselineDetector
from ml.anomaly.isolation_forest import IsolationForestDetector
from ml.anomaly.scoring import AnomalyScoreCalibrator
from ml.anomaly.explain import AnomalyExplainer

from datalake.s3_client import get_s3_filesystem, ensure_bucket_exists, parse_s3_uri


def detect_telemetry_anomalies(config=None, ml_source=None, output_dir=None):
    """
    Executes End-to-End Telemetry Anomaly Detection:
    1. Loads Train, Validation, and Test ML feature datasets.
    2. Fits Preprocessor (StandardScaler) strictly on Train.
    3. Fits Z-Score Baseline and Isolation Forest strictly on Train.
    4. Calibrates min/max normalization and severity thresholds on Validation.
    5. Scores Test partition (and full dataset) for anomaly_score, label, severity, and top signals.
    6. Writes Parquet datasets to Local or S3A MinIO storage.

    Args:
        config (AnomalyConfig, optional): Configuration container.
        ml_source (str, optional): Custom ML dataset source folder / S3 URI.
        output_dir (str, optional): Custom anomaly output directory / S3 URI.

    Returns:
        dict: Detailed summary containing anomaly counts, severity breakdown, baseline comparison, and duration.
    """
    t0 = time.time()

    if config is None:
        config = AnomalyConfig()

    ml_source = config.ml_source if ml_source is None else ml_source
    output_dir = config.output_dir if output_dir is None else output_dir

    is_s3 = output_dir.startswith("s3a://") or output_dir.startswith("s3://")
    s3_fs = None
    if is_s3 or (isinstance(ml_source, str) and (ml_source.startswith("s3a://") or ml_source.startswith("s3://"))):
        s3_fs = get_s3_filesystem()

    # 1. Load ML Feature Partitions (Train, Validation, Test)
    def load_partition(partition_name):
        is_source_s3 = isinstance(ml_source, str) and (ml_source.startswith("s3a://") or ml_source.startswith("s3://"))
        if is_source_s3:
            bucket, subpath = parse_s3_uri(ml_source)
            part_path = f"{bucket}/{subpath}/{partition_name}".rstrip("/")
            try:
                ds = pq.ParquetDataset(part_path, filesystem=s3_fs)
                return ds.read().to_pandas()
            except Exception:
                return pd.DataFrame()
        else:
            part_path = os.path.join(ml_source, partition_name)
            if os.path.exists(part_path):
                try:
                    ds = pq.ParquetDataset(part_path)
                    return ds.read().to_pandas()
                except Exception:
                    return pd.DataFrame()
            return pd.DataFrame()

    df_train = load_partition("train")
    df_val = load_partition("validation")
    df_test = load_partition("test")

    # If partitions are empty, attempt loading directly from ml_source directory
    if df_train.empty and df_val.empty and df_test.empty:
        if isinstance(ml_source, pd.DataFrame):
            df_full = ml_source.copy()
        elif isinstance(ml_source, str) and os.path.exists(ml_source):
            try:
                ds = pq.ParquetDataset(ml_source)
                df_full = ds.read().to_pandas()
            except Exception:
                df_full = pd.DataFrame()
        else:
            df_full = pd.DataFrame()

        if not df_full.empty:
            from ml.dataset.split import perform_temporal_split
            df_train, df_val, df_test, _ = perform_temporal_split(df_full)

    if df_train.empty:
        t1 = time.time()
        return {
            "total_records": 0,
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
            "severities": {},
            "status": "ERROR: Train feature dataset is empty",
            "duration_sec": round(t1 - t0, 3)
        }

    # 2. Fit Preprocessor strictly on Train
    preprocessor = AnomalyPreprocessor(excluded_columns=config.excluded_columns)
    X_train_scaled = preprocessor.fit_transform(df_train)

    # 3. Fit Baseline and Isolation Forest models strictly on Train
    baseline = ZScoreBaselineDetector(z_threshold=config.z_threshold)
    baseline.fit(X_train_scaled, feature_names=preprocessor.fitted_columns)

    iso_forest = IsolationForestDetector(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        random_state=config.random_state
    )
    iso_forest.fit(X_train_scaled)

    # 4. Calibrate Score Normalization & Severity Quantiles on Validation set
    if not df_val.empty:
        X_val_scaled = preprocessor.transform(df_val)
        raw_val_scores = iso_forest.decision_function(X_val_scaled)
    else:
        raw_val_scores = iso_forest.decision_function(X_train_scaled)

    calibrator = AnomalyScoreCalibrator(quantiles=config.severity_quantiles)
    calibrator.calibrate(raw_val_scores)

    # 5. Explainer initialized with Train baseline stats
    explainer = AnomalyExplainer(
        feature_names=preprocessor.fitted_columns,
        train_means=preprocessor.scaler.mean_,
        train_stds=preprocessor.scaler.scale_
    )

    # 6. Predict & Format Anomalies on Test Set (and full combined dataset for output)
    results = {}
    for part_name, df_part in [("train", df_train), ("validation", df_val), ("test", df_test)]:
        if df_part.empty:
            continue

        X_part_scaled = preprocessor.transform(df_part)
        raw_scores = iso_forest.decision_function(X_part_scaled)
        norm_scores = calibrator.score(raw_scores)
        labels = iso_forest.predict(X_part_scaled)
        severities = calibrator.map_severity(norm_scores)
        signals_json = explainer.explain_dataframe(X_part_scaled, top_k=3)

        df_out = df_part.copy()
        df_out["anomaly_score"] = norm_scores
        df_out["anomaly_label"] = labels
        df_out["anomaly_severity"] = severities
        df_out["contributing_signals"] = signals_json
        df_out["model_version"] = config.model_version

        # Baseline comparative score
        df_out["baseline_z_score"] = baseline.predict_score(X_part_scaled)
        df_out["baseline_label"] = baseline.predict_label(X_part_scaled)

        results[part_name] = df_out

    # 7. Persist Output Datasets
    if is_s3:
        bucket, subpath = parse_s3_uri(output_dir)
        ensure_bucket_exists(bucket, s3_fs)
        for part_name, df_res in results.items():
            out_path = f"{bucket}/{subpath}/{part_name}".rstrip("/")
            table = pa.Table.from_pandas(df_res)
            pq.write_to_dataset(table, root_path=out_path, filesystem=s3_fs, compression="SNAPPY")
    else:
        for part_name, df_res in results.items():
            out_dir = os.path.join(output_dir, part_name)
            os.makedirs(out_dir, exist_ok=True)
            table = pa.Table.from_pandas(df_res)
            pq.write_to_dataset(table, root_path=out_dir, compression="SNAPPY")

    # Combine metrics across partitions
    all_res = pd.concat(list(results.values()), ignore_index=True) if results else pd.DataFrame()
    total_recs = len(all_res)
    total_anomalies = int(all_res["anomaly_label"].sum()) if not all_res.empty else 0
    anomaly_rate = float(total_anomalies / total_recs) if total_recs > 0 else 0.0

    sev_counts = all_res["anomaly_severity"].value_counts().to_dict() if not all_res.empty else {}

    t1 = time.time()
    return {
        "total_records": total_recs,
        "anomaly_count": total_anomalies,
        "anomaly_rate": round(anomaly_rate, 4),
        "severities": sev_counts,
        "partition_counts": {k: len(v) for k, v in results.items()},
        "partition_anomalies": {k: int(v["anomaly_label"].sum()) for k, v in results.items()},
        "baseline_anomalies": int(all_res["baseline_label"].sum()) if not all_res.empty else 0,
        "output_dir": output_dir,
        "duration_sec": round(t1 - t0, 3)
    }
