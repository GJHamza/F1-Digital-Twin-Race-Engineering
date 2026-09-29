# -*- coding: utf-8 -*-
"""
End-to-End Integration Tests for Anomaly Detection Pipeline (G.4.2)
"""

import os
import sys
import pytest
import pandas as pd

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.anomaly.config import AnomalyConfig
from ml.anomaly.detector import detect_telemetry_anomalies
from datalake.s3_client import check_minio_health, MINIO_BUCKET


@pytest.fixture
def dummy_ml_dataset_path(tmp_path):
    base_dir = str(tmp_path / "ml_features")
    for part in ["train", "validation", "test"]:
        part_dir = os.path.join(base_dir, part)
        os.makedirs(part_dir, exist_ok=True)
        count = 70 if part == "train" else 15
        records = [
            {
                "event_id": f"EVT_{part.upper()}_{i:04d}",
                "session_id": "SES_ANOM_01",
                "car_id": "FERRARI_01",
                "driver_id": "LEC",
                "timestamp": f"2026-09-22T10:00:{i:02d}.000Z",
                "speed_kmh": 290.0 + (i if part != "test" or i != 14 else 120.0),  # Extreme value in test
                "speed_ms": 80.0,
                "acceleration_estimate": 0.5,
                "g_force": 1.4,
                "tire_temp_avg": 95.0,
                "tire_temp_max": 96.0,
                "tire_wear_avg": 2.5,
                "tire_wear_max": 2.7,
                "tire_stress_index": 70.0,
                "tire_wear_rate": 0.1,
                "downforce": 420.0,
                "drag_coefficient": 0.35,
                "wind_speed": 10.0,
                "aero_efficiency": 2.5,
                "downforce_per_speed": 5.2,
                "rpm": 11500.0,
                "torque": 410.0,
                "torque_per_rpm": 0.035,
                "estimated_power_kw": 490.0,
                "fuel_level": 100.0,
                "fuel_remaining_pct": 90.9,
                "elapsed_time_sec": float(i),
                "rolling_speed_mean_5": 290.0,
                "rolling_speed_std_5": 0.0,
                "rolling_tire_temp_5": 95.0,
                "rolling_tire_wear_5": 2.5,
            }
            for i in range(count)
        ]
        df = pd.DataFrame(records)
        df.to_parquet(os.path.join(part_dir, f"{part}.parquet"), index=False)

    return base_dir


def test_detect_telemetry_anomalies_local(dummy_ml_dataset_path, tmp_path):
    output_dir = str(tmp_path / "anomalies_out")
    config = AnomalyConfig(storage_backend="local", ml_source=dummy_ml_dataset_path, output_dir=output_dir)

    res = detect_telemetry_anomalies(config)

    assert res["total_records"] == 100
    assert "test" in res["partition_counts"]
    assert res["partition_counts"]["train"] == 70
    assert res["partition_counts"]["validation"] == 15
    assert res["partition_counts"]["test"] == 15

    # Check output Parquet dataset created
    assert os.path.exists(os.path.join(output_dir, "test"))
    df_test_out = pd.read_parquet(os.path.join(output_dir, "test"))

    assert "anomaly_score" in df_test_out.columns
    assert "anomaly_label" in df_test_out.columns
    assert "anomaly_severity" in df_test_out.columns
    assert "contributing_signals" in df_test_out.columns
    assert "model_version" in df_test_out.columns


@pytest.mark.integration
def test_detect_telemetry_anomalies_minio(dummy_ml_dataset_path):
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")

    s3_output = f"s3a://{MINIO_BUCKET}/ml/test_anomalies"
    config = AnomalyConfig(storage_backend="minio", ml_source=dummy_ml_dataset_path, output_dir=s3_output)

    res = detect_telemetry_anomalies(config)

    assert res["total_records"] == 100
