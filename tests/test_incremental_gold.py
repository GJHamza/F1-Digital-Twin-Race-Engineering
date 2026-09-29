# -*- coding: utf-8 -*-
"""
Unit Tests for Incremental Gold Analytical Dataset Builder
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

from etl.gold.incremental_builder import build_gold_incremental


@pytest.fixture
def dummy_silver_data(tmp_path):
    silver_dir = str(tmp_path / "silver")
    os.makedirs(silver_dir, exist_ok=True)

    records = [
        {
            "event_id": f"EVT_GOLD_{i:04d}",
            "session_id": "SES_GOLD_01",
            "car_id": "FERRARI_01",
            "lap_number": 1,
            "timestamp": "2026-09-22T12:00:00.000Z",
            "speed_kmh": 290.0 + i,
            "g_force": 1.5,
            "fuel_level": 105.0 - i,
            "tire_temp_avg": 95.0,
            "tire_temp_max": 98.0,
            "tire_wear_avg": 2.5,
            "tire_wear_max": 3.0,
            "downforce": 440.0,
            "drag_coefficient": 0.35,
            "wind_speed": 10.0,
            "aero_efficiency": 2.1,
            "tire_stress_index": 45.2,
            "tire_compound": "SOFT",
            "active_anomalies": "[]"
        }
        for i in range(10)
    ]

    df = pd.DataFrame(records)
    f = os.path.join(silver_dir, "silver_batch.parquet")
    pq.write_table(pa.Table.from_pandas(df), f)
    return silver_dir


def test_build_gold_incremental_datasets(dummy_silver_data, tmp_path):
    silver_dir = dummy_silver_data
    gold_dir = str(tmp_path / "gold")

    res = build_gold_incremental(silver_source=silver_dir, output_dir=gold_dir)
    assert res["gold_datasets_updated"] == 5
    assert res["counts"]["lap_performance"] == 1
    assert res["counts"]["tire_performance"] == 1
    assert res["counts"]["fuel_performance"] == 1
    assert res["counts"]["aero_performance"] == 1

    # Verify output Parquet files created
    for name in ["lap_performance", "tire_performance", "fuel_performance", "aero_performance", "anomaly_summary"]:
        target = os.path.join(gold_dir, name, f"{name}.parquet")
        assert os.path.exists(target), f"Missing Gold parquet file: {target}"
