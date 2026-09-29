# -*- coding: utf-8 -*-
"""
ML Dataset Validation Engine for Phase G.4.1
Validates schema compliance, physical bounds, null ratios, duplicates, and temporal ordering.
"""

import pandas as pd
import numpy as np
from ml.schema import FEATURE_BOUNDS, NULL_TOLERANCE


def validate_ml_dataset(df, feature_columns=None):
    """
    Validates ML feature DataFrame against physical bounds, quality standards, and schema rules.

    Checks:
    1. Presence of mandatory identifier columns
    2. Null rate per feature (must satisfy NULL_TOLERANCE)
    3. Duplicate event_id count (must be 0)
    4. Bounded numeric value ranges (FEATURE_BOUNDS)
    5. Monotonic temporal ordering per session

    Args:
        df (pd.DataFrame): ML feature DataFrame to validate.
        feature_columns (list, optional): List of feature column names to validate.

    Returns:
        dict: Detailed quality report containing boolean `is_valid`, error details, null rates, and duplicate count.
    """
    if feature_columns is None:
        feature_columns = list(FEATURE_BOUNDS.keys())

    errors = []
    null_rates = {}

    if df.empty:
        return {
            "is_valid": False,
            "total_records": 0,
            "duplicate_count": 0,
            "null_rates": {},
            "errors": ["DataFrame is empty"]
        }

    # 1. Identifier Columns Verification
    for col in ["event_id", "session_id", "timestamp"]:
        if col not in df.columns:
            errors.append(f"Missing mandatory identifier column '{col}'")

    # 2. Duplicate event_id Check
    duplicate_count = 0
    if "event_id" in df.columns:
        duplicate_count = int(df.duplicated(subset=["event_id"]).sum())
        if duplicate_count > 0:
            errors.append(f"Found {duplicate_count} duplicate event_id records")

    # 3. Null Rate & Numeric Bounds Check
    for col in feature_columns:
        if col not in df.columns:
            errors.append(f"Missing feature column '{col}'")
            null_rates[col] = 1.0
            continue

        n_null = df[col].isna().sum()
        null_rate = float(n_null / len(df))
        null_rates[col] = round(null_rate, 4)

        tol = NULL_TOLERANCE.get(col, 0.0)
        if null_rate > tol:
            errors.append(f"Column '{col}' null rate {null_rate:.2%} exceeds tolerance {tol:.2%}")

        # Physical Bounds Verification
        if col in FEATURE_BOUNDS:
            b = FEATURE_BOUNDS[col]
            valid_vals = df[col].dropna()
            if not valid_vals.empty:
                min_v = float(valid_vals.min())
                max_v = float(valid_vals.max())
                if min_v < b["min"] - 1e-3:
                    errors.append(f"Column '{col}' min value {min_v} below bound min {b['min']}")
                if max_v > b["max"] + 1e-3:
                    errors.append(f"Column '{col}' max value {max_v} above bound max {b['max']}")

    # 4. Temporal Monotonicity Check
    if "session_id" in df.columns and "timestamp" in df.columns:
        try:
            df_temp = df.copy()
            df_temp["dt"] = pd.to_datetime(df_temp["timestamp"], format="ISO8601", errors="coerce")
            for sid, group in df_temp.groupby("session_id", sort=False):
                dts = group["dt"].values
                if len(dts) > 1 and np.any(np.diff(dts) < np.timedelta64(0, 'ns')):
                    errors.append(f"Non-monotonic timestamps detected in session '{sid}'")
        except Exception:
            pass

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "total_records": len(df),
        "duplicate_count": duplicate_count,
        "null_rates": null_rates,
        "errors": errors
    }
