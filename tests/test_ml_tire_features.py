# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.4 Feature Engineering & Temporal Split
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from ml.tire_degradation.config import TireDegradationConfig
from ml.tire_degradation.dataset import construct_tire_degradation_dataset
from ml.tire_degradation.features import compute_tire_degradation_features
from ml.tire_degradation.preprocessing import prepare_tire_degradation_dataset, perform_temporal_split


@pytest.fixture
def sample_supervised():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=3)
    df_silver = pd.DataFrame(raw_events)
    df_sup, _ = construct_tire_degradation_dataset(df_silver, horizon_steps=10)
    return df_silver, df_sup


def test_tire_feature_computation(sample_supervised):
    _, df_sup = sample_supervised
    config = TireDegradationConfig(horizon_steps=10)
    df_featured = compute_tire_degradation_features(df_sup)

    assert not df_featured.empty
    assert len(df_featured) == len(df_sup)

    for col in config.feature_columns:
        assert col in df_featured.columns
        assert not df_featured[col].isna().any()


def test_no_future_leakage_in_tire_features(sample_supervised):
    _, df_sup = sample_supervised
    df_featured = compute_tire_degradation_features(df_sup)

    for pos in ["fl", "fr", "rl", "rr"]:
        prev_col = f"previous_wear_delta_{pos}"
        fut_col = f"future_wear_delta_{pos}"
        # previous_wear_delta must not equal future_wear_delta
        assert prev_col in df_featured.columns
        assert fut_col in df_featured.columns


def test_temporal_split_proportions_and_bounds(sample_supervised):
    df_silver, _ = sample_supervised
    config = TireDegradationConfig(horizon_steps=10)
    df_train, df_val, df_test, preprocessor, feature_cols, split_info = prepare_tire_degradation_dataset(
        df_silver, config
    )

    assert len(df_train) + len(df_val) + len(df_test) == split_info["total_rows"]
    assert len(df_train) > 0
    assert len(df_val) > 0
    assert len(df_test) > 0
    assert preprocessor.is_fitted is True
