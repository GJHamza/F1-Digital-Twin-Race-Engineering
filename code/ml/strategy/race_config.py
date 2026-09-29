# -*- coding: utf-8 -*-
"""
Race Configuration Data Model for G.4.5 Strategy Intelligence.
"""

from dataclasses import dataclass
from typing import Dict, Any, Union
from ml.strategy.config import (
    DEFAULT_TOTAL_LAPS,
    DEFAULT_STARTING_FUEL_KG,
    DEFAULT_PIT_STOP_LOSS_SEC,
    DEFAULT_MAX_TIRE_WEAR_PCT,
    DEFAULT_MIN_STINT_LAPS,
)
from ml.strategy.compounds import TireCompound, get_compound_model


@dataclass
class RaceConfig:
    """
    Configuration parameters defining race scenario constraints and parameters.

    Attributes:
        race_id: Unique identifier for the race session.
        total_laps: Total planned race distance in laps.
        starting_fuel: Initial fuel mass on race start grid (kg).
        initial_compound: Tire compound mounted at race start.
        pit_stop_loss_sec: Stationary and pit lane delta time loss per pit stop (sec).
        max_tire_wear: Maximum allowable tire wear percentage before mandatory pit (%).
        min_stint_laps: Minimum required laps per stint.
    """
    race_id: str = "RACE_DEFAULT"
    total_laps: int = DEFAULT_TOTAL_LAPS
    starting_fuel: float = DEFAULT_STARTING_FUEL_KG
    initial_compound: str = "MEDIUM"
    pit_stop_loss_sec: float = DEFAULT_PIT_STOP_LOSS_SEC
    max_tire_wear: float = DEFAULT_MAX_TIRE_WEAR_PCT
    min_stint_laps: int = DEFAULT_MIN_STINT_LAPS

    def __post_init__(self):
        """Validate race configuration parameters."""
        self.initial_compound = str(self.initial_compound).upper()
        get_compound_model(self.initial_compound)  # Validates compound exists

        if self.total_laps <= 0:
            raise ValueError(f"total_laps must be > 0, got {self.total_laps}")
        if self.starting_fuel <= 0.0:
            raise ValueError(f"starting_fuel must be > 0.0, got {self.starting_fuel}")
        if self.pit_stop_loss_sec <= 0.0:
            raise ValueError(f"pit_stop_loss_sec must be > 0.0, got {self.pit_stop_loss_sec}")
        if not (0.0 < self.max_tire_wear <= 100.0):
            raise ValueError(f"max_tire_wear must be between 0.0 and 100.0, got {self.max_tire_wear}")
        if self.min_stint_laps <= 0:
            raise ValueError(f"min_stint_laps must be > 0, got {self.min_stint_laps}")
        if self.min_stint_laps > self.total_laps:
            raise ValueError(f"min_stint_laps ({self.min_stint_laps}) cannot exceed total_laps ({self.total_laps})")

    def to_dict(self) -> Dict[str, Any]:
        """Return dict serialization of race config."""
        return {
            "race_id": self.race_id,
            "total_laps": self.total_laps,
            "starting_fuel": self.starting_fuel,
            "initial_compound": self.initial_compound,
            "pit_stop_loss_sec": self.pit_stop_loss_sec,
            "max_tire_wear": self.max_tire_wear,
            "min_stint_laps": self.min_stint_laps,
        }
