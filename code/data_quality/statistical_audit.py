# -*- coding: utf-8 -*-
"""
Statistical Audit & Correlation Module for F1 Synthetic Telemetry Generator V2
"""

import math
import os
import pandas as pd
import numpy as np


def extract_numeric_dataframe(events):
    """Converts a list of telemetry event dictionaries into a flat Pandas DataFrame."""
    rows = []
    for evt in events:
        tel = evt.get("telemetry", {})
        aero = evt.get("aerodynamics", {})
        tires = evt.get("tires", {})
        row = {
            "session_id": evt.get("session_id"),
            "event_id": evt.get("event_id"),
            "scenario": evt.get("session_type"),
            "speed": tel.get("speed", 0.0),
            "rpm": tel.get("rpm", 0.0),
            "gear": tel.get("gear", 0),
            "torque": tel.get("torque", 0.0),
            "g_force": tel.get("g_force", 0.0),
            "throttle": evt.get("throttle", 0.0),
            "brake": evt.get("brake", 0.0),
            "engine_temperature": tel.get("engine_temperature", 0.0),
            "engine_load": tel.get("engine_load", 0.0),
            "wind_speed": aero.get("wind_speed", 0.0),
            "drag_coefficient": aero.get("drag_coefficient", 0.0),
            "downforce": aero.get("downforce", 0.0),
            "tire_temp_fl": tires.get("tire_temp", [0,0,0,0])[0] if tires.get("tire_temp") else 0.0,
            "tire_wear_fl": tires.get("tire_wear", [0,0,0,0])[0] if tires.get("tire_wear") else 0.0,
            "tire_pressure_fl": tires.get("tire_pressure", [0,0,0,0])[0] if tires.get("tire_pressure") else 0.0,
            "fuel_level": evt.get("fuel_level", 0.0),
            "fuel_used": evt.get("fuel_used", 0.0),
            "rain_intensity": evt.get("rain_intensity", 0.0),
            "lap_number": evt.get("lap_number", 1),
            "lap_progress_pct": evt.get("lap_progress_pct", 0.0)
        }
        rows.append(row)

    return pd.DataFrame(rows)


def calculate_statistical_summary(df):
    """Calculates summary statistics (count, min, max, mean, median, std, p5, p25, p75, p95)."""
    numeric_cols = [
        "speed", "rpm", "torque", "throttle", "brake", "engine_temperature",
        "engine_load", "fuel_level", "fuel_used", "tire_temp_fl", "tire_wear_fl",
        "tire_pressure_fl", "downforce", "drag_coefficient", "rain_intensity"
    ]
    summary = {}

    for col in numeric_cols:
        if col in df.columns:
            s = df[col].dropna()
            if len(s) > 0:
                summary[col] = {
                    "count": int(len(s)),
                    "min": float(round(s.min(), 4)),
                    "max": float(round(s.max(), 4)),
                    "mean": float(round(s.mean(), 4)),
                    "median": float(round(s.median(), 4)),
                    "std": float(round(s.std(), 4)),
                    "p5": float(round(s.quantile(0.05), 4)),
                    "p25": float(round(s.quantile(0.25), 4)),
                    "p75": float(round(s.quantile(0.75), 4)),
                    "p95": float(round(s.quantile(0.95), 4))
                }

    return summary


def calculate_pearson_correlations(df):
    """Calculates Pearson correlation coefficients for expected physical relationships."""
    pairs = [
        ("throttle", "engine_load", "EXPECTED", "Higher throttle increases engine load"),
        ("throttle", "torque", "EXPECTED", "Higher throttle increases torque output"),
        ("speed", "downforce", "EXPECTED", "Downforce increases quadratically with speed"),
        ("speed", "drag_coefficient", "EXPECTED", "Drag coefficient correlates with wind/speed"),
        ("fuel_level", "tire_wear_fl", "EXPECTED", "Fuel level decreases as tire wear increases"),
        ("rain_intensity", "speed", "EXPECTED", "Rain intensity reduces vehicle speed"),
        ("engine_load", "engine_temperature", "EXPECTED", "Engine load increases engine coolant temp")
    ]

    correlations = []
    for col1, col2, exp_status, desc in pairs:
        if col1 in df.columns and col2 in df.columns and len(df) > 1:
            val = df[col1].corr(df[col2])
            r_val = float(round(val, 4)) if not np.isnan(val) else 0.0
            correlations.append({
                "var1": col1,
                "var2": col2,
                "pearson_r": r_val,
                "expected_status": exp_status,
                "description": desc
            })

    return correlations


def analyze_scenario_differentiation(events):
    """Compares mean telemetry metrics across key scenarios."""
    df = extract_numeric_dataframe(events)
    if "scenario" not in df.columns:
        return {}

    scenarios = df["scenario"].unique()
    diff_summary = {}

    for sc in scenarios:
        sub = df[df["scenario"] == sc]
        diff_summary[sc] = {
            "count": int(len(sub)),
            "mean_speed": float(round(sub["speed"].mean(), 2)),
            "max_speed": float(round(sub["speed"].max(), 2)),
            "mean_tire_temp": float(round(sub["tire_temp_fl"].mean(), 2)),
            "max_tire_wear": float(round(sub["tire_wear_fl"].max(), 2)),
            "mean_rain": float(round(sub["rain_intensity"].mean(), 2))
        }

    return diff_summary


def generate_offline_plots(events, output_dir="reports/g2_3"):
    """Generates visual audit plots using Matplotlib/Plotly and saves under output_dir."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        os.makedirs(output_dir, exist_ok=True)
        df = extract_numeric_dataframe(events)

        # Plot 1: Speed Distribution
        plt.figure(figsize=(8, 4))
        plt.hist(df["speed"], bins=30, color="#0066ff", edgecolor="black", alpha=0.7)
        plt.title("Speed Distribution (km/h)")
        plt.xlabel("Speed (km/h)")
        plt.ylabel("Frequency")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "speed_distribution.png"))
        plt.close()

        # Plot 2: Tire Wear Progression
        plt.figure(figsize=(8, 4))
        plt.plot(df["lap_progress_pct"], df["tire_wear_fl"], color="#e63946", label="FL Wear %")
        plt.title("Tire Wear Progression vs Lap Progress")
        plt.xlabel("Lap Progress (%)")
        plt.ylabel("Tire Wear (%)")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "tire_wear_progression.png"))
        plt.close()

        # Plot 3: Downforce vs Speed
        plt.figure(figsize=(8, 4))
        plt.scatter(df["speed"], df["downforce"], color="#2a9d8f", alpha=0.5, s=10)
        plt.title("Downforce (N) vs Speed (km/h)")
        plt.xlabel("Speed (km/h)")
        plt.ylabel("Downforce (N)")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "downforce_vs_speed.png"))
        plt.close()

        print(f"[SUCCESS] Generated visual audit plots -> {output_dir}/")
        return True
    except Exception as e:
        print(f"[WARNING] Visual plot generation skipped: {e}")
        return False
