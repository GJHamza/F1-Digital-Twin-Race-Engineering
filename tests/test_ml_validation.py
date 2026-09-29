# -*- coding: utf-8 -*-
"""
Unit Tests for ML Dataset Quality Validation Engine (G.4.1)
"""

import os
import sys
import pytest
import pandas as pd

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.dataset.validation import validate_ml_dataset


@pytest.fixture
def valid_ml_df():
    return pd.DataFrame([
        {
            "event_id": f"EVT_VAL_{i:04d}",
            "session_id": "SES_VAL_01",
            "timestamp": f"2026-09-22T10:00:{i:02d}.000Z",
            "speed_kmh": 290.0,
            "speed_ms": 290.0 / 3.6,
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
        for i in range(10)
    ])


def test_valid_ml_dataset_passes(valid_ml_df):
    report = validate_ml_dataset(valid_ml_df)
    assert report["is_valid"] is True
    assert report["duplicate_count"] == 0
    assert len(report["errors"]) == 0


def test_duplicate_event_id_detected(valid_ml_df):
    df_dup = valid_ml_df.copy()
    df_dup.loc[1, "event_id"] = df_dup.loc[0, "event_id"]
    report = validate_ml_dataset(df_dup)
    assert report["is_valid"] is False
    assert report["duplicate_count"] == 1


def test_out_of_bounds_value_rejected(valid_ml_df):
    df_oob = valid_ml_df.copy()
    df_oob.loc[0, "speed_kmh"] = 999.0  # Exceeds max 420.0
    report = validate_ml_dataset(df_oob)
    assert report["is_valid"] is False
    assert any("speed_kmh" in err for err in report["errors"])
