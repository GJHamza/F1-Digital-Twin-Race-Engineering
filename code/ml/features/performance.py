# -*- coding: utf-8 -*-
"""
Performance Feature Extractor
Derives speed, acceleration, and G-force features from telemetry inputs.
"""

import numpy as np
import pandas as pd


def compute_performance_features(df):
    """
    Computes performance engineering features on Silver DataFrame.

    Features generated:
    - speed_kmh: Speed in km/h (float)
    - speed_ms: Speed converted to meters per second (speed_kmh / 3.6)
    - acceleration_estimate: Delta speed_ms per record step grouped by session (m/s^2)
    - g_force: Resultant g-force experienced by vehicle

    Args:
        df (pd.DataFrame): Silver telemetry DataFrame.

    Returns:
        pd.DataFrame: Copy of DataFrame with performance features.
    """
    res = df.copy()

    if "speed_kmh" not in res.columns:
        if "speed" in res.columns:
            res["speed_kmh"] = pd.to_numeric(res["speed"], errors="coerce").fillna(0.0)
        else:
            res["speed_kmh"] = 0.0

    res["speed_ms"] = res["speed_kmh"] / 3.6

    if "g_force" not in res.columns:
        res["g_force"] = 1.0
    else:
        res["g_force"] = pd.to_numeric(res["g_force"], errors="coerce").fillna(1.0)

    # Compute acceleration estimate per session if not already computed
    if "acceleration_estimate" not in res.columns or res["acceleration_estimate"].isna().all():
        res = res.sort_values(by=["session_id", "timestamp"]).reset_index(drop=True)
        accel_list = []
        for sid, group in res.groupby("session_id", sort=False):
            speeds = group["speed_ms"].values
            accels = np.zeros(len(speeds))
            if len(speeds) > 1:
                accels[1:] = np.diff(speeds)
            accel_list.extend(accels)
        res["acceleration_estimate"] = accel_list

    return res
