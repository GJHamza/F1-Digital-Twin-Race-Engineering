# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.3 Target Construction Module
"""

import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from etl.silver.silver_transformer import transform_silver
from ml.performance.target import construct_lap_target_dataset


@pytest.fixture
def sample_silver_data():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=3)
    return pd.DataFrame(raw_events)


def test_target_construction_valid_laps(sample_silver_data):
    df_laps = construct_lap_target_dataset(sample_silver_data)

    assert not df_laps.empty
    assert len(df_laps) == 6  # 2 sessions x 3 laps
    assert "lap_id" in df_laps.columns
    assert "lap_time_sec" in df_laps.columns
    assert (df_laps["lap_time_sec"] > 0).all()
    assert not df_laps["lap_time_sec"].isna().any()


def test_target_construction_empty_input():
    df_laps = construct_lap_target_dataset(pd.DataFrame())
    assert df_laps.empty
    assert "lap_time_sec" in df_laps.columns


def test_target_construction_chronological_ordering(sample_silver_data):
    df_laps = construct_lap_target_dataset(sample_silver_data)
    laps_list = df_laps["lap_number"].tolist()

    # Check lap numbers increase within sessions
    for session_id, group in df_laps.groupby("session_id"):
        nums = group["lap_number"].tolist()
        assert nums == sorted(nums)
