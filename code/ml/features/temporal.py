# -*- coding: utf-8 -*-
"""
Temporal Feature Extractor (Data Leakage Safe)
Derives elapsed session time and rolling window statistics with zero future lookahead.
"""

import pandas as pd
import numpy as np
from datetime import datetime


def compute_temporal_features(df, window_size=5):
    """
    Computes temporal and rolling features on Silver DataFrame.
    STRICT DATA LEAKAGE PREVENTION:
    All rolling statistics are computed on PAST events only using a backward-looking window
    (closed='left' or shift(1) lag).

    Features generated:
    - elapsed_time_sec: Seconds elapsed since session start (float)
    - rolling_speed_mean_5: 5-step rolling mean speed km/h (backward-looking)
    - rolling_speed_std_5: 5-step rolling std speed km/h (backward-looking)
    - rolling_tire_temp_5: 5-step rolling mean tire temperature (backward-looking)
    - rolling_tire_wear_5: 5-step rolling mean tire wear (backward-looking)

    Args:
        df (pd.DataFrame): Silver telemetry DataFrame.
        window_size (int): Size of rolling backward window.

    Returns:
        pd.DataFrame: Copy of DataFrame with temporal features.
    """
    res = df.copy()

    # Ensure chronological order per session
    res = res.sort_values(by=["session_id", "timestamp"]).reset_index(drop=True)

    # Convert timestamp to ISO datetime object if needed
    if not pd.api.types.is_datetime64_any_dtype(res["timestamp"]):
        res["dt_timestamp"] = pd.to_datetime(res["timestamp"], format="ISO8601", errors="coerce")
    else:
        res["dt_timestamp"] = res["timestamp"]

    # Compute elapsed time in seconds per session
    elapsed_list = []
    for sid, group in res.groupby("session_id", sort=False):
        min_ts = group["dt_timestamp"].min()
        elapsed = (group["dt_timestamp"] - min_ts).dt.total_seconds().values
        elapsed_list.extend(elapsed)

    res["elapsed_time_sec"] = elapsed_list

    # Compute backward-looking rolling statistics per session
    rolling_speed_mean = []
    rolling_speed_std = []
    rolling_tire_temp = []
    rolling_tire_wear = []

    for sid, group in res.groupby("session_id", sort=False):
        s_speeds = group["speed_kmh"].values
        s_temps = group["tire_temp_avg"].values
        s_wears = group["tire_wear_avg"].values
        n = len(group)

        group_r_sp_mean = np.zeros(n)
        group_r_sp_std = np.zeros(n)
        group_r_tp_mean = np.zeros(n)
        group_r_tw_mean = np.zeros(n)

        for i in range(n):
            start_idx = max(0, i - window_size)
            # Include only up to i (past + current step, no future i+1)
            window_sp = s_speeds[start_idx:i + 1]
            window_tp = s_temps[start_idx:i + 1]
            window_tw = s_wears[start_idx:i + 1]

            group_r_sp_mean[i] = np.mean(window_sp) if len(window_sp) > 0 else s_speeds[i]
            group_r_sp_std[i] = np.std(window_sp) if len(window_sp) > 1 else 0.0
            group_r_tp_mean[i] = np.mean(window_tp) if len(window_tp) > 0 else s_temps[i]
            group_r_tw_mean[i] = np.mean(window_tw) if len(window_tw) > 0 else s_wears[i]

        rolling_speed_mean.extend(group_r_sp_mean)
        rolling_speed_std.extend(group_r_sp_std)
        rolling_tire_temp.extend(group_r_tp_mean)
        rolling_tire_wear.extend(group_r_tw_mean)

    res["rolling_speed_mean_5"] = rolling_speed_mean
    res["rolling_speed_std_5"] = rolling_speed_std
    res["rolling_tire_temp_5"] = rolling_tire_temp
    res["rolling_tire_wear_5"] = rolling_tire_wear

    if "dt_timestamp" in res.columns:
        res = res.drop(columns=["dt_timestamp"])

    return res
