# -*- coding: utf-8 -*-
"""
Silver Layer Quality Validation Rules for F1 Telemetry Pipeline
Defines explicit deterministic validation rules and quarantine rejection reasons.
"""

import json
import pandas as pd
from datetime import datetime


def validate_silver_record(record):
    """
    Validates a raw/bronze record against explicit Silver quality rules.

    Args:
        record (dict): Single telemetry event record.

    Returns:
        tuple: (is_valid: bool, rejection_reason: str or None)
    """
    # 1. Mandatory Core Fields Check
    for field in ["event_id", "session_id", "car_id", "timestamp"]:
        val = record.get(field)
        if not val or not str(val).strip():
            return False, f"Missing or empty mandatory field '{field}'"

    # 2. Timestamp Validation
    ts_str = str(record.get("timestamp"))
    try:
        # Check ISO timestamp parsing
        if ts_str.endswith("Z"):
            ts_str_clean = ts_str[:-1]
        else:
            ts_str_clean = ts_str
        datetime.fromisoformat(ts_str_clean)
    except Exception:
        return False, f"Invalid ISO timestamp format '{record.get('timestamp')}'"

    # 3. Numeric Bounds Validation
    throttle = record.get("throttle")
    if throttle is not None and not pd.isna(throttle):
        try:
            th_val = float(throttle)
            if not (0.0 <= th_val <= 100.0):
                return False, f"Throttle value {th_val} out of bounds [0.0, 100.0]"
        except (ValueError, TypeError):
            return False, f"Invalid throttle type '{throttle}'"

    brake = record.get("brake")
    if brake is not None and not pd.isna(brake):
        try:
            br_val = float(brake)
            if not (0.0 <= br_val <= 100.0):
                return False, f"Brake value {br_val} out of bounds [0.0, 100.0]"
        except (ValueError, TypeError):
            return False, f"Invalid brake type '{brake}'"

    fuel_level = record.get("fuel_level")
    if fuel_level is not None and not pd.isna(fuel_level):
        try:
            fl_val = float(fuel_level)
            if fl_val < 0.0 or fl_val > 150.0:
                return False, f"Fuel level {fl_val} out of physical bounds [0.0, 150.0]"
        except (ValueError, TypeError):
            return False, f"Invalid fuel_level type '{fuel_level}'"

    # Nested Telemetry Extraction
    telemetry = record.get("telemetry")
    if isinstance(telemetry, str):
        try:
            telemetry = json.loads(telemetry)
        except Exception:
            telemetry = {}
    elif not isinstance(telemetry, dict):
        telemetry = {}

    speed = telemetry.get("speed")
    if speed is not None:
        try:
            sp_val = float(speed)
            if sp_val < 0.0 or sp_val > 450.0:
                return False, f"Speed value {sp_val} out of physical bounds [0.0, 450.0]"
        except (ValueError, TypeError):
            return False, f"Invalid speed type '{speed}'"

    rpm = telemetry.get("rpm")
    if rpm is not None:
        try:
            rpm_val = float(rpm)
            if rpm_val < 0.0 or rpm_val > 22000.0:
                return False, f"RPM value {rpm_val} out of physical bounds [0.0, 22000.0]"
        except (ValueError, TypeError):
            return False, f"Invalid rpm type '{rpm}'"

    # Nested Tires Extraction & Array Length Check (must contain 4 values)
    tires = record.get("tires")
    if isinstance(tires, str):
        try:
            tires = json.loads(tires)
        except Exception:
            tires = {}
    elif not isinstance(tires, dict):
        tires = {}

    tire_temps = tires.get("tire_temp")
    if tire_temps is not None and len(tire_temps) > 0:
        if not isinstance(tire_temps, list):
            try:
                tire_temps = list(tire_temps)
            except Exception:
                pass
        if not isinstance(tire_temps, list) or len(tire_temps) != 4:
            return False, f"tire_temp array must contain exactly 4 values, got {tire_temps}"
        for t in tire_temps:
            try:
                t_val = float(t)
                if t_val < -20.0 or t_val > 250.0:
                    return False, f"tire_temp element {t_val} out of physical bounds [-20, 250]"
            except (ValueError, TypeError):
                return False, f"Invalid tire_temp element '{t}'"

    tire_wears = tires.get("tire_wear")
    if tire_wears is not None and len(tire_wears) > 0:
        if not isinstance(tire_wears, list):
            try:
                tire_wears = list(tire_wears)
            except Exception:
                pass
        if not isinstance(tire_wears, list) or len(tire_wears) != 4:
            return False, f"tire_wear array must contain exactly 4 values, got {tire_wears}"
        for w in tire_wears:
            try:
                w_val = float(w)
                if w_val < 0.0 or w_val > 100.0:
                    return False, f"tire_wear element {w_val} out of bounds [0, 100]"
            except (ValueError, TypeError):
                return False, f"Invalid tire_wear element '{w}'"

    return True, None
