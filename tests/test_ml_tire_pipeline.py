# -*- coding: utf-8 -*-
"""
Automated Integration Tests for G.4.4 Tire Degradation Pipeline & Storage
"""

import os
import sys
import tempfile
import json
import pytest
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from data_generator.generator_v2 import SyntheticGeneratorV2
from ml.tire_degradation.config import TireDegradationConfig
from ml.tire_degradation.predictor import run_tire_degradation_pipeline


def test_tire_degradation_pipeline_end_to_end_local():
    gen = SyntheticGeneratorV2(seed=42)
    raw_events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=3)
    df_silver = pd.DataFrame(raw_events)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "tire_degradation")
        config = TireDegradationConfig(output_dir=out_dir, horizon_steps=10)

        report = run_tire_degradation_pipeline(config=config, silver_source=df_silver)

        assert report["total_predictions"] > 0
        assert report["best_model_name"] in [
            "Zero Degradation Baseline", "Previous Degradation Baseline",
            "RandomForestRegressor", "GradientBoostingRegressor"
        ]

        # Verify predictions parquet file exists and has correct schema
        pred_file = os.path.join(out_dir, "tire_degradation_predictions.parquet")
        assert os.path.exists(pred_file)

        df_pred = pd.read_parquet(pred_file)
        assert len(df_pred) == report["total_predictions"]

        expected_cols = [
            "event_id", "session_id", "car_id", "driver_id", "timestamp", "horizon_steps",
            "current_wear_fl", "current_wear_fr", "current_wear_rl", "current_wear_rr",
            "actual_delta_fl", "actual_delta_fr", "actual_delta_rl", "actual_delta_rr",
            "predicted_delta_fl", "predicted_delta_fr", "predicted_delta_rl", "predicted_delta_rr",
            "predicted_wear_fl", "predicted_wear_fr", "predicted_wear_rl", "predicted_wear_rr",
            "model_name", "model_version", "prediction_timestamp"
        ]
        for col in expected_cols:
            assert col in df_pred.columns

        # Verify metrics.json and metadata.json existence
        assert os.path.exists(os.path.join(out_dir, "metrics.json"))
        assert os.path.exists(os.path.join(out_dir, "metadata.json"))

        with open(os.path.join(out_dir, "metrics.json"), "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
            assert "best_model_name" in metrics_data
            assert "physical_validation" in metrics_data

        with open(os.path.join(out_dir, "metadata.json"), "r", encoding="utf-8") as f:
            meta_data = json.load(f)
            assert meta_data["phase"] == "G.4.4"
            assert meta_data["horizon_steps"] == 10
