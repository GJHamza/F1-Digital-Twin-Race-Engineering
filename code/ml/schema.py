# -*- coding: utf-8 -*-
"""
ML Dataset Schema Definition & Physical Bound Specifications for Phase G.4.1
"""

# Physical and Data Quality Bounds for ML Features
FEATURE_BOUNDS = {
    "speed_kmh": {"min": 0.0, "max": 420.0},
    "speed_ms": {"min": 0.0, "max": 116.7},
    "acceleration_estimate": {"min": -50.0, "max": 50.0},
    "g_force": {"min": 0.0, "max": 10.0},
    "tire_temp_avg": {"min": -20.0, "max": 250.0},
    "tire_temp_max": {"min": -20.0, "max": 250.0},
    "tire_wear_avg": {"min": 0.0, "max": 100.0},
    "tire_wear_max": {"min": 0.0, "max": 100.0},
    "tire_stress_index": {"min": 0.0, "max": 1000.0},
    "tire_wear_rate": {"min": 0.0, "max": 100.0},
    "downforce": {"min": 0.0, "max": 30000.0},
    "drag_coefficient": {"min": 0.0, "max": 2.5},
    "wind_speed": {"min": 0.0, "max": 200.0},
    "aero_efficiency": {"min": 0.0, "max": 50.0},
    "downforce_per_speed": {"min": 0.0, "max": 500.0},
    "rpm": {"min": 0.0, "max": 22000.0},
    "torque": {"min": 0.0, "max": 2000.0},
    "torque_per_rpm": {"min": 0.0, "max": 10.0},
    "estimated_power_kw": {"min": 0.0, "max": 1500.0},
    "fuel_level": {"min": 0.0, "max": 150.0},
    "fuel_remaining_pct": {"min": 0.0, "max": 100.0},
    "elapsed_time_sec": {"min": 0.0, "max": 86400.0},
    "rolling_speed_mean_5": {"min": 0.0, "max": 420.0},
    "rolling_speed_std_5": {"min": 0.0, "max": 100.0},
    "rolling_tire_temp_5": {"min": -20.0, "max": 250.0},
    "rolling_tire_wear_5": {"min": 0.0, "max": 100.0},
}

# Maximum Allowed Null Ratios Per Column (0.0 means 0% nulls tolerated)
NULL_TOLERANCE = {
    col: 0.0 for col in FEATURE_BOUNDS
}
