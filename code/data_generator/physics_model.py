# -*- coding: utf-8 -*-
"""
Deterministic Physics & Synthetic Engineering Model for F1 Data Generator V2
"""

import math

def calculate_vehicle_mass(base_mass_kg, fuel_level_kg):
    """Calculates total vehicle mass including remaining fuel."""
    return max(500.0, float(base_mass_kg + max(0.0, fuel_level_kg)))


def calculate_speed_and_inputs(lap_progress_pct, max_target_speed=330.0, grip_factor=1.0):
    """
    Simulates lap velocity profile across lap progress (0.0 to 100.0%):
    - 0-30%: Main Straight (High Acceleration)
    - 30-40%: Turn 1 Braking Zone (Heavy Deceleration)
    - 40-55%: Apex Cornering (Constant Low Speed)
    - 55-80%: Technical Sector 2 (Acceleration & Medium Cornering)
    - 80-90%: Hairpin Braking Zone
    - 90-100%: Straight Exit Acceleration
    """
    pct = lap_progress_pct % 100.0
    effective_max_speed = max_target_speed * grip_factor

    if pct <= 30.0:
        # Straight acceleration
        ratio = pct / 30.0
        speed = 180.0 + (effective_max_speed - 180.0) * (ratio ** 0.7)
        throttle = 100.0
        brake = 0.0
        steering = 0.0
    elif pct <= 40.0:
        # Heavy braking zone for T1
        ratio = (pct - 30.0) / 10.0
        speed = effective_max_speed - (effective_max_speed - 90.0 * grip_factor) * (ratio ** 0.8)
        throttle = 0.0
        brake = max(0.0, 100.0 * (1.0 - ratio * 0.5))
        steering = 15.0 * ratio
    elif pct <= 55.0:
        # Apex cornering T1
        ratio = (pct - 40.0) / 15.0
        speed = 90.0 * grip_factor + 30.0 * math.sin(ratio * math.pi)
        throttle = 40.0 + 30.0 * ratio
        brake = 0.0
        steering = 35.0 * math.sin(ratio * math.pi)
    elif pct <= 80.0:
        # Sector 2 acceleration and sweeping turns
        ratio = (pct - 55.0) / 25.0
        speed = 120.0 + (effective_max_speed * 0.85 - 120.0) * ratio
        throttle = 80.0 + 20.0 * ratio
        brake = 0.0
        steering = -20.0 * math.sin(ratio * 2 * math.pi)
    elif pct <= 90.0:
        # Hairpin braking
        ratio = (pct - 80.0) / 10.0
        speed = (effective_max_speed * 0.85) - ((effective_max_speed * 0.85) - 75.0 * grip_factor) * ratio
        throttle = 0.0
        brake = max(0.0, 90.0 * (1.0 - ratio * 0.6))
        steering = 45.0 * ratio
    else:
        # Straight exit acceleration
        ratio = (pct - 90.0) / 10.0
        speed = (75.0 * grip_factor) + (180.0 - (75.0 * grip_factor)) * ratio
        throttle = 90.0 + 10.0 * ratio
        brake = 0.0
        steering = 5.0 * (1.0 - ratio)

    speed = max(0.0, min(360.0, speed))
    return speed, throttle, brake, steering


def calculate_gear_and_rpm(speed_kmh, throttle_pct):
    """Derives current gear and engine RPM deterministically from vehicle speed."""
    if speed_kmh < 2.0:
        gear = 0
        rpm = 1000.0
    else:
        if speed_kmh >= 330.0:
            gear = 8
        elif speed_kmh >= 290.0:
            gear = 7
        elif speed_kmh >= 250.0:
            gear = 6
        elif speed_kmh >= 200.0:
            gear = 5
        elif speed_kmh >= 150.0:
            gear = 4
        elif speed_kmh >= 100.0:
            gear = 3
        elif speed_kmh >= 50.0:
            gear = 2
        else:
            gear = 1

        rpm_base = 6000.0 + (speed_kmh / 350.0) * 8000.0
        rpm_throttle = (throttle_pct / 100.0) * 1000.0
        rpm = min(15000.0, max(1000.0, rpm_base + rpm_throttle))

    return gear, rpm


def calculate_powertrain(speed_kmh, throttle_pct, setup_engine_mix=5, is_overheating=False):
    """Calculates torque, engine load, and engine temperature."""
    gear, rpm = calculate_gear_and_rpm(speed_kmh, throttle_pct)
    mix_factor = 0.6 + (setup_engine_mix / 10.0) * 0.8
    torque = max(0.0, (speed_kmh / 350.0) * 850.0) * mix_factor * (0.3 + (throttle_pct / 100.0) * 0.7)
    engine_load = max(0.0, min(100.0, (throttle_pct * 0.8) + (rpm / 15000.0) * 20.0))
    
    base_temp = 90.0 + (engine_load / 100.0) * 15.0 + (setup_engine_mix / 10.0) * 5.0
    if is_overheating:
        base_temp += 28.0

    engine_temp = min(135.0, max(70.0, base_temp))
    return gear, rpm, torque, engine_load, engine_temp


