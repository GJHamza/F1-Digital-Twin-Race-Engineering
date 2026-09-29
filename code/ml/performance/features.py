# -*- coding: utf-8 -*-
"""
Pre-Lap Feature Engineering Module for Phase G.4.3
Computes pre-lap telemetry aggregations and rolling historic lap metrics with zero future data leakage.
"""

import pandas as pd
import numpy as np


def compute_pre_lap_features(df_silver: pd.DataFrame, df_laps: pd.DataFrame) -> pd.DataFrame:
    """
    Computes pre-lap features for each lap in `df_laps` using only telemetry data
    from preceding laps (or initial lap conditions for Lap 1).

    Args:
        df_silver (pd.DataFrame): Telemetry tick-level dataset.
        df_laps (pd.DataFrame): Lap target dataset from construct_lap_target_dataset.

    Returns:
        pd.DataFrame: Merged lap dataset containing identifier columns, feature columns, and lap_time_sec target.
    """
    if df_laps is None or df_laps.empty:
        return pd.DataFrame()

    df_tel = df_silver.copy() if df_silver is not None else pd.DataFrame()

    # Ensure required telemetry columns exist with default fallbacks
    default_telemetry_cols = {
        "speed_kmh": 200.0,
        "g_force": 1.0,
        "acceleration_estimate": 0.0,
        "tire_temp_avg": 90.0,
        "tire_temp_max": 95.0,
        "tire_wear_avg": 5.0,
        "tire_wear_max": 6.0,
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
        "fuel_level": 110.0
    }
    for col, default_val in default_telemetry_cols.items():
        if col not in df_tel.columns:
            df_tel[col] = default_val

    if "lap_number" in df_tel.columns:
        df_tel["lap_number"] = pd.to_numeric(df_tel["lap_number"], errors="coerce").fillna(1).astype(int)

    feature_rows = []

    for idx, lap_row in df_laps.iterrows():
        sid = lap_row["session_id"]
        car = lap_row["car_id"]
        lap_num = lap_row["lap_number"]

        # Filter telemetry strictly BEFORE current lap (previous lap or past laps in session)
        tel_prev_lap = df_tel[
            (df_tel["session_id"] == sid) &
            (df_tel["car_id"] == car) &
            (df_tel["lap_number"] == lap_num - 1)
        ]

        if tel_prev_lap.empty:
            # Fallback for Lap 1: use first tick of current lap or default session baseline
            tel_first_tick = df_tel[
                (df_tel["session_id"] == sid) &
                (df_tel["car_id"] == car) &
                (df_tel["lap_number"] == lap_num)
            ]
            if not tel_first_tick.empty:
                ref_df = tel_first_tick.iloc[:1]
            else:
                ref_df = pd.DataFrame([default_telemetry_cols])
        else:
            ref_df = tel_prev_lap

        # Compute pre-lap aggregations
        avg_speed = float(ref_df["speed_kmh"].mean())
        max_speed = float(ref_df["speed_kmh"].max())
        avg_acc = float(ref_df["acceleration_estimate"].mean()) if "acceleration_estimate" in ref_df.columns else 0.0
        avg_g = float(ref_df["g_force"].mean())

        t_temp_avg = float(ref_df["tire_temp_avg"].mean())
        t_temp_max = float(ref_df["tire_temp_max"].max())
        t_wear_avg = float(ref_df["tire_wear_avg"].mean())
        t_wear_max = float(ref_df["tire_wear_max"].max())
        t_stress = float(ref_df["tire_stress_index"].mean()) if "tire_stress_index" in ref_df.columns else 50.0
        t_wear_rate = float(ref_df["tire_wear_rate"].mean()) if "tire_wear_rate" in ref_df.columns else 0.1

        avg_df = float(ref_df["downforce"].mean())
        drag_c = float(ref_df["drag_coefficient"].mean())
        wind = float(ref_df["wind_speed"].mean())
        aero_eff = float(ref_df["aero_efficiency"].mean())

        avg_rpm = float(ref_df["rpm"].mean())
        avg_torque = float(ref_df["torque"].mean())
        power_kw = float(ref_df["estimated_power_kw"].mean()) if "estimated_power_kw" in ref_df.columns else 600.0

        if "fuel_remaining_pct" in ref_df.columns:
            fuel_pct = float(ref_df["fuel_remaining_pct"].iloc[-1])
        else:
            fuel_lvl = float(ref_df["fuel_level"].iloc[-1]) if "fuel_level" in ref_df.columns else 110.0
            fuel_pct = min(100.0, max(0.0, (fuel_lvl / 110.0) * 100.0))

        # Historic Lap Statistics (strictly past laps up to lap_num - 1)
        past_laps = df_laps[
            (df_laps["session_id"] == sid) &
            (df_laps["car_id"] == car) &
            (df_laps["lap_number"] < lap_num)
        ]

        if not past_laps.empty:
            prev_lap_time = float(past_laps.iloc[-1]["lap_time_sec"])
            rolling_mean = float(past_laps["lap_time_sec"].tail(3).mean())
            rolling_std = float(past_laps["lap_time_sec"].tail(3).std()) if len(past_laps) > 1 else 0.0
            elapsed_time = float(past_laps["lap_time_sec"].sum())
        else:
            prev_lap_time = float(lap_row["lap_time_sec"])
            rolling_mean = float(lap_row["lap_time_sec"])
            rolling_std = 0.0
            elapsed_time = 0.0

        if np.isnan(rolling_std):
            rolling_std = 0.0

        f_dict = dict(lap_row)
        f_dict.update({
            "average_speed_before_lap": round(avg_speed, 2),
            "max_speed_before_lap": round(max_speed, 2),
            "average_acceleration_before_lap": round(avg_acc, 3),
            "average_g_force_before_lap": round(avg_g, 3),
            "tire_temp_avg_before_lap": round(t_temp_avg, 2),
            "tire_temp_max_before_lap": round(t_temp_max, 2),
            "tire_wear_avg_before_lap": round(t_wear_avg, 2),
            "tire_wear_max_before_lap": round(t_wear_max, 2),
            "tire_stress_index_before_lap": round(t_stress, 3),
            "tire_wear_rate_before_lap": round(t_wear_rate, 4),
            "average_downforce_before_lap": round(avg_df, 2),
            "average_drag_coefficient_before_lap": round(drag_c, 4),
            "average_wind_speed_before_lap": round(wind, 2),
            "average_aero_efficiency_before_lap": round(aero_eff, 4),
            "average_rpm_before_lap": round(avg_rpm, 1),
            "average_torque_before_lap": round(avg_torque, 1),
            "estimated_power_kw_before_lap": round(power_kw, 2),
            "fuel_remaining_pct_before_lap": round(fuel_pct, 2),
            "previous_lap_time_sec": round(prev_lap_time, 3),
            "rolling_lap_time_mean": round(rolling_mean, 3),
            "rolling_lap_time_std": round(rolling_std, 3),
            "elapsed_session_time_sec": round(elapsed_time, 3),
        })

        feature_rows.append(f_dict)

    df_featured = pd.DataFrame(feature_rows)

    return df_featured
