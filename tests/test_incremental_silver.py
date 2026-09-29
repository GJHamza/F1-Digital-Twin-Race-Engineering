# -*- coding: utf-8 -*-
"""
Unit & Integration Tests for Incremental Silver Layer Transformation
Tests: State manifest tracking, Bronze delta detection, quality validation,
event_id deduplication, quarantine routing, and derived metrics computation.
"""

import os
import sys
import pytest
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from etl.silver.incremental_transformer import transform_silver_incremental, load_state_manifest, save_state_manifest


@pytest.fixture
def dummy_bronze_dataset(tmp_path):
    bronze_dir = str(tmp_path / "bronze")
    os.makedirs(bronze_dir, exist_ok=True)

    records1 = [
        {
            "event_id": f"EVT_INC_{i:04d}",
            "session_id": "SES_INC_01",
            "car_id": "FERRARI_01",
            "lap_number": 1,
            "timestamp": "2026-09-22T12:00:00.000Z",
            "speed": 295.0,
            "rpm": 11800,
            "fuel_level": 108.0,
            "telemetry": {"speed": 295.0, "rpm": 11800, "gear": 6, "g_force": 1.6},
            "aerodynamics": {"downforce": 440.0, "drag_coefficient": 0.35, "wind_speed": 10.0},
            "tires": {"tire_temp": [94.0, 95.0, 96.0, 93.0], "tire_wear": [2.0, 2.1, 2.2, 1.9]},
            "active_anomalies": "[]"
        }
        for i in range(1, 11)
    ]

    df1 = pd.DataFrame(records1)
    f1 = os.path.join(bronze_dir, "batch1.parquet")
    pq.write_table(pa.Table.from_pandas(df1), f1)

    return bronze_dir, f1


def test_incremental_silver_batch1(dummy_bronze_dataset, tmp_path):
    bronze_dir, f1 = dummy_bronze_dataset
    silver_dir = str(tmp_path / "silver")
    quarantine_dir = str(tmp_path / "quarantine")
    state_path = str(tmp_path / "state.json")

    res1 = transform_silver_incremental(
        bronze_source=bronze_dir,
        output_dir=silver_dir,
        quarantine_dir=quarantine_dir,
        state_path=state_path
    )

    assert res1["new_files_processed"] == 1
    assert res1["valid_count"] == 10
    assert res1["duplicate_count"] == 0
    assert res1["quarantine_count"] == 0

    state = load_state_manifest(state_path)
    assert len(state["processed_files"]) == 1
    assert len(state["seen_event_ids"]) == 10


def test_incremental_silver_idempotence_and_deduplication(dummy_bronze_dataset, tmp_path):
    bronze_dir, f1 = dummy_bronze_dataset
    silver_dir = str(tmp_path / "silver")
    quarantine_dir = str(tmp_path / "quarantine")
    state_path = str(tmp_path / "state.json")

    # Run Batch 1
    res1 = transform_silver_incremental(
        bronze_source=bronze_dir,
        output_dir=silver_dir,
        quarantine_dir=quarantine_dir,
        state_path=state_path
    )
    assert res1["valid_count"] == 10

    # Run Batch 2 without adding new files
    res2 = transform_silver_incremental(
        bronze_source=bronze_dir,
        output_dir=silver_dir,
        quarantine_dir=quarantine_dir,
        state_path=state_path
    )
    assert res2["new_files_processed"] == 0
    assert res2["valid_count"] == 0

    # Add Batch 2 containing 5 duplicate event_ids and 5 new event_ids
    records2 = [
        # 5 duplicates
        {
            "event_id": f"EVT_INC_{i:04d}",
            "session_id": "SES_INC_01",
            "car_id": "FERRARI_01",
            "lap_number": 1,
            "timestamp": "2026-09-22T12:00:00.000Z",
            "speed": 295.0,
            "telemetry": {"speed": 295.0, "rpm": 11800, "gear": 6},
            "aerodynamics": {"downforce": 440.0, "drag_coefficient": 0.35, "wind_speed": 10.0},
            "tires": {"tire_temp": [94.0, 95.0, 96.0, 93.0], "tire_wear": [2.0, 2.1, 2.2, 1.9]},
            "active_anomalies": "[]"
        }
        for i in range(1, 6)
    ] + [
        # 5 new
        {
            "event_id": f"EVT_INC_{i:04d}",
            "session_id": "SES_INC_01",
            "car_id": "FERRARI_01",
            "lap_number": 1,
            "timestamp": "2026-09-22T12:00:00.000Z",
            "speed": 300.0,
            "telemetry": {"speed": 300.0, "rpm": 11900, "gear": 6},
            "aerodynamics": {"downforce": 450.0, "drag_coefficient": 0.35, "wind_speed": 10.0},
            "tires": {"tire_temp": [94.0, 95.0, 96.0, 93.0], "tire_wear": [2.0, 2.1, 2.2, 1.9]},
            "active_anomalies": "[]"
        }
        for i in range(11, 16)
    ]

    f2 = os.path.join(bronze_dir, "batch2.parquet")
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(records2)), f2)

    res3 = transform_silver_incremental(
        bronze_source=bronze_dir,
        output_dir=silver_dir,
        quarantine_dir=quarantine_dir,
        state_path=state_path
    )
    assert res3["new_files_processed"] == 1
    assert res3["total_processed"] == 10
    assert res3["valid_count"] == 5
    assert res3["duplicate_count"] == 5
    assert res3["quarantine_count"] == 5

    state = load_state_manifest(state_path)
    assert len(state["seen_event_ids"]) == 15
