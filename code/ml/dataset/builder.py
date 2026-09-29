# -*- coding: utf-8 -*-
"""
ML Dataset Builder Orchestrator for Phase G.4.1
Reads Silver Parquet data, executes feature engineering, validates quality,
performs temporal splits, and writes output datasets to Local or MinIO S3A storage.
"""

import os
import sys
import time
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ml.config import MLConfig
from ml.features.performance import compute_performance_features
from ml.features.tyres import compute_tyre_features
from ml.features.aerodynamics import compute_aerodynamic_features
from ml.features.powertrain import compute_powertrain_features
from ml.features.temporal import compute_temporal_features
from ml.dataset.validation import validate_ml_dataset
from ml.dataset.split import perform_temporal_split

from datalake.s3_client import get_s3_filesystem, ensure_bucket_exists, parse_s3_uri


def build_ml_dataset(config=None, silver_source=None, output_dir=None):
    """
    Executes end-to-end ML Feature Dataset Construction:
    1. Loads Silver Parquet telemetry data.
    2. Runs feature engineering modules (Performance, Tyres, Aerodynamics, Powertrain, Temporal).
    3. Validates quality, bounds, and null rates.
    4. Performs temporal split into Train / Validation / Test partitions.
    5. Persists Parquet datasets to Local or MinIO S3A storage.

    Args:
        config (MLConfig, optional): Configuration object.
        silver_source (str, optional): Custom Silver Parquet source path / S3 URI.
        output_dir (str, optional): Custom ML dataset output directory / S3 URI.

    Returns:
        dict: Summary of feature generation, dataset counts, split breakdown, and validation results.
    """
    t0 = time.time()

    if config is None:
        config = MLConfig()

    silver_source = config.silver_source if silver_source is None else silver_source
    output_dir = config.output_dir if output_dir is None else output_dir

    is_s3 = output_dir.startswith("s3a://") or output_dir.startswith("s3://")
    s3_fs = None
    if is_s3 or (isinstance(silver_source, str) and (silver_source.startswith("s3a://") or silver_source.startswith("s3://"))):
        s3_fs = get_s3_filesystem()

    # 1. Load Silver DataFrame
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

    if df_silver.empty:
        t1 = time.time()
        return {
            "total_records": 0,
            "feature_count": 0,
            "train_count": 0,
            "val_count": 0,
            "test_count": 0,
            "validation": {"is_valid": False, "errors": ["Silver input dataset is empty"]},
            "duration_sec": round(t1 - t0, 3)
        }

    # 2. Execute Feature Extractors
    df_feat = compute_performance_features(df_silver)
    df_feat = compute_tyre_features(df_feat)
    df_feat = compute_aerodynamic_features(df_feat)
    df_feat = compute_powertrain_features(df_feat)
    df_feat = compute_temporal_features(df_feat)

    # Filter to selected identifier & feature columns
    keep_cols = [c for c in config.identifier_columns + config.feature_columns if c in df_feat.columns]
    df_ml = df_feat[keep_cols].copy()

    # 3. Quality Validation
    val_report = validate_ml_dataset(df_ml, feature_columns=config.feature_columns)

    # 4. Temporal Split (Train / Validation / Test)
    df_train, df_val, df_test, split_info = perform_temporal_split(
        df_ml,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        test_ratio=config.test_ratio
    )

    # 5. Persist Datasets
    if is_s3:
        bucket, subpath = parse_s3_uri(output_dir)
        ensure_bucket_exists(bucket, s3_fs)
        for part_name, df_part in [("train", df_train), ("validation", df_val), ("test", df_test)]:
            if not df_part.empty:
                part_path = f"{bucket}/{subpath}/{part_name}".rstrip("/")
                table = pa.Table.from_pandas(df_part)
                pq.write_to_dataset(table, root_path=part_path, filesystem=s3_fs, compression="SNAPPY")
    else:
        for part_name, df_part in [("train", df_train), ("validation", df_val), ("test", df_test)]:
            if not df_part.empty:
                part_dir = os.path.join(output_dir, part_name)
                os.makedirs(part_dir, exist_ok=True)
                table = pa.Table.from_pandas(df_part)
                pq.write_to_dataset(table, root_path=part_dir, compression="SNAPPY")

    t1 = time.time()
    return {
        "total_records": len(df_ml),
        "feature_count": len([c for c in config.feature_columns if c in df_ml.columns]),
        "train_count": len(df_train),
        "val_count": len(df_val),
        "test_count": len(df_test),
        "split_summary": split_info,
        "validation": val_report,
        "output_dir": output_dir,
        "duration_sec": round(t1 - t0, 3)
    }
