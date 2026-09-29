# -*- coding: utf-8 -*-
"""
Automated Integration Tests for G.4.3 Performance Predictor Pipeline
"""

import os
import sys
import tempfile
import pytest
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from etl.silver.silver_transformer import transform_silver
from ml.performance.config import PerformanceConfig
from ml.performance.predictor import run_performance_prediction_pipeline


def test_performance_prediction_pipeline_end_to_end_local():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=5)
    df_silver = pd.DataFrame(raw_events)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "performance")
        config = PerformanceConfig(output_dir=out_dir)

        report = run_performance_prediction_pipeline(config=config, silver_source=df_silver)

        assert report["total_laps"] == 10
        assert report["total_predictions"] == 10
        assert report["best_model_name"] in [
            "Mean Baseline", "Previous-Lap Baseline", "RandomForestRegressor", "GradientBoostingRegressor"
        ]

        # Verify output Parquet file creation and schema
        pred_file = os.path.join(out_dir, "lap_predictions.parquet")
        assert os.path.exists(pred_file)

        df_pred = pd.read_parquet(pred_file)
        assert len(df_pred) == 10
        assert "lap_id" in df_pred.columns
        assert "actual_lap_time_sec" in df_pred.columns
        assert "predicted_lap_time_sec" in df_pred.columns
        assert "absolute_error_sec" in df_pred.columns
        assert (df_pred["actual_lap_time_sec"] > 0).all()
        assert not df_pred["predicted_lap_time_sec"].isna().any()
