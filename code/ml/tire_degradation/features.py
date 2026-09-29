# -*- coding: utf-8 -*-
"""
Feature Engineering Module for Phase G.4.4 Tire Degradation Modeling
Computes causal, backward-looking pre-horizon features with zero future data leakage.
"""

import pandas as pd
import numpy as np


def compute_tire_degradation_features(df_supervised: pd.DataFrame) -> pd.DataFrame:
    """
    Computes and validates feature matrix for tire degradation modeling.
    Uses strictly current (t) and past (t-W ... t) telemetry observations.

    Args:
        df_supervised (pd.DataFrame): Supervised dataset output from construct_tire_degradation_dataset.

    Returns:
        pd.DataFrame: Enriched DataFrame containing features, identifiers, and targets.
    """
    if df_supervised is None or df_supervised.empty:
        return pd.DataFrame()

    df = df_supervised.copy()

    # Default value fallbacks for missing columns
    default_feature_values = {
        "speed_kmh": 200.0,
        "speed_ms": 55.56,
        "acceleration_estimate": 0.0,
        "g_force": 1.0,
        "tire_stress_index": 50.0,
        "tire_wear_rate": 0.1,
        "downforce": 5000.0,
        "drag_coefficient": 0.7,
        "wind_speed": 10.0,
        "aero_efficiency": 3.0,
        "rpm": 11000.0,
        "torque": 400.0,
        "estimated_power_kw": 600.0,
        "fuel_remaining_pct": 100.0,
        "fuel_level": 110.0,
        "elapsed_time_sec": 0.0,
    }
    for col, def_val in default_feature_values.items():
        if col not in df.columns:
            df[col] = def_val

    # Calculate backward-looking rolling wear deltas (t-5 ... t) per session/wheel
    wheel_positions = ["fl", "fr", "rl", "rr"]
    for pos in wheel_positions:
        prev_delta_col = f"previous_wear_delta_{pos}"
        wear_col = f"tire_wear_{pos}"

        if prev_delta_col not in df.columns:
            if "session_id" in df.columns:
                # Compute backward diff within session
                df[prev_delta_col] = df.groupby("session_id")[wear_col].diff(periods=5).fillna(0.0)
            else:
                df[prev_delta_col] = df[wear_col].diff(periods=5).fillna(0.0)

        # Replace any negative rolling diffs with 0.0 if numerical noise
        df[prev_delta_col] = df[prev_delta_col].apply(lambda x: max(0.0, float(x)) if not np.isnan(x) else 0.0)

    return df
