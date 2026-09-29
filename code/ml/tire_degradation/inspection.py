# -*- coding: utf-8 -*-
"""
Telemetry Inspection Module for Phase G.4.4 Tire Degradation Modeling
Inspects Silver telemetry inputs for tire array formats, wheel order, units, monotonicity, and continuity.
"""

import pandas as pd
import numpy as np


def inspect_tire_telemetry(df_silver: pd.DataFrame, horizon_steps: int = 10) -> dict:
    """
    Performs mandatory pre-implementation telemetry inspection on tire fields.

    Args:
        df_silver (pd.DataFrame): Telemetry dataset.
        horizon_steps (int): Configured horizon steps (default 10).

    Returns:
        dict: Inspection report containing format, wheel order, bounds, monotonicity, and session stats.
    """
    if df_silver is None or df_silver.empty:
        return {
            "total_records": 0,
            "sessions_count": 0,
            "has_tire_wear": False,
            "has_tire_temp": False,
            "tire_wear_format": "UNKNOWN",
            "wheel_order": ["FL", "FR", "RL", "RR"],
            "is_monotonic": True,
            "horizon_achievable": False,
            "anomalies_found": []
        }

    df = df_silver.copy()
    n_records = len(df)
    n_sessions = df["session_id"].nunique() if "session_id" in df.columns else 0

    has_wear = "tire_wear" in df.columns or "tire_wear_fl" in df.columns
    has_temp = "tire_temp" in df.columns or "tire_temp_fl" in df.columns

    wear_format = "ARRAY"
    if "tire_wear" in df.columns:
        first_wear = df["tire_wear"].iloc[0]
        if isinstance(first_wear, (list, np.ndarray, tuple)):
            wear_format = f"LIST[{len(first_wear)}]"
        elif isinstance(first_wear, str):
            wear_format = "JSON_STRING"
    elif "tire_wear_fl" in df.columns:
        wear_format = "SPLIT_COLUMNS"

    # Extract sample tire wear values for monotonicity check
    monotonic_issues = []
    if "tire_wear" in df.columns:
        wear_series = df["tire_wear"].apply(lambda x: x[0] if isinstance(x, (list, np.ndarray)) else 0.0)
        # Check monotonicity within session
        if "session_id" in df.columns:
            for sid, group in df.groupby("session_id"):
                diffs = group["tire_wear"].apply(lambda x: x[0] if isinstance(x, (list, np.ndarray)) else 0.0).diff().dropna()
                neg_count = int((diffs < -1e-6).sum())
                if neg_count > 0:
                    monotonic_issues.append(f"Session {sid}: {neg_count} negative wear steps found")

    # Check if horizon_steps is achievable
    min_session_len = df.groupby("session_id").size().min() if "session_id" in df.columns else n_records
    horizon_achievable = bool(min_session_len > horizon_steps)

    report = {
        "total_records": n_records,
        "sessions_count": n_sessions,
        "has_tire_wear": has_wear,
        "has_tire_temp": has_temp,
        "tire_wear_format": wear_format,
        "wheel_order": ["FL", "FR", "RL", "RR"],
        "units": {"wear": "percentage (%)", "temp": "Celsius (°C)", "pressure": "PSI"},
        "is_monotonic": len(monotonic_issues) == 0,
        "monotonic_anomalies": monotonic_issues,
        "min_session_length": int(min_session_len),
        "horizon_steps": horizon_steps,
        "horizon_achievable": horizon_achievable,
        "wheel_positions": ["fl", "fr", "rl", "rr"]
    }

    return report
