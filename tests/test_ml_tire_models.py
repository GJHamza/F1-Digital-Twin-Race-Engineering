# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.4 Multi-Output Regression Models, Baselines, and Metrics
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from ml.tire_degradation.baseline import ZeroDegradationBaseline, PreviousDegradationBaseline
from ml.tire_degradation.models import TireDegradationModel
from ml.tire_degradation.evaluation import calculate_tire_metrics, validate_physical_bounds, evaluate_tire_degradation_models


def test_calculate_tire_metrics():
    y_true = np.array([
        [0.01, 0.01, 0.01, 0.01],
        [0.02, 0.02, 0.02, 0.02],
        [0.03, 0.03, 0.03, 0.03]
    ])
    y_pred = np.array([
        [0.01, 0.01, 0.01, 0.01],
        [0.02, 0.02, 0.02, 0.02],
        [0.03, 0.03, 0.03, 0.03]
    ])

    m = calculate_tire_metrics(y_true, y_pred)

    for wheel in ["FL", "FR", "RL", "RR", "GLOBAL"]:
        assert wheel in m
        assert m[wheel]["mae"] == 0.0
        assert m[wheel]["rmse"] == 0.0
        assert m[wheel]["r2"] == 1.0


def test_zero_degradation_baseline():
    X = np.zeros((10, 5))
    model = ZeroDegradationBaseline()
    model.fit(None, None)
    preds = model.predict(X)

    assert preds.shape == (10, 4)
    assert (preds == 0.0).all()


def test_previous_degradation_baseline():
    df = pd.DataFrame({
        "previous_wear_delta_fl": [0.05, 0.06],
        "previous_wear_delta_fr": [0.05, 0.06],
        "previous_wear_delta_rl": [0.04, 0.05],
        "previous_wear_delta_rr": [0.04, 0.05],
    })
    model = PreviousDegradationBaseline(horizon_steps=10)
    model.fit(None, np.zeros((2, 4)))
    preds = model.predict(df)

    assert preds.shape == (2, 4)
    assert np.isclose(preds[0, 0], 0.05)


def test_random_forest_multioutput_reproducibility():
    X_train = np.random.RandomState(42).randn(20, 5)
    y_train = np.random.RandomState(42).uniform(0.01, 0.10, size=(20, 4))

    m1 = TireDegradationModel("random_forest", random_state=42, n_estimators=50)
    m1.fit(X_train, y_train)
    p1 = m1.predict(X_train)

    m2 = TireDegradationModel("random_forest", random_state=42, n_estimators=50)
    m2.fit(X_train, y_train)
    p2 = m2.predict(X_train)

    assert p1.shape == (20, 4)
    assert np.allclose(p1, p2)


def test_gradient_boosting_multioutput_fit_predict():
    X_train = np.random.RandomState(42).randn(20, 5)
    y_train = np.random.RandomState(42).uniform(0.01, 0.10, size=(20, 4))

    model = TireDegradationModel("gradient_boosting", random_state=42, n_estimators=50)
    model.fit(X_train, y_train)
    preds = model.predict(X_train)

    assert preds.shape == (20, 4)
    df_imp = model.get_feature_importances(["f1", "f2", "f3", "f4", "f5"])
    assert len(df_imp) == 5
    assert "importance" in df_imp.columns


def test_physical_bounds_validation():
    df_pred = pd.DataFrame({
        "predicted_delta_fl": [0.05, 0.10],
        "predicted_wear_fl": [10.5, 20.0],
        "predicted_delta_fr": [0.05, 0.10],
        "predicted_wear_fr": [10.5, 20.0],
        "predicted_delta_rl": [0.04, 0.09],
        "predicted_wear_rl": [8.5, 18.0],
        "predicted_delta_rr": [0.04, 0.09],
        "predicted_wear_rr": [8.5, 18.0],
    })
    report = validate_physical_bounds(df_pred)
    assert report["is_physically_valid"] is True
    assert report["out_of_bounds_count"] == 0
