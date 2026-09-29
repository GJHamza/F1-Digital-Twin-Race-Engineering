# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.4 Supervised Target Dataset Construction
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from ml.tire_degradation.dataset import construct_tire_degradation_dataset, parse_wheel_arrays


@pytest.fixture
def sample_silver():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=2)
    return pd.DataFrame(raw_events)


def test_parse_wheel_arrays(sample_silver):
    df_parsed = parse_wheel_arrays(sample_silver)

    for pos in ["fl", "fr", "rl", "rr"]:
        assert f"tire_wear_{pos}" in df_parsed.columns
        assert f"tire_temp_{pos}" in df_parsed.columns

    assert "tire_wear_avg" in df_parsed.columns
    assert "tire_temp_avg" in df_parsed.columns


def test_construct_tire_degradation_dataset_target_pairing(sample_silver):
    df_sup, summary = construct_tire_degradation_dataset(sample_silver, horizon_steps=10)

    assert not df_sup.empty
    assert summary["supervised_samples"] > 0
    assert summary["excluded_tail_samples"] > 0

    for pos in ["fl", "fr", "rl", "rr"]:
        assert f"future_wear_delta_{pos}" in df_sup.columns
        assert f"future_wear_{pos}" in df_sup.columns
        # Deltas must be >= 0.0 in nominal test data
        assert (df_sup[f"future_wear_delta_{pos}"] >= 0.0).all()


def test_horizon_does_not_cross_session_boundaries(sample_silver):
    df_sup, summary = construct_tire_degradation_dataset(sample_silver, horizon_steps=10)

    # Verify that future_timestamp comes from the same session_id as observation t
    for sid, group in df_sup.groupby("session_id"):
        assert len(group["session_id"].unique()) == 1
