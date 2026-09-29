# -*- coding: utf-8 -*-
"""
Strategy State Representation and State Machine for G.4.5 Strategy Intelligence.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Union
from ml.strategy.compounds import get_compound_model, TireCompound


class VehicleStatus(str, Enum):
    """Vehicle track / pit status during race session."""
    ON_TRACK = "ON_TRACK"
    PIT_ENTRY = "PIT_ENTRY"
    IN_PIT = "IN_PIT"
    PIT_EXIT = "PIT_EXIT"

    @classmethod
    def has_value(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        return value.upper() in cls._value2member_map_


@dataclass
class StrategyState:
    """
    Complete state representation of the race engineering strategy status at a given lap.

    Attributes:
        race_id: Race session identifier.
        current_lap: Current lap number (1-based).
        current_stint: Current stint index (1-based).
        current_compound: Currently mounted tire compound.
        fuel_remaining: Fuel level remaining in tank (kg).
        tire_wear: Dictionary of four-wheel wear percentages {"FL": %, "FR": %, "RL": %, "RR": %}.
        pit_stop_count: Cumulative number of completed pit stops.
        vehicle_status: Vehicle operational status enum.
    """
    race_id: str
    current_lap: int
    current_stint: int
    current_compound: str
    fuel_remaining: float
    tire_wear: Dict[str, float] = field(default_factory=lambda: {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0})
    pit_stop_count: int = 0
    vehicle_status: VehicleStatus = VehicleStatus.ON_TRACK

    def __post_init__(self):
        """Validate state variables."""
        self.current_compound = str(self.current_compound).upper()
        get_compound_model(self.current_compound)

        if self.current_lap < 1:
            raise ValueError(f"current_lap must be >= 1, got {self.current_lap}")
        if self.current_stint < 1:
            raise ValueError(f"current_stint must be >= 1, got {self.current_stint}")
        if self.fuel_remaining < 0.0:
            raise ValueError(f"fuel_remaining cannot be negative, got {self.fuel_remaining}")
        if self.pit_stop_count < 0:
            raise ValueError(f"pit_stop_count cannot be negative, got {self.pit_stop_count}")

        if not isinstance(self.vehicle_status, VehicleStatus):
            status_str = str(self.vehicle_status).upper()
            if not VehicleStatus.has_value(status_str):
                raise ValueError(f"Invalid vehicle_status '{self.vehicle_status}'")
            self.vehicle_status = VehicleStatus(status_str)

        # Validate tire wear dictionary keys and values
        for wheel in ["FL", "FR", "RL", "RR"]:
            if wheel not in self.tire_wear:
                raise ValueError(f"Missing wheel '{wheel}' in tire_wear dict")
            val = self.tire_wear[wheel]
            if not (0.0 <= val <= 100.0):
                raise ValueError(f"Tire wear for {wheel} must be in [0, 100], got {val}")

    @property
    def avg_tire_wear(self) -> float:
        """Calculate four-wheel average tire wear percentage."""
        return round(sum(self.tire_wear.values()) / 4.0, 3)

    def transition_status(self, target_status: Union[str, VehicleStatus]) -> "StrategyState":
        """
        Executes deterministic status transitions according to valid state graph:
        ON_TRACK -> PIT_ENTRY -> IN_PIT -> PIT_EXIT -> ON_TRACK
        """
        target = target_status if isinstance(target_status, VehicleStatus) else VehicleStatus(str(target_status).upper())
        current = self.vehicle_status

        valid_transitions = {
            VehicleStatus.ON_TRACK: [VehicleStatus.ON_TRACK, VehicleStatus.PIT_ENTRY],
            VehicleStatus.PIT_ENTRY: [VehicleStatus.IN_PIT],
            VehicleStatus.IN_PIT: [VehicleStatus.PIT_EXIT],
            VehicleStatus.PIT_EXIT: [VehicleStatus.ON_TRACK],
        }

        if target not in valid_transitions[current]:
            raise ValueError(f"Invalid vehicle status transition from {current.value} to {target.value}")

        self.vehicle_status = target
        return self

    def to_telemetry_extension(self) -> Dict[str, Any]:
        """
        Serialize strategy state as an extension payload compatible with V1 Telemetry schema.
        """
        return {
            "stint_id": f"STINT_{self.current_stint:02d}",
            "stint_number": self.current_stint,
            "tire_compound": self.current_compound,
            "pit_stop_count": self.pit_stop_count,
            "vehicle_status": self.vehicle_status.value,
            "avg_tire_wear_pct": self.avg_tire_wear,
            "fuel_remaining_kg": round(self.fuel_remaining, 3),
            "race_lap": self.current_lap,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full dictionary representation."""
        res = self.to_telemetry_extension()
        res["race_id"] = self.race_id
        res["tire_wear_fl"] = round(self.tire_wear["FL"], 2)
        res["tire_wear_fr"] = round(self.tire_wear["FR"], 2)
        res["tire_wear_rl"] = round(self.tire_wear["RL"], 2)
        res["tire_wear_rr"] = round(self.tire_wear["RR"], 2)
        return res
