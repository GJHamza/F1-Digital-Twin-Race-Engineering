# -*- coding: utf-8 -*-
"""
Deterministic Fuel State and Depletion Model for G.4.5 Strategy Intelligence.
"""

from dataclasses import dataclass
from typing import Dict, Any
from ml.strategy.config import DEFAULT_STARTING_FUEL_KG, DEFAULT_FUEL_BURN_PER_LAP_KG, MIN_FUEL_LEVEL_KG


@dataclass
class FuelState:
    """
    State tracking vehicle fuel level and consumption history.

    Attributes:
        starting_fuel: Initial fuel mass allocated for session (kg).
        fuel_remaining: Current fuel mass remaining in fuel tank (kg).
        fuel_consumed: Total fuel consumed up to current state (kg).
        fuel_consumption_rate: Deterministic burn rate per completed lap (kg/lap).
    """
    starting_fuel: float
    fuel_remaining: float
    fuel_consumed: float
    fuel_consumption_rate: float

    def __post_init__(self):
        """Validate fuel state consistency."""
        if self.starting_fuel < 0.0:
            raise ValueError(f"starting_fuel cannot be negative, got {self.starting_fuel}")
        if self.fuel_remaining < MIN_FUEL_LEVEL_KG:
            raise ValueError(f"fuel_remaining cannot be negative, got {self.fuel_remaining}")
        if self.fuel_consumed < 0.0:
            raise ValueError(f"fuel_consumed cannot be negative, got {self.fuel_consumed}")
        if self.fuel_consumed > self.starting_fuel + 1e-6:
            raise ValueError(f"fuel_consumed ({self.fuel_consumed}) cannot exceed starting_fuel ({self.starting_fuel})")
        if self.fuel_consumption_rate <= 0.0:
            raise ValueError(f"fuel_consumption_rate must be > 0, got {self.fuel_consumption_rate}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert fuel state to dictionary representation."""
        return {
            "starting_fuel": self.starting_fuel,
            "fuel_remaining": round(self.fuel_remaining, 3),
            "fuel_consumed": round(self.fuel_consumed, 3),
            "fuel_consumption_rate": self.fuel_consumption_rate,
        }


class FuelModel:
    """
    Deterministic fuel model managing per-lap fuel depletion.
    """

    def __init__(self, starting_fuel: float = DEFAULT_STARTING_FUEL_KG,
                 fuel_consumption_rate: float = DEFAULT_FUEL_BURN_PER_LAP_KG):
        if starting_fuel <= 0.0:
            raise ValueError(f"starting_fuel must be > 0, got {starting_fuel}")
        if fuel_consumption_rate <= 0.0:
            raise ValueError(f"fuel_consumption_rate must be > 0, got {fuel_consumption_rate}")

        self.starting_fuel = float(starting_fuel)
        self.fuel_consumption_rate = float(fuel_consumption_rate)
        self._fuel_remaining = float(starting_fuel)
        self._fuel_consumed = 0.0

    def get_state(self) -> FuelState:
        """Returns current FuelState instance."""
        return FuelState(
            starting_fuel=self.starting_fuel,
            fuel_remaining=self._fuel_remaining,
            fuel_consumed=self._fuel_consumed,
            fuel_consumption_rate=self.fuel_consumption_rate,
        )

    def consume_fuel(self, laps: float = 1.0) -> FuelState:
        """
        Simulates deterministic fuel depletion over a given number of laps.

        Args:
            laps: Number of laps completed (default 1.0).

        Returns:
            Updated FuelState.
        """
        if laps < 0.0:
            raise ValueError(f"laps to consume cannot be negative, got {laps}")

        burn_amount = laps * self.fuel_consumption_rate
        if burn_amount > self._fuel_remaining:
            raise ValueError(
                f"Insufficient fuel remaining ({self._fuel_remaining:.2f} kg) to complete {laps} laps "
                f"at {self.fuel_consumption_rate:.2f} kg/lap (requires {burn_amount:.2f} kg)"
            )

        self._fuel_consumed += burn_amount
        self._fuel_remaining -= burn_amount
        return self.get_state()
