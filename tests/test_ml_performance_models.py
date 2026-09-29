# -*- coding: utf-8 -*-
"""
Automated Unit Tests for G.4.3 Regression Models, Baselines, and Metrics
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from ml.performance.baseline import MeanBaselineModel, PreviousLapBaselineModel
from ml.performance.models import PerformanceRegressionModel
from ml.performance.evaluation import calculate_metrics, evaluate_regression_models


def test_metrics_calculation():
    y_true = np.array([60.0, 62.0, 58.0, 64.0, 60.0])
    y_pred = np.array([60.0, 61.0, 59.0, 63.0, 60.0])

    m = calculate_metrics(y_true, y_pred)

    assert "mae" in m
    assert "rmse" in m
    assert "r2" in m
    assert "mape" in m
    assert m["mae"] >= 0.0
    assert m["rmse"] >= m["mae"]
    assert m["r2"] <= 1.0


def test_mean_baseline_model():
    y_train = np.array([60.0, 70.0, 80.0])
    model = MeanBaselineModel()
    model.fit(None, y_train)

    preds = model.predict(np.zeros((5, 2)))

    assert len(preds) == 5
    assert (preds == 70.0).all()


def test_previous_lap_baseline_model():
    df = pd.DataFrame({"previous_lap_time_sec": [61.5, 62.0, 59.0]})
    model = PreviousLapBaselineModel()
    model.fit(None, np.array([60.0, 60.0]))

    preds = model.predict(df)

    assert len(preds) == 3
    assert np.isclose(preds[0], 61.5)


def test_random_forest_regressor_reproducibility():
    X_train = np.random.RandomState(42).randn(20, 5)
    y_train = np.random.RandomState(42).uniform(50, 70, size=20)

    model1 = PerformanceRegressionModel("random_forest", random_state=42, n_estimators=50)
    model1.fit(X_train, y_train)
    p1 = model1.predict(X_train)

    model2 = PerformanceRegressionModel("random_forest", random_state=42, n_estimators=50)
    model2.fit(X_train, y_train)
    p2 = model2.predict(X_train)

    assert np.allclose(p1, p2)


def test_gradient_boosting_regressor_fit_predict():
    X_train = np.random.RandomState(42).randn(20, 5)
    y_train = np.random.RandomState(42).uniform(50, 70, size=20)

    model = PerformanceRegressionModel("gradient_boosting", random_state=42, n_estimators=50)
    model.fit(X_train, y_train)
    preds = model.predict(X_train)

    assert len(preds) == 20
    df_imp = model.get_feature_importances(["f1", "f2", "f3", "f4", "f5"])
    assert len(df_imp) == 5
    assert "importance" in df_imp.columns
