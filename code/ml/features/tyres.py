# -*- coding: utf-8 -*-
"""
Tyres Feature Extractor
Derives tire temperature, tire wear, stress index, and wear rate features.
"""

import numpy as np
import pandas as pd


def compute_tyre_features(df):
    """
    Computes tyre engineering features on Silver DataFrame.

    Features generated:
    - tire_temp_avg: Average tire temperature across 4 tires (°C)
    - tire_temp_max: Maximum tire temperature among 4 tires (°C)
    - tire_wear_avg: Average tire wear percentage (%)
    - tire_wear_max: Maximum tire wear percentage (%)
    - tire_stress_index: Dimensionless stress index: (temp_avg / 100) * (1 + wear_avg / 100) * speed_ms
    - tire_wear_rate: Rate of wear progression per event step (%/step)

    Args:
        df (pd.DataFrame): Silver telemetry DataFrame.

    Returns:
        pd.DataFrame: Copy of DataFrame with tyre features.
    """
    res = df.copy()

    for col in ["tire_temp_avg", "tire_temp_max", "tire_wear_avg", "tire_wear_max"]:
        if col not in res.columns:
            res[col] = 0.0

    if "tire_stress_index" not in res.columns:
        speed_ms = res["speed_ms"] if "speed_ms" in res.columns else res["speed_kmh"] / 3.6
        res["tire_stress_index"] = (
            (res["tire_temp_avg"] / 100.0) *
            (1.0 + res["tire_wear_avg"] / 100.0) *
            speed_ms
        )

    # Compute tire wear rate per session
    res = res.sort_values(by=["session_id", "timestamp"]).reset_index(drop=True)
    wear_rates = []
    for sid, group in res.groupby("session_id", sort=False):
        wears = group["tire_wear_avg"].values
        rates = np.zeros(len(wears))
        if len(wears) > 1:
            rates[1:] = np.maximum(0.0, np.diff(wears))
        wear_rates.extend(rates)
    res["tire_wear_rate"] = wear_rates

    return res
