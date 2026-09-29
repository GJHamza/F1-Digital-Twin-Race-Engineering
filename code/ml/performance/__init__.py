# -*- coding: utf-8 -*-
"""
ML Performance Prediction Package for Phase G.4.3: Lap Time / Performance Prediction.
Provides end-to-end target construction, feature engineering, temporal splitting,
baseline/ML regression models, metric evaluation, and output export.
"""

from ml.performance.config import PerformanceConfig
from ml.performance.target import construct_lap_target_dataset
from ml.performance.features import compute_pre_lap_features
from ml.performance.preprocessing import prepare_performance_dataset
from ml.performance.baseline import MeanBaselineModel, PreviousLapBaselineModel
from ml.performance.models import PerformanceRegressionModel
from ml.performance.evaluation import evaluate_regression_models
from ml.performance.predictor import run_performance_prediction_pipeline

__all__ = [
    "PerformanceConfig",
    "construct_lap_target_dataset",
    "compute_pre_lap_features",
    "prepare_performance_dataset",
    "MeanBaselineModel",
    "PreviousLapBaselineModel",
    "PerformanceRegressionModel",
    "evaluate_regression_models",
    "run_performance_prediction_pipeline",
]
