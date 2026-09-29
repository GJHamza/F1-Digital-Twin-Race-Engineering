# -*- coding: utf-8 -*-
"""
Aerodynamics Feature Extractor
Derives downforce, drag coefficient, wind speed, aero efficiency, and downforce-per-speed features.
"""

import pandas as pd


def compute_aerodynamic_features(df):
    """
    Computes aerodynamic engineering features on Silver DataFrame.

    Features generated:
    - downforce: Downforce generated (N)
    - drag_coefficient: Aerodynamic drag coefficient Cd
    - wind_speed: Ambient wind speed (km/h)
    - aero_efficiency: Ratio downforce / ((speed_ms^2)*drag_coefficient + 1e-5)
    - downforce_per_speed: Ratio downforce / (speed_ms + 1e-5)

    Args:
        df (pd.DataFrame): Silver telemetry DataFrame.

    Returns:
        pd.DataFrame: Copy of DataFrame with aerodynamic features.
    """
    res = df.copy()

    for col, default_val in [("downforce", 0.0), ("drag_coefficient", 0.35), ("wind_speed", 0.0)]:
        if col not in res.columns:
            res[col] = default_val
        else:
            res[col] = pd.to_numeric(res[col], errors="coerce").fillna(default_val)

    speed_ms = res["speed_ms"] if "speed_ms" in res.columns else res["speed_kmh"] / 3.6

    if "aero_efficiency" not in res.columns:
        res["aero_efficiency"] = res["downforce"] / (
            (speed_ms ** 2) * res["drag_coefficient"] + 1e-5
        )

    res["downforce_per_speed"] = res["downforce"] / (speed_ms + 1e-5)

    return res
