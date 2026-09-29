# -*- coding: utf-8 -*-
"""
Unit Tests for Z-Score Baseline Detector (G.4.2)
"""

import os
import sys
import pytest
import numpy as np

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.anomaly.baseline import ZScoreBaselineDetector


def test_baseline_detector_fit_and_score():
    # Normal data centered around 0 with std 1
    np.random.seed(42)
    X_train = np.random.normal(0, 1, (100, 3))

    detector = ZScoreBaselineDetector(z_threshold=3.0)
    detector.fit(X_train)

    assert detector.is_fitted is True

    # Test sample with normal values vs massive outlier
    X_test = np.array([
        [0.1, -0.2, 0.5],   # Normal sample
        [10.0, 0.0, 0.0]    # Outlier (10 std devs away)
    ])

    scores = detector.predict_score(X_test)
    labels = detector.predict_label(X_test)

    assert scores[0] < 3.0
    assert labels[0] == 0

    assert scores[1] > 3.0
    assert labels[1] == 1