def calculate_aerodynamics(speed_kmh, wind_speed_kts, setup_downforce=50, drs_active=False, is_anomaly=False):
    """Calculates aerodynamic drag coefficient and downforce."""
    v_ms = speed_kmh / 3.6
    drs_mult = 0.8 if drs_active else 1.0
    base_cd = (0.28 + (wind_speed_kts / 100.0) * 0.15) * (0.8 + (setup_downforce / 100.0) * 0.4) * drs_mult
    
    if is_anomaly:
        base_cd += 0.12  # Anomaly drag spike

    drag_coefficient = max(0.20, min(0.60, base_cd))
    downforce = 0.5 * 1.225 * (v_ms ** 2) * drag_coefficient * 3.2 * (0.5 + (setup_downforce / 100.0) * 1.0)
    return drag_coefficient, downforce


def calculate_tires(speed_kmh, brake_pct, tire_age_laps, compound="MEDIUM", track_temp=35.0,
                    is_stress=False, is_overheating=False, lap_progress_pct=0.0):
    """
    Calculates four tire temperatures, wear percentages, pressures, and degradation rates.
    Returns: (tire_temps_list, tire_wears_list, tire_pressures_list, deg_rate)
    """
    compound_wear_mult = {
        "SOFT": 1.4,
        "MEDIUM": 1.0,
        "HARD": 0.7,
        "INTERMEDIATE": 1.1,
        "WET": 1.2
    }.get(compound, 1.0)

    # Base wear rate per lap
    base_wear_rate = 0.8 * compound_wear_mult
    if is_stress:
        base_wear_rate *= 3.0

    # Strictly monotonic progress calculation
    laps_completed = max(0.0, (tire_age_laps - 1) + (lap_progress_pct / 100.0))
    accumulated_wear = min(100.0, laps_completed * base_wear_rate)
    
    # Wheel-specific wear offsets (Front Left gets slightly higher cornering load)
    wear_fl = min(100.0, accumulated_wear * 1.05)
    wear_fr = min(100.0, accumulated_wear * 1.02)
    wear_rl = min(100.0, accumulated_wear * 0.98)
    wear_rr = min(100.0, accumulated_wear * 0.95)

    # Thermal calculation
    target_temp = 80.0 + (track_temp / 50.0) * 15.0 + (speed_kmh / 350.0) * 20.0
    if brake_pct > 50.0:
        target_temp += 15.0  # Brake heat transfer
    if is_stress:
        target_temp += 25.0
    if is_overheating:
        target_temp += 32.0

    temp_fl = min(145.0, target_temp + 2.0)
    temp_fr = min(145.0, target_temp + 1.5)
    temp_rl = min(145.0, target_temp)
    temp_rr = min(145.0, target_temp - 0.5)

    # Pressures (psi) scale with temperature
    press_fl = 22.0 + (temp_fl - 90.0) * 0.05
    press_fr = 22.0 + (temp_fr - 90.0) * 0.05
    press_rl = 21.5 + (temp_rl - 90.0) * 0.05
    press_rr = 21.5 + (temp_rr - 90.0) * 0.05

    tire_temps = [round(temp_fl, 1), round(temp_fr, 1), round(temp_rl, 1), round(temp_rr, 1)]
    tire_wears = [round(wear_fl, 2), round(wear_fr, 2), round(wear_rl, 2), round(wear_rr, 2)]
    tire_pressures = [round(press_fl, 1), round(press_fr, 1), round(press_rl, 1), round(press_rr, 1)]

    return tire_temps, tire_wears, tire_pressures, round(base_wear_rate, 3)


def calculate_fuel(initial_fuel_kg, current_lap, lap_progress_pct, setup_engine_mix=5):
    """
    Calculates remaining fuel level (monotonically decreasing) and fuel used.
    """
    consumption_rate_per_lap = 1.8 + (setup_engine_mix / 10.0) * 0.6  # 1.8 - 2.4 kg/lap
    laps_completed = (current_lap - 1) + (lap_progress_pct / 100.0)
    
    fuel_used = min(initial_fuel_kg, laps_completed * consumption_rate_per_lap)
    fuel_level = max(0.0, initial_fuel_kg - fuel_used)
    
    return round(fuel_level, 2), round(fuel_used, 2), round(consumption_rate_per_lap, 2)


def calculate_track_position(lap_progress_pct):
    """
    Calculates X and Z track coordinates based on parametric oval geometry.
    """
    angle = (lap_progress_pct / 100.0) * 2.0 * math.pi
    pos_x = 120.0 * math.sin(angle) + 40.0 * math.sin(2.0 * angle)
    pos_z = 80.0 * math.cos(angle) + 20.0 * math.cos(2.0 * angle)
    return round(pos_x, 2), round(pos_z, 2)
