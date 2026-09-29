# -*- coding: utf-8 -*-
"""
Unit Tests for Anomaly Preprocessing Module (G.4.2)
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.anomaly.preprocessing import AnomalyPreprocessor


@pytest.fixture
def sample_train_df():
    return pd.DataFrame([
        {
            "event_id": f"EVT_{i}",
            "session_id": "SES_01",
            "timestamp": "2026-09-22T10:00:00.000Z",
            "speed_kmh": 280.0 + i,
            "rpm": 11000 + (i * 10),
            "tire_temp_avg": 90.0 + (i * 0.1)
        }
        for i in range(20)
    ])


def test_preprocessor_fit_transform_excludes_identifiers(sample_train_df):
    prep = AnomalyPreprocessor()
    X_scaled = prep.fit_transform(sample_train_df)

    assert prep.is_fitted is True
    assert "event_id" not in prep.fitted_columns
    assert "session_id" not in prep.fitted_columns
    assert "timestamp" not in prep.fitted_columns
    assert "speed_kmh" in prep.fitted_columns
    assert X_scaled.shape == (20, 3)


def test_preprocessor_prevents_transform_before_fit(sample_train_df):
    prep = AnomalyPreprocessor()
    with pytest.raises(RuntimeError):
        prep.transform(sample_train_df)
