# -*- coding: utf-8 -*-
"""
Unit Tests for ML Feature Extraction Modules (G.4.1)
Tests performance, tyres, aerodynamics, powertrain, and temporal feature calculations.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.features.performance import compute_performance_features
from ml.features.tyres import compute_tyre_features
from ml.features.aerodynamics import compute_aerodynamic_features
from ml.features.powertrain import compute_powertrain_features
from ml.features.temporal import compute_temporal_features


@pytest.fixture
def sample_silver_df():
    return pd.DataFrame([
        {
            "event_id": f"EVT_ML_{i:04d}",
            "session_id": "SES_ML_01",
            "car_id": "FERRARI_01",
            "driver_id": "LEC",
            "timestamp": f"2026-09-22T12:00:{i:02d}.000Z",
            "speed_kmh": 280.0 + (i * 2.0),
            "speed_ms": (280.0 + (i * 2.0)) / 3.6,
            "g_force": 1.5,
            "tire_temp_avg": 90.0 + i,
            "tire_temp_max": 92.0 + i,
            "tire_wear_avg": 2.0 + (i * 0.1),
            "tire_wear_max": 2.2 + (i * 0.1),
            "downforce": 400.0 + (i * 10.0),
            "drag_coefficient": 0.35,
            "wind_speed": 10.0,
            "rpm": 11000 + (i * 50),
            "torque": 400.0,
            "fuel_level": 105.0 - (i * 0.2)
        }
        for i in range(10)
    ])


def test_performance_feature_computation(sample_silver_df):
    res = compute_performance_features(sample_silver_df)
    assert "speed_ms" in res.columns
    assert "acceleration_estimate" in res.columns
    assert res["speed_ms"].iloc[0] == pytest.approx(280.0 / 3.6, abs=1e-3)
    assert len(res) == 10


def test_tyre_feature_computation(sample_silver_df):
    res = compute_tyre_features(sample_silver_df)
    assert "tire_stress_index" in res.columns
    assert "tire_wear_rate" in res.columns
    assert (res["tire_stress_index"] >= 0).all()
    assert (res["tire_wear_rate"] >= 0).all()


def test_aerodynamic_feature_computation(sample_silver_df):
    res = compute_aerodynamic_features(sample_silver_df)
    assert "aero_efficiency" in res.columns
    assert "downforce_per_speed" in res.columns
    assert (res["aero_efficiency"] > 0).all()
    assert (res["downforce_per_speed"] > 0).all()


def test_powertrain_feature_computation(sample_silver_df):
    res = compute_powertrain_features(sample_silver_df)
    assert "torque_per_rpm" in res.columns
    assert "estimated_power_kw" in res.columns
    assert "fuel_remaining_pct" in res.columns
    assert (res["estimated_power_kw"] > 0).all()
    assert res["fuel_remaining_pct"].iloc[0] == pytest.approx((105.0 / 110.0) * 100.0, abs=1e-2)


def test_temporal_feature_computation(sample_silver_df):
    res = compute_temporal_features(sample_silver_df, window_size=3)
    assert "elapsed_time_sec" in res.columns
    assert "rolling_speed_mean_5" in res.columns
    assert "rolling_speed_std_5" in res.columns
    assert res["elapsed_time_sec"].iloc[0] == 0.0
    assert res["elapsed_time_sec"].iloc[9] == 9.0
