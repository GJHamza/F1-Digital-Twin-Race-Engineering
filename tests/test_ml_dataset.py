# -*- coding: utf-8 -*-
"""
Integration & End-to-End Tests for ML Dataset Builder (G.4.1)
"""

import os
import sys
import pytest
import pandas as pd

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.config import MLConfig
from ml.dataset.builder import build_ml_dataset
from datalake.s3_client import check_minio_health, MINIO_BUCKET


@pytest.fixture
def dummy_silver_data(tmp_path):
    silver_dir = str(tmp_path / "silver")
    os.makedirs(silver_dir, exist_ok=True)

    records = [
        {
            "event_id": f"EVT_ML_DS_{i:04d}",
            "session_id": "SES_ML_BUILD_01",
            "car_id": "FERRARI_01",
            "driver_id": "LEC",
            "timestamp": f"2026-09-22T14:00:{i:02d}.000Z",
            "speed": 290.0 + i,
            "rpm": 11500 + (i * 10),
            "torque": 420.0,
            "g_force": 1.5,
            "downforce": 430.0,
            "drag_coefficient": 0.35,
            "wind_speed": 10.0,
            "fuel_level": 108.0 - (i * 0.1),
            "tire_temp_avg": 94.0,
            "tire_temp_max": 95.0,
            "tire_wear_avg": 1.5 + (i * 0.05),
            "tire_wear_max": 1.7 + (i * 0.05),
        }
        for i in range(20)
    ]
    df = pd.DataFrame(records)
    f_path = os.path.join(silver_dir, "silver_sample.parquet")
    df.to_parquet(f_path, index=False)
    return silver_dir


def test_build_ml_dataset_local(dummy_silver_data, tmp_path):
    output_dir = str(tmp_path / "ml_features")
    config = MLConfig(storage_backend="local", silver_source=dummy_silver_data, output_dir=output_dir)

    res = build_ml_dataset(config)

    assert res["total_records"] == 20
    assert res["feature_count"] > 15
    assert res["train_count"] == 14  # 70% of 20
    assert res["val_count"] == 3    # 15% of 20
    assert res["test_count"] == 3   # 15% of 20
    assert res["validation"]["is_valid"] is True

    # Verify Parquet files exist in train, validation, and test folders
    assert os.path.exists(os.path.join(output_dir, "train"))
    assert os.path.exists(os.path.join(output_dir, "validation"))
    assert os.path.exists(os.path.join(output_dir, "test"))


@pytest.mark.integration
def test_build_ml_dataset_minio(dummy_silver_data):
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")

    s3_output = f"s3a://{MINIO_BUCKET}/ml/test_features"
    config = MLConfig(storage_backend="minio", silver_source=dummy_silver_data, output_dir=s3_output)

    res = build_ml_dataset(config)

    assert res["total_records"] == 20
    assert res["validation"]["is_valid"] is True
