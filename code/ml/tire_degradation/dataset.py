# -*- coding: utf-8 -*-
"""
Supervised Dataset Construction Module for Phase G.4.4 Tire Degradation Modeling
Pairs current observation t with future observation t+H within session boundaries
to calculate multi-wheel targets: future_wear_delta_fl, fr, rl, rr.
"""

import pandas as pd
import numpy as np


def parse_wheel_arrays(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parses array fields (`tire_wear`, `tire_temp`) into explicit wheel columns:
    fl (0), fr (1), rl (2), rr (3).

    Args:
        df (pd.DataFrame): Input telemetry DataFrame.

    Returns:
        pd.DataFrame: DataFrame enriched with explicit per-wheel columns.
    """
    df_out = df.copy()

    # Parse tire_wear array if present
    if "tire_wear" in df_out.columns:
        w_arr = df_out["tire_wear"].apply(
            lambda x: x if isinstance(x, (list, np.ndarray, tuple)) and len(x) == 4 else [0.0, 0.0, 0.0, 0.0]
        )
        df_out["tire_wear_fl"] = [float(w[0]) for w in w_arr]
        df_out["tire_wear_fr"] = [float(w[1]) for w in w_arr]
        df_out["tire_wear_rl"] = [float(w[2]) for w in w_arr]
        df_out["tire_wear_rr"] = [float(w[3]) for w in w_arr]
    else:
        for pos in ["fl", "fr", "rl", "rr"]:
            if f"tire_wear_{pos}" not in df_out.columns:
                df_out[f"tire_wear_{pos}"] = 0.0

    # Parse tire_temp array if present
    if "tire_temp" in df_out.columns:
        t_arr = df_out["tire_temp"].apply(
            lambda x: x if isinstance(x, (list, np.ndarray, tuple)) and len(x) == 4 else [100.0, 100.0, 100.0, 100.0]
        )
        df_out["tire_temp_fl"] = [float(t[0]) for t in t_arr]
        df_out["tire_temp_fr"] = [float(t[1]) for t in t_arr]
        df_out["tire_temp_rl"] = [float(t[2]) for t in t_arr]
        df_out["tire_temp_rr"] = [float(t[3]) for t in t_arr]
    else:
        for pos in ["fl", "fr", "rl", "rr"]:
            if f"tire_temp_{pos}" not in df_out.columns:
                df_out[f"tire_temp_{pos}"] = 100.0

    # Aggregate wear/temp metrics
    wear_cols = ["tire_wear_fl", "tire_wear_fr", "tire_wear_rl", "tire_wear_rr"]
    temp_cols = ["tire_temp_fl", "tire_temp_fr", "tire_temp_rl", "tire_temp_rr"]

    df_out["tire_wear_avg"] = df_out[wear_cols].mean(axis=1)
    df_out["tire_wear_max"] = df_out[wear_cols].max(axis=1)
    df_out["tire_temp_avg"] = df_out[temp_cols].mean(axis=1)
    df_out["tire_temp_max"] = df_out[temp_cols].max(axis=1)

    return df_out


def construct_tire_degradation_dataset(df_silver: pd.DataFrame, horizon_steps: int = 10) -> tuple:
    """
    Constructs the supervised dataset for tire degradation over horizon H.
    Pairs observation t with observation t + H within the same session/car run.

    Args:
        df_silver (pd.DataFrame): Silver telemetry dataset.
        horizon_steps (int): Future step offset H (default 10).

    Returns:
        tuple: (df_supervised, summary_dict)
    """
    if df_silver is None or df_silver.empty:
        return pd.DataFrame(), {
            "total_records_input": 0,
            "supervised_samples": 0,
            "excluded_tail_samples": 0,
            "horizon_steps": horizon_steps
        }

    df_parsed = parse_wheel_arrays(df_silver)

    # Group by session_id, car_id to prevent horizon from crossing sessions
    supervised_rows = []
    total_excluded = 0

    group_cols = [c for c in ["session_id", "car_id"] if c in df_parsed.columns]
    if group_cols:
        grouped = df_parsed.groupby(group_cols, sort=False)
    else:
        grouped = [("SINGLE_SESSION", df_parsed)]

    wheel_positions = ["fl", "fr", "rl", "rr"]

    for _, group in grouped:
        group_sorted = group.sort_values(by="timestamp").reset_index(drop=True)
        n = len(group_sorted)

        if n <= horizon_steps:
            total_excluded += n
            continue

        n_valid = n - horizon_steps
        total_excluded += horizon_steps

        for i in range(n_valid):
            row_t = group_sorted.iloc[i].to_dict()
            row_fut = group_sorted.iloc[i + horizon_steps]

            row_dict = dict(row_t)
            row_dict["horizon_steps"] = horizon_steps
            row_dict["future_timestamp"] = row_fut["timestamp"]

            # Compute future wear and deltas for all 4 wheels
            for pos in wheel_positions:
                curr_w = float(row_t[f"tire_wear_{pos}"])
                fut_w = float(row_fut[f"tire_wear_{pos}"])
                delta_w = round(fut_w - curr_w, 4)

                row_dict[f"future_wear_{pos}"] = fut_w
                row_dict[f"future_wear_delta_{pos}"] = delta_w

            supervised_rows.append(row_dict)

    df_supervised = pd.DataFrame(supervised_rows)

    if not df_supervised.empty:
        df_supervised = df_supervised.sort_values(by=["session_id", "timestamp"] if "session_id" in df_supervised.columns else ["timestamp"]).reset_index(drop=True)

    summary = {
        "total_records_input": len(df_silver),
        "supervised_samples": len(df_supervised),
        "excluded_tail_samples": total_excluded,
        "horizon_steps": horizon_steps
    }

    return df_supervised, summary
