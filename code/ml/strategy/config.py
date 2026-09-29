# -*- coding: utf-8 -*-
"""
Configuration Constants and Simulation Defaults for G.4.5 Strategy Intelligence.

These constants represent explicit, configurable simulation assumptions
for pit stops, tire compounds, fuel burn rates, and stint boundaries.
"""

from typing import Dict, Any

# Pit stop simulation assumptions
DEFAULT_PIT_STOP_LOSS_SEC: float = 22.5
MIN_PIT_STOP_DURATION_SEC: float = 1.0

# Race configuration defaults
DEFAULT_TOTAL_LAPS: int = 50
DEFAULT_STARTING_FUEL_KG: float = 85.0
DEFAULT_MAX_TIRE_WEAR_PCT: float = 85.0
DEFAULT_MIN_STINT_LAPS: int = 3

# Fuel consumption defaults (kg/lap)
DEFAULT_FUEL_BURN_PER_LAP_KG: float = 2.0
MIN_FUEL_LEVEL_KG: float = 0.0

# Tire compound characteristics (simulation assumptions aligned with physics_model.py)
COMPOUND_PROPERTIES: Dict[str, Dict[str, Any]] = {
    "SOFT": {
        "grip_factor": 1.05,
        "degradation_factor": 1.4,
        "wear_multiplier": 1.4,
        "warmup_laps": 1,
        "temp_optimum_c": 100.0,
    },
    "MEDIUM": {
        "grip_factor": 1.00,
        "degradation_factor": 1.0,
        "wear_multiplier": 1.0,
        "warmup_laps": 2,
        "temp_optimum_c": 95.0,
    },
    "HARD": {
        "grip_factor": 0.95,
        "degradation_factor": 0.7,
        "wear_multiplier": 0.7,
        "warmup_laps": 3,
        "temp_optimum_c": 90.0,
    },
    "INTERMEDIATE": {
        "grip_factor": 0.88,
        "degradation_factor": 1.1,
        "wear_multiplier": 1.1,
        "warmup_laps": 2,
        "temp_optimum_c": 80.0,
    },
    "WET": {
        "grip_factor": 0.75,
        "degradation_factor": 1.2,
        "wear_multiplier": 1.2,
        "warmup_laps": 2,
        "temp_optimum_c": 75.0,
    }
}
