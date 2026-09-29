# -*- coding: utf-8 -*-
"""
Synthetic Telemetry Generator V2 for F1 Digital Twin
Generates deterministic, schema-validated telemetry datasets.
"""

import sys
import os
import json
import argparse
import random
import math
from datetime import datetime, timedelta, timezone

# Reconfigure stdout/stderr to support utf-8 on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from schema.schema_validator import validate_telemetry
from data_generator.scenarios import get_scenario, list_scenarios
from data_generator.physics_model import (
    calculate_vehicle_mass,
    calculate_speed_and_inputs,
    calculate_powertrain,
    calculate_aerodynamics,
    calculate_tires,
    calculate_fuel,
    calculate_track_position
)
from data_generator.anomaly_model import AnomalyModel


class SyntheticGeneratorV2:
    def __init__(self, seed=42):
        self.seed = seed
        self.set_seed(seed)
        self.config = self._load_config()

    def set_seed(self, seed):
        self.seed = seed
        random.seed(seed)

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "default_cars": [{
                "car_id": "SIM-CAR-01",
                "car_name": "AERO PHANTOM",
                "team": "WILLIAMS",
                "driver_id": "SIM-DRV-01",
                "driver_name": "Alex Albon (Sim)",
                "base_mass": 798.0
            }]
        }

    def generate_session(self, scenario_name, laps_count=5, start_time=None, car_index=0):
        """
        Generates a sequence of deterministic telemetry events for one simulation session.
        Returns:
            list of dict: Validated V1 telemetry events.
        """
        scenario = get_scenario(scenario_name)
        cars = self.config.get("default_cars", [])
        car_info = cars[car_index % len(cars)]

        # Unique session_id constant for the session
        session_id = f"SES-{scenario_name}-{self.seed}-{random.randint(1000, 9999)}"
        
        if start_time is None:
            current_time = datetime.now(timezone.utc)
        else:
            current_time = start_time

        events = []
        seq_counter = 0

        total_steps_per_lap = 60  # 60 seconds per lap at 1 Hz
        total_steps = laps_count * total_steps_per_lap

        for step in range(total_steps):
            seq_counter += 1
            current_time += timedelta(seconds=1)
            timestamp_str = current_time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{current_time.microsecond // 1000:03d}Z"
            
            event_id = f"EVT-{session_id}-{seq_counter:05d}"
            
            lap_number = (step // total_steps_per_lap) + 1
            progress_pct = ((step % total_steps_per_lap) / float(total_steps_per_lap)) * 100.0
            session_progress_pct = step / float(total_steps)

            # Scenario dynamic environmental modifiers
            env_mods = scenario.get_dynamic_modifiers(session_progress_pct)
            grip_factor = env_mods["grip_factor"]

            # Physics calculations
            fuel_level, fuel_used, consumption_rate = calculate_fuel(
                scenario.initial_fuel_kg, lap_number, progress_pct, scenario.setup_engine_mix
            )
            vehicle_mass = calculate_vehicle_mass(car_info.get("base_mass", 798.0), fuel_level)

            speed, throttle, brake, steering = calculate_speed_and_inputs(
                progress_pct, max_target_speed=330.0, grip_factor=grip_factor
            )

            # Anomaly evaluation
            anomaly_eval = AnomalyModel.evaluate(scenario.anomaly_type, progress_pct, timestamp_str)

            if anomaly_eval["is_brake_stress"]:
                g_force = round(min(5.5, 1.0 + (speed / 100.0) * 3.5), 2)
            else:
                g_force = round(max(1.0, min(4.5, 1.0 + (abs(throttle - brake) / 100.0) * 1.5)), 2)

            gear, rpm, torque, engine_load, engine_temp = calculate_powertrain(
                speed, throttle, scenario.setup_engine_mix, is_overheating=anomaly_eval["is_engine_overheat"]
            )

            drag_coefficient, downforce = calculate_aerodynamics(
                speed, scenario.wind_speed, scenario.setup_downforce, drs_active=(speed > 280.0 and throttle > 90.0),
                is_anomaly=anomaly_eval["is_aero_anomaly"]
            )

            tire_temps, tire_wears, tire_pressures, deg_rate = calculate_tires(
                speed, brake, lap_number, scenario.compound, scenario.track_temp,
                is_stress=(scenario.anomaly_type == "TIRE_OVERHEAT"),
                is_overheating=anomaly_eval["is_tire_overheat"],
                lap_progress_pct=progress_pct
            )

            pos_x, pos_z = calculate_track_position(progress_pct)

            # Sector determination (1, 2, 3)
            if progress_pct < 33.33:
                sector_number = 1
            elif progress_pct < 66.66:
                sector_number = 2
            else:
                sector_number = 3

            # Construct Schema V1 event payload
            event = {
                "schema_version": "1.0",
                "session_id": session_id,
                "event_id": event_id,
                "car_id": car_info.get("car_id", "SIM-CAR-01"),
                "car_name": car_info.get("car_name", "AERO PHANTOM"),
                "team": car_info.get("team", "WILLIAMS"),
                "driver_id": car_info.get("driver_id", "SIM-DRV-01"),
                "driver_name": car_info.get("driver_name", "Alex Albon (Sim)"),
                "timestamp": timestamp_str,
                "lap_number": lap_number,
                "lap_time_ms": int((step % total_steps_per_lap) * 1000),
                "sector_number": sector_number,
                "sector_time_ms": int(((step % 20)) * 1000),
                "distance_m": round(progress_pct * 48.0, 1),
                "race_position": 1,
                "session_type": scenario.session_type,
                "vehicle_mass": vehicle_mass,
                "setup_downforce": scenario.setup_downforce,
                "setup_engine_mix": scenario.setup_engine_mix,
                "vehicle_status": "ON_TRACK",
                "throttle": round(throttle, 1),
                "brake": round(brake, 1),
                "steering_angle": round(steering, 1),
                "telemetry": {
                    "speed": round(speed, 2),
                    "rpm": round(rpm, 1),
                    "gear": gear,
                    "torque": round(torque, 2),
                    "g_force": g_force,
                    "pos_x": pos_x,
                    "pos_z": pos_z,
                    "engine_temperature": round(engine_temp, 1),
                    "engine_load": round(engine_load, 1)
                },
                "aerodynamics": {
                    "wind_speed": scenario.wind_speed,
                    "wind_direction": scenario.wind_direction,
                    "drag_coefficient": round(drag_coefficient, 4),
                    "downforce": round(downforce, 2),
                    "drs_active": (speed > 280.0 and throttle > 90.0),
                    "air_density": 1.225
                },
                "tires": {
                    "tire_temp": tire_temps,
                    "tire_wear": tire_wears,
                    "tire_pressure": tire_pressures,
                    "compound": scenario.compound,
                    "tire_age_laps": lap_number,
                    "degradation_rate": deg_rate
                },
                "fuel_level": fuel_level,
                "fuel_consumption_rate": consumption_rate,
                "fuel_used": fuel_used,
                "air_temperature": scenario.air_temp,
                "track_temperature": scenario.track_temp,
                "humidity": 50.0,
                "rain_intensity": round(env_mods["rain_intensity"], 1),
                "weather_state": env_mods["weather_state"],
                "track_condition": env_mods["track_condition"],
                "pos_x": pos_x,
                "pos_z": pos_z,
                "lap_progress_pct": round(progress_pct, 2),
                "anomaly_flag": anomaly_eval["flag"],
                "active_anomalies": anomaly_eval["anomalies"],
                # Legacy flat key backward compatibility
                "speed": round(speed, 2),
                "wind_speed": scenario.wind_speed,
                "drag_coefficient": round(drag_coefficient, 4),
                "downforce": round(downforce, 2),
                "g_force": g_force,
                "torque": round(torque, 2),
                "tire_temp": tire_temps,
                "tire_wear": tire_wears
            }

            # Enforce Schema V1 validation before saving
            val_res = validate_telemetry(event)
            if not val_res["valid"]:
                raise ValueError(f"Generated event {event_id} failed schema validation: {val_res['errors']}")

            events.append(event)

        return events

    def generate_dataset(self, scenario_name="RACE_DRY", sessions_count=1, laps_per_session=5, output_file=None):
        """
        Generates multiple sessions and writes to JSONL format.
        """
        all_events = []
        base_time = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)

        for s in range(sessions_count):
            session_start = base_time + timedelta(hours=s * 2)
            events = self.generate_session(scenario_name, laps_count=laps_per_session, start_time=session_start, car_index=s)
            all_events.extend(events)

        if output_file:
            out_dir = os.path.dirname(output_file)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                for evt in all_events:
                    f.write(json.dumps(evt) + "\n")
            print(f"[SUCCESS] Generated {len(all_events)} events across {sessions_count} session(s) -> {output_file}")

        return all_events


def main():
    parser = argparse.ArgumentParser(description="F1 Digital Twin — Synthetic Data Generator V2")
    parser.add_argument("--scenario", type=str, default="RACE_DRY", help="Scenario name")
    parser.add_argument("--sessions", type=int, default=1, help="Number of sessions")
    parser.add_argument("--laps", type=int, default=5, help="Number of laps per session")
    parser.add_argument("--seed", type=int, default=42, help="Random seed integer")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL file path")
    parser.add_argument("--list-scenarios", action="store_true", help="List all available scenarios")

    args = parser.parse_args()

    if args.list_scenarios:
        print("Available Scenarios:")
        for sc in list_scenarios():
            obj = get_scenario(sc)
            print(f" - {sc:20s}: {obj.description}")
        return

    if not args.output:
        args.output = f"data/generated/{args.scenario.lower()}.jsonl"

    generator = SyntheticGeneratorV2(seed=args.seed)
    generator.generate_dataset(
        scenario_name=args.scenario,
        sessions_count=args.sessions,
        laps_per_session=args.laps,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
