# -*- coding: utf-8 -*-
"""
Automated Unit Tests for Gold Layer Builder & Analytical Aggregations
"""

import os
import sys
import tempfile
import pytest
import pandas as pd
import pyarrow.parquet as pq

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from etl.silver.silver_transformer import transform_silver
from etl.gold.gold_builder import build_gold
from data_generator.generator_v2 import SyntheticGeneratorV2


@pytest.fixture
def sample_silver_df():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("TIRE_OVERHEAT", sessions_count=2, laps_per_session=2)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        silver_out = os.path.join(tmpdir, "silver")
        quarantine_out = os.path.join(tmpdir, "quarantine")
        transform_silver(raw_events, output_dir=silver_out, quarantine_dir=quarantine_out)
        
        dataset = pq.ParquetDataset(silver_out)
        return dataset.read().to_pandas()


def test_build_gold_datasets(sample_silver_df):
    with tempfile.TemporaryDirectory() as tmpdir:
        gold_out = os.path.join(tmpdir, "gold")
        report = build_gold(sample_silver_df, output_dir=gold_out)

        assert report["gold_datasets_created"] == 5
        assert "lap_performance" in report["counts"]
        assert "tire_performance" in report["counts"]
        assert "fuel_performance" in report["counts"]
        assert "aero_performance" in report["counts"]
        assert "anomaly_summary" in report["counts"]

        # 1. Lap Performance
        df_lap = pd.read_parquet(os.path.join(gold_out, "lap_performance", "lap_performance.parquet"))
        assert len(df_lap) == 4  # 2 sessions x 2 laps
        assert "lap_time_ms" in df_lap.columns
        assert "average_speed" in df_lap.columns
        assert (df_lap["fuel_consumed"] >= 0.0).all()

        # 2. Tire Performance
        df_tire = pd.read_parquet(os.path.join(gold_out, "tire_performance", "tire_performance.parquet"))
        assert len(df_tire) == 4
        assert "avg_tire_temp" in df_tire.columns
        assert "tire_stress" in df_tire.columns

        # 3. Fuel Performance
        df_fuel = pd.read_parquet(os.path.join(gold_out, "fuel_performance", "fuel_performance.parquet"))
        assert len(df_fuel) == 2  # 2 sessions
        assert "starting_fuel" in df_fuel.columns
        assert "ending_fuel" in df_fuel.columns

        # 4. Aero Performance
        df_aero = pd.read_parquet(os.path.join(gold_out, "aero_performance", "aero_performance.parquet"))
        assert len(df_aero) == 4
        assert "aero_efficiency" in df_aero.columns

        # 5. Anomaly Summary
        df_anom = pd.read_parquet(os.path.join(gold_out, "anomaly_summary", "anomaly_summary.parquet"))
        assert len(df_anom) > 0
        assert "anomaly_type" in df_anom.columns
        assert "anomaly_count" in df_anom.columns


def test_build_gold_empty_input():
    with tempfile.TemporaryDirectory() as tmpdir:
        report = build_gold(pd.DataFrame(), output_dir=tmpdir)
        assert report["gold_datasets_created"] == 0
        assert report["counts"] == {}
