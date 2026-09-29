# -*- coding: utf-8 -*-
"""
Temporal Split Engine for Phase G.4.1 ML Dataset Foundation
Performs chronological temporal partitioning (Train / Validation / Test) without data leakage.
"""

import pandas as pd


def perform_temporal_split(df, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15):
    """
    Splits a telemetry DataFrame strictly by timestamp into Train, Validation, and Test sets.

    STRICT DATA LEAKAGE PREVENTION:
    - Sorts records chronologically by timestamp.
    - TRAIN: Earliest train_ratio fraction of timeline.
    - VALIDATION: Intermediate val_ratio fraction of timeline.
    - TEST: Latest test_ratio fraction of timeline.
    - NO random shuffling or cross-validation mixing across time boundaries.

    Args:
        df (pd.DataFrame): Input ML feature DataFrame.
        train_ratio (float): Fraction of dataset for Train split (default 0.70).
        val_ratio (float): Fraction of dataset for Validation split (default 0.15).
        test_ratio (float): Fraction of dataset for Test split (default 0.15).

    Returns:
        tuple: (df_train: pd.DataFrame, df_val: pd.DataFrame, df_test: pd.DataFrame, split_summary: dict)
    """
    if df.empty:
        empty_df = pd.DataFrame()
        return empty_df, empty_df, empty_df, {
            "total_count": 0,
            "train_count": 0,
            "val_count": 0,
            "test_count": 0
        }

    # Verify ratio sum
    total_ratio = train_ratio + val_ratio + test_ratio
    train_pct = train_ratio / total_ratio
    val_pct = val_ratio / total_ratio

    # Sort strictly chronologically by timestamp
    df_sorted = df.sort_values(by=["timestamp", "event_id"]).reset_index(drop=True)
    n_total = len(df_sorted)

    train_end = int(round(n_total * train_pct))
    val_end = train_end + int(round(n_total * val_pct))

    # Ensure bounds
    train_end = min(n_total, max(1, train_end)) if n_total > 1 else n_total
    val_end = min(n_total, max(train_end, val_end))

    df_train = df_sorted.iloc[:train_end].copy().reset_index(drop=True)
    df_val = df_sorted.iloc[train_end:val_end].copy().reset_index(drop=True)
    df_test = df_sorted.iloc[val_end:].copy().reset_index(drop=True)

    summary = {
        "total_count": n_total,
        "train_count": len(df_train),
        "val_count": len(df_val),
        "test_count": len(df_test),
        "train_min_ts": df_train["timestamp"].min() if not df_train.empty else None,
        "train_max_ts": df_train["timestamp"].max() if not df_train.empty else None,
        "val_min_ts": df_val["timestamp"].min() if not df_val.empty else None,
        "val_max_ts": df_val["timestamp"].max() if not df_val.empty else None,
        "test_min_ts": df_test["timestamp"].min() if not df_test.empty else None,
        "test_max_ts": df_test["timestamp"].max() if not df_test.empty else None,
    }

    return df_train, df_val, df_test, summary
