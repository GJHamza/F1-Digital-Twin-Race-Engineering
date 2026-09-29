# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.3 Feature Engineering & Temporal Split
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from etl.silver.silver_transformer import transform_silver
from ml.performance.config import PerformanceConfig
from ml.performance.target import construct_lap_target_dataset
from ml.performance.features import compute_pre_lap_features
from ml.performance.preprocessing import prepare_performance_dataset, perform_temporal_split


@pytest.fixture
def sample_telemetry_and_laps():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=5)
    df_silver = pd.DataFrame(raw_events)
    df_laps = construct_lap_target_dataset(df_silver)
    return df_silver, df_laps


def test_pre_lap_feature_computation(sample_telemetry_and_laps):
    df_silver, df_laps = sample_telemetry_and_laps
    config = PerformanceConfig()
    df_featured = compute_pre_lap_features(df_silver, df_laps)

    assert not df_featured.empty
    assert len(df_featured) == len(df_laps)

    for col in config.feature_columns:
        assert col in df_featured.columns
        assert not df_featured[col].isna().any()


def test_no_temporal_leakage_in_pre_lap_features(sample_telemetry_and_laps):
    df_silver, df_laps = sample_telemetry_and_laps
    df_featured = compute_pre_lap_features(df_silver, df_laps)

    # For Lap 2, previous_lap_time_sec must equal Lap 1 lap_time_sec
    lap1_time = df_featured[df_featured["lap_number"] == 1]["lap_time_sec"].iloc[0]
    lap2_prev_time = df_featured[df_featured["lap_number"] == 2]["previous_lap_time_sec"].iloc[0]
    assert np.isclose(lap1_time, lap2_prev_time)


def test_temporal_split_proportions(sample_telemetry_and_laps):
    df_silver, df_laps = sample_telemetry_and_laps
    config = PerformanceConfig()
    df_featured = compute_pre_lap_features(df_silver, df_laps)

    df_train, df_val, df_test, info = perform_temporal_split(df_featured, 0.70, 0.15, 0.15)

    assert len(df_train) + len(df_val) + len(df_test) == len(df_featured)
    assert len(df_train) > 0
    assert len(df_val) > 0
    assert len(df_test) > 0
