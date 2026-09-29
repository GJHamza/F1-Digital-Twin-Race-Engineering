# -*- coding: utf-8 -*-
"""
Automated Unit Tests for Silver Layer Transformer & Quality Rules
"""

import os
import sys
import tempfile
import pytest
import pandas as pd
import pyarrow.parquet as pq

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from etl.silver.quality_rules import validate_silver_record
from etl.silver.silver_transformer import transform_silver
from data_generator.generator_v2 import SyntheticGeneratorV2


@pytest.fixture
def sample_events():
    gen = SyntheticGeneratorV2(seed=42)
    return gen.generate_dataset("RACE_DRY", sessions_count=1, laps_per_session=2)


def test_quality_rules_validation(sample_events):
    valid_evt = sample_events[0]
    is_valid, reason = validate_silver_record(valid_evt)
    assert is_valid is True
    assert reason is None

    # Missing mandatory event_id
    invalid_evt1 = dict(valid_evt)
    invalid_evt1["event_id"] = ""
    is_valid, reason = validate_silver_record(invalid_evt1)
    assert is_valid is False
    assert "event_id" in reason

    # Out of bounds throttle (> 100)
    invalid_evt2 = dict(valid_evt)
    invalid_evt2["throttle"] = 150.0
    is_valid, reason = validate_silver_record(invalid_evt2)
    assert is_valid is False
    assert "Throttle" in reason

    # Invalid tire array length (!= 4)
    invalid_evt3 = dict(valid_evt)
    invalid_evt3["tires"] = {"tire_temp": [90.0, 90.0]}
    is_valid, reason = validate_silver_record(invalid_evt3)
    assert is_valid is False
    assert "tire_temp" in reason


def test_silver_transformer_and_derived_metrics(sample_events):
    with tempfile.TemporaryDirectory() as tmpdir:
        silver_out = os.path.join(tmpdir, "silver")
        quarantine_out = os.path.join(tmpdir, "quarantine")

        # Include an invalid record and a duplicate record
        invalid_evt = dict(sample_events[0])
        invalid_evt["throttle"] = 200.0  # Invalid

        duplicate_evt = dict(sample_events[1])  # Duplicate event_id

        input_list = sample_events + [invalid_evt, duplicate_evt]

        report = transform_silver(input_list, output_dir=silver_out, quarantine_dir=quarantine_out)

        assert report["total_processed"] == len(sample_events) + 2
        assert report["valid_count"] == len(sample_events)
        assert report["quarantine_count"] == 2
        assert report["duplicate_count"] == 1

        # Read back Silver Parquet dataset
        dataset = pq.ParquetDataset(silver_out)
        df_silver = dataset.read().to_pandas()

        assert len(df_silver) == len(sample_events)
        assert "speed_ms" in df_silver.columns
        assert "acceleration_estimate" in df_silver.columns
        assert "tire_temp_avg" in df_silver.columns
        assert "tire_wear_avg" in df_silver.columns
        assert "fuel_remaining_pct" in df_silver.columns
        assert "aero_efficiency" in df_silver.columns
        assert "tire_stress_index" in df_silver.columns

        # Check unit formula: speed_ms == speed_kmh / 3.6
        first_row = df_silver.iloc[0]
        assert abs(first_row["speed_ms"] - (first_row["speed_kmh"] / 3.6)) < 1e-4

        # Read back Quarantine Parquet dataset
        dataset_q = pq.ParquetDataset(quarantine_out)
        df_q = dataset_q.read().to_pandas()
        assert len(df_q) == 2
        assert "rejection_reason" in df_q.columns
