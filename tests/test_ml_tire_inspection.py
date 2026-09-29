# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.4 Telemetry Inspection Module
"""

import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from ml.tire_degradation.inspection import inspect_tire_telemetry


@pytest.fixture
def sample_telemetry():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=2)
    return pd.DataFrame(raw_events)


def test_tire_telemetry_inspection(sample_telemetry):
    report = inspect_tire_telemetry(sample_telemetry, horizon_steps=10)

    assert report["total_records"] > 0
    assert report["sessions_count"] == 2
    assert report["has_tire_wear"] is True
    assert report["has_tire_temp"] is True
    assert report["wheel_order"] == ["FL", "FR", "RL", "RR"]
    assert report["is_monotonic"] is True
    assert report["horizon_achievable"] is True


def test_tire_telemetry_inspection_empty():
    report = inspect_tire_telemetry(pd.DataFrame(), horizon_steps=10)
    assert report["total_records"] == 0
    assert report["sessions_count"] == 0
    assert report["has_tire_wear"] is False
