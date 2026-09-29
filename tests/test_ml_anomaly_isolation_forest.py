# -*- coding: utf-8 -*-
"""
Unit Tests for Isolation Forest Detector & Scoring (G.4.2)
"""

import os
import sys
import pytest
import numpy as np

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.anomaly.isolation_forest import IsolationForestDetector
from ml.anomaly.scoring import AnomalyScoreCalibrator


def test_isolation_forest_reproducibility_and_predictions():
    np.random.seed(42)
    X_train = np.random.normal(0, 1, (200, 4))

    # Add artificial extreme outlier
    X_train[199] = [20.0, 20.0, 20.0, 20.0]

    detector1 = IsolationForestDetector(random_state=42)
    detector1.fit(X_train)

    detector2 = IsolationForestDetector(random_state=42)
    detector2.fit(X_train)

    raw_scores1 = detector1.decision_function(X_train)
    raw_scores2 = detector2.decision_function(X_train)

    np.testing.assert_allclose(raw_scores1, raw_scores2)

    preds = detector1.predict(X_train)
    assert preds[199] == 1  # Extreme outlier detected as anomaly


def test_anomaly_score_calibrator_severity_mapping():
    raw_scores_val = np.linspace(1.0, -1.0, 100)  # Inverted: smaller/negative = more anomalous

    calibrator = AnomalyScoreCalibrator()
    calibrator.calibrate(raw_scores_val)

    norm_scores = calibrator.score(raw_scores_val)
    severities = calibrator.map_severity(norm_scores)

    assert norm_scores.min() == 0.0
    assert norm_scores.max() == 1.0
    assert "NORMAL" in severities
    assert "HIGH" in severities
