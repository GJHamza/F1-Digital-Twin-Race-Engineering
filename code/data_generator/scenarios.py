# -*- coding: utf-8 -*-
"""
Scenario Registry and Definitions for F1 Synthetic Data Generator V2
"""

class Scenario:
    def __init__(self, name, session_type="RACE", compound="MEDIUM",
                 initial_fuel_kg=80.0, setup_downforce=50, setup_engine_mix=5,
                 weather_state="DRY", track_condition="DRY", rain_intensity=0.0,
                 air_temp=25.0, track_temp=35.0, wind_speed=15.0, wind_direction=0.0,
                 anomaly_type=None, description=""):
        self.name = name
        self.session_type = session_type
        self.compound = compound
        self.initial_fuel_kg = initial_fuel_kg
        self.setup_downforce = setup_downforce
        self.setup_engine_mix = setup_engine_mix
        self.weather_state = weather_state
        self.track_condition = track_condition
        self.rain_intensity = rain_intensity
        self.air_temp = air_temp
        self.track_temp = track_temp
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self.anomaly_type = anomaly_type
        self.description = description

    def get_dynamic_modifiers(self, progress_pct):
        """
        Returns dynamic environment/track modifiers based on session progress (0.0 to 1.0)
        """
        mods = {
            "rain_intensity": self.rain_intensity,
            "weather_state": self.weather_state,
            "track_condition": self.track_condition,
            "grip_factor": 1.0
        }

        if self.name == "DRY_TO_WET":
            if progress_pct > 0.5:
                rain_val = min(100.0, (progress_pct - 0.5) * 200.0)
                mods["rain_intensity"] = rain_val
                mods["weather_state"] = "HEAVY_RAIN" if rain_val > 60 else "LIGHT_RAIN"
                mods["track_condition"] = "WET" if rain_val > 50 else "DAMP"
                mods["grip_factor"] = max(0.6, 1.0 - (rain_val / 250.0))
        elif self.name == "WET_TO_DRY":
            if progress_pct > 0.4:
                rain_val = max(0.0, 70.0 - (progress_pct - 0.4) * 150.0)
                mods["rain_intensity"] = rain_val
                mods["weather_state"] = "LIGHT_RAIN" if rain_val > 20 else "DRY"
                mods["track_condition"] = "DAMP" if rain_val > 10 else "DRY"
                mods["grip_factor"] = min(1.0, 0.7 + ((progress_pct - 0.4) * 0.5))
        elif self.weather_state == "HEAVY_RAIN":
            mods["grip_factor"] = 0.65
        elif self.weather_state == "LIGHT_RAIN":
            mods["grip_factor"] = 0.82

        return mods


SCENARIO_REGISTRY = {
    "QUALIFYING_DRY": Scenario(
        name="QUALIFYING_DRY",
        session_type="QUALIFYING",
        compound="SOFT",
        initial_fuel_kg=15.0,
        setup_downforce=40,
        setup_engine_mix=9,
        description="High speed qualifying run with low fuel and soft compound"
    ),
    "RACE_DRY": Scenario(
        name="RACE_DRY",
        session_type="RACE",
        compound="MEDIUM",
        initial_fuel_kg=85.0,
        setup_downforce=55,
        setup_engine_mix=6,
        description="Standard dry race stint with medium compound"
    ),
    "LONG_STINT": Scenario(
        name="LONG_STINT",
        session_type="RACE",
        compound="HARD",
        initial_fuel_kg=105.0,
        setup_downforce=50,
        setup_engine_mix=5,
        description="Extended race stint focusing on tire wear and fuel drop"
    ),
    "LOW_FUEL": Scenario(
        name="LOW_FUEL",
        session_type="QUALIFYING",
        compound="SOFT",
        initial_fuel_kg=8.0,
        setup_downforce=35,
        setup_engine_mix=10,
        description="Ultra-light vehicle mass stint near stint end"
    ),
    "HIGH_FUEL": Scenario(
        name="HIGH_FUEL",
        session_type="RACE",
        compound="HARD",
        initial_fuel_kg=110.0,
        setup_downforce=60,
        setup_engine_mix=5,
        description="Full fuel tank race start simulation"
    ),
    "HOT_TRACK": Scenario(
        name="HOT_TRACK",
        session_type="RACE",
        compound="HARD",
        initial_fuel_kg=70.0,
        air_temp=38.0,
        track_temp=52.0,
        description="Extreme thermal track environment"
    ),
    "COLD_TRACK": Scenario(
        name="COLD_TRACK",
        session_type="TEST",
        compound="MEDIUM",
        initial_fuel_kg=50.0,
        air_temp=12.0,
        track_temp=16.0,
        description="Low temperature track conditions"
    ),
    "LIGHT_RAIN": Scenario(
        name="LIGHT_RAIN",
        session_type="RACE",
        compound="INTERMEDIATE",
        initial_fuel_kg=60.0,
        weather_state="LIGHT_RAIN",
        track_condition="DAMP",
        rain_intensity=35.0,
        description="Light rain stint on intermediate tires"
    ),
    "HEAVY_RAIN": Scenario(
        name="HEAVY_RAIN",
        session_type="RACE",
        compound="WET",
        initial_fuel_kg=70.0,
        weather_state="HEAVY_RAIN",
        track_condition="WET",
        rain_intensity=85.0,
        description="Heavy rain stint on wet tires"
    ),
    "DRY_TO_WET": Scenario(
        name="DRY_TO_WET",
        session_type="RACE",
        compound="MEDIUM",
        initial_fuel_kg=75.0,
        description="Dynamic transition from dry to heavy rain"
    ),
    "WET_TO_DRY": Scenario(
        name="WET_TO_DRY",
        session_type="RACE",
        compound="INTERMEDIATE",
        initial_fuel_kg=65.0,
        weather_state="LIGHT_RAIN",
        track_condition="WET",
        rain_intensity=60.0,
        description="Dynamic transition from wet track to drying line"
    ),
    "TIRE_OVERHEAT": Scenario(
        name="TIRE_OVERHEAT",
        session_type="TIRE_TEST",
        compound="SOFT",
        initial_fuel_kg=40.0,
        anomaly_type="TIRE_OVERHEAT",
        description="Controlled tire thermal overload anomaly test"
    ),
    "ENGINE_OVERHEAT": Scenario(
        name="ENGINE_OVERHEAT",
        session_type="TEST",
        compound="MEDIUM",
        initial_fuel_kg=50.0,
        setup_engine_mix=10,
        anomaly_type="ENGINE_OVERHEAT",
        description="Controlled engine coolant overheating anomaly test"
    ),
    "BRAKE_STRESS": Scenario(
        name="BRAKE_STRESS",
        session_type="BRAKE_TEST",
        compound="MEDIUM",
        initial_fuel_kg=30.0,
        anomaly_type="BRAKE_STRESS",
        description="Controlled brake stress & deceleration test"
    ),
    "AERO_ANOMALY": Scenario(
        name="AERO_ANOMALY",
        session_type="WIND_TUNNEL",
        compound="MEDIUM",
        initial_fuel_kg=40.0,
        anomaly_type="AERO_ANOMALY",
        description="Controlled aerodynamic drag anomaly test"
    )
}


def get_scenario(name):
    """Retrieve scenario configuration by name."""
    if name not in SCENARIO_REGISTRY:
        raise ValueError(f"Unknown scenario '{name}'. Available: {list(SCENARIO_REGISTRY.keys())}")
    return SCENARIO_REGISTRY[name]


def list_scenarios():
    """Returns list of all available scenario names."""
    return sorted(list(SCENARIO_REGISTRY.keys()))
