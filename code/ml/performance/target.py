# -*- coding: utf-8 -*-
"""
Lap Target Construction Module for Phase G.4.3
Extracts lap-level records and calculates deterministic lap_time_sec targets from Silver telemetry.
"""

import pandas as pd
import numpy as np


def construct_lap_target_dataset(df_silver) -> pd.DataFrame:
    """
    Groups tick-level Silver telemetry events by session, car, and lap number,
    and computes the target metric `lap_time_sec` (> 0) along with timestamps and identifiers.

    Args:
        df_silver (pd.DataFrame or list): Silver telemetry records.

    Returns:
        pd.DataFrame: Supervised lap target dataset sorted chronologically.
    """
    if df_silver is None:
        return pd.DataFrame(columns=[
            "lap_id", "session_id", "car_id", "driver_id",
            "lap_number", "lap_start_timestamp", "lap_end_timestamp", "lap_time_sec"
        ])

    if isinstance(df_silver, list):
        df_silver = pd.DataFrame(df_silver)
    elif isinstance(df_silver, dict) or not isinstance(df_silver, pd.DataFrame):
        return pd.DataFrame(columns=[
            "lap_id", "session_id", "car_id", "driver_id",
            "lap_number", "lap_start_timestamp", "lap_end_timestamp", "lap_time_sec"
        ])

    if df_silver.empty:
        return pd.DataFrame(columns=[
            "lap_id", "session_id", "car_id", "driver_id",
            "lap_number", "lap_start_timestamp", "lap_end_timestamp", "lap_time_sec"
        ])

    df = df_silver.copy()

    # Ensure required grouping and timestamp columns exist
    for col in ["session_id", "car_id", "driver_id", "lap_number", "timestamp"]:
        if col not in df.columns:
            if col == "driver_id":
                df["driver_id"] = "SIM-DRV-01"
            elif col == "lap_number":
                df["lap_number"] = 1
            else:
                raise KeyError(f"Required column '{col}' missing from telemetry dataset.")

    # Convert lap_number to integer
    df["lap_number"] = pd.to_numeric(df["lap_number"], errors="coerce").fillna(1).astype(int)

    # Parse timestamp as datetime
    df["ts_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Group by session_id, car_id, lap_number
    lap_rows = []
    grouped = df.groupby(["session_id", "car_id", "lap_number"], sort=False)

    for (session_id, car_id, lap_num), group in grouped:
        driver_id = str(group["driver_id"].iloc[0]) if "driver_id" in group.columns else "SIM-DRV-01"
        
        ts_valid = group["ts_dt"].dropna()
        if not ts_valid.empty:
            t_min = ts_valid.min()
            t_max = ts_valid.max()
            start_ts = str(group["timestamp"].iloc[0])
            end_ts = str(group["timestamp"].iloc[-1])
            duration_sec = (t_max - t_min).total_seconds()
            if duration_sec <= 0:
                duration_sec = float(len(group))
        else:
            start_ts = "1970-01-01T00:00:00.000Z"
            end_ts = "1970-01-01T00:00:00.000Z"
            duration_sec = float(len(group))

        lap_id = f"{session_id}_{car_id}_L{lap_num:02d}"

        lap_rows.append({
            "lap_id": lap_id,
            "session_id": session_id,
            "car_id": car_id,
            "driver_id": driver_id,
            "lap_number": int(lap_num),
            "lap_start_timestamp": start_ts,
            "lap_end_timestamp": end_ts,
            "lap_time_sec": round(float(duration_sec), 3)
        })

    df_laps = pd.DataFrame(lap_rows)

    # Sort strictly by session_id, car_id, lap_number
    if not df_laps.empty:
        df_laps = df_laps.sort_values(by=["session_id", "car_id", "lap_number"]).reset_index(drop=True)

        # Quality check on lap_time_sec
        assert (df_laps["lap_time_sec"] > 0).all(), "Error: Found lap_time_sec <= 0"
        assert not df_laps["lap_time_sec"].isna().any(), "Error: Found NaN in lap_time_sec"

    return df_laps
