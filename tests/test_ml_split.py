# -*- coding: utf-8 -*-
"""
Unit Tests for Temporal Split Engine (G.4.1)
Tests ratio partitioning, strict chronological ordering, and zero data leakage.
"""

import os
import sys
import pytest
import pandas as pd

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.dataset.split import perform_temporal_split


@pytest.fixture
def chronological_df():
    return pd.DataFrame([
        {
            "event_id": f"EVT_SPLIT_{i:04d}",
            "session_id": "SES_SPLIT_01",
            "timestamp": f"2026-09-22T10:{i:02d}:00.000Z",
            "value": float(i)
        }
        for i in range(100)
    ])


def test_temporal_split_proportions(chronological_df):
    train, val, test, summary = perform_temporal_split(chronological_df, 0.70, 0.15, 0.15)
    assert summary["total_count"] == 100
    assert summary["train_count"] == 70
    assert summary["val_count"] == 15
    assert summary["test_count"] == 15


def test_no_temporal_overlap_and_leakage(chronological_df):
    train, val, test, _ = perform_temporal_split(chronological_df, 0.70, 0.15, 0.15)

    max_train_ts = train["timestamp"].max()
    min_val_ts = val["timestamp"].min()
    max_val_ts = val["timestamp"].max()
    min_test_ts = test["timestamp"].min()

    assert max_train_ts <= min_val_ts
    assert max_val_ts <= min_test_ts

    # Verify event set disjointness
    train_ids = set(train["event_id"])
    val_ids = set(val["event_id"])
    test_ids = set(test["event_id"])

    assert len(train_ids.intersection(val_ids)) == 0
    assert len(val_ids.intersection(test_ids)) == 0
    assert len(train_ids.intersection(test_ids)) == 0
