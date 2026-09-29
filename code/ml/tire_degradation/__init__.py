# -*- coding: utf-8 -*-
"""
ML Tire Degradation Package for Phase G.4.4: Tire Degradation Modeling.
Provides telemetry inspection, future wear delta target construction (horizon H=10),
four-wheel (FL, FR, RL, RR) feature engineering, temporal splitting, baseline/ML regression models,
evaluation metrics, physical constraint checks, and Parquet/JSON exports.
"""

from ml.tire_degradation.config import TireDegradationConfig
from ml.tire_degradation.inspection import inspect_tire_telemetry
from ml.tire_degradation.dataset import construct_tire_degradation_dataset
from ml.tire_degradation.features import compute_tire_degradation_features
from ml.tire_degradation.preprocessing import prepare_tire_degradation_dataset
from ml.tire_degradation.baseline import ZeroDegradationBaseline, PreviousDegradationBaseline
from ml.tire_degradation.models import TireDegradationModel
from ml.tire_degradation.evaluation import evaluate_tire_degradation_models, validate_physical_bounds
from ml.tire_degradation.predictor import run_tire_degradation_pipeline

__all__ = [
    "TireDegradationConfig",
    "inspect_tire_telemetry",
    "construct_tire_degradation_dataset",
    "compute_tire_degradation_features",
    "prepare_tire_degradation_dataset",
    "ZeroDegradationBaseline",
    "PreviousDegradationBaseline",
    "TireDegradationModel",
    "evaluate_tire_degradation_models",
    "validate_physical_bounds",
    "run_tire_degradation_pipeline",
]
