# -*- coding: utf-8 -*-
"""
Powertrain Feature Extractor
Derives RPM, torque, torque-per-RPM ratio, estimated power output, and fuel metrics.
"""

import pandas as pd


def compute_powertrain_features(df):
    """
    Computes powertrain engineering features on Silver DataFrame.

    Features generated:
    - rpm: Engine revolutions per minute (RPM)
    - torque: Engine torque output (Nm)
    - torque_per_rpm: Ratio torque / (rpm + 1.0)
    - estimated_power_kw: Estimated engine power output in kW: (torque * rpm) / 9548.8
    - fuel_level: Current fuel mass (kg)
    - fuel_remaining_pct: Percentage fuel remaining relative to 110 kg capacity (%)

    Args:
        df (pd.DataFrame): Silver telemetry DataFrame.

    Returns:
        pd.DataFrame: Copy of DataFrame with powertrain features.
    """
    res = df.copy()

    for col, default_val in [("rpm", 0.0), ("torque", 0.0), ("fuel_level", 0.0)]:
        if col not in res.columns:
            res[col] = default_val
        else:
            res[col] = pd.to_numeric(res[col], errors="coerce").fillna(default_val)

    res["torque_per_rpm"] = res["torque"] / (res["rpm"] + 1.0)
    res["estimated_power_kw"] = (res["torque"] * res["rpm"]) / 9548.8

    res["fuel_remaining_pct"] = (res["fuel_level"] / 110.0) * 100.0

    return res
