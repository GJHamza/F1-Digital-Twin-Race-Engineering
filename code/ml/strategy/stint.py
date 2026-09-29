# -*- coding: utf-8 -*-
"""
Stint Data Model and Timeline Tracking for G.4.5 Strategy Intelligence.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
from ml.strategy.compounds import get_compound_model, TireCompound


@dataclass
class Stint:
    """
    Representation of a single tire stint during a race.

    Attributes:
        stint_id: Unique stint string identifier.
        stint_number: Sequential stint index (1-based).
        compound: Mounted tire compound name.
        start_lap: Lap number when stint commences (1-based inclusive).
        end_lap: Lap number when stint concludes (1-based inclusive).
        starting_fuel: Vehicle fuel mass at stint start (kg).
        ending_fuel: Vehicle fuel mass at stint conclusion (kg).
        starting_tire_wear: Average wheel tire wear at stint start (%).
        ending_tire_wear: Average wheel tire wear at stint conclusion (%).
    """
    stint_id: str
    stint_number: int
    compound: str
    start_lap: int
    end_lap: int
    starting_fuel: float
    ending_fuel: float
    starting_tire_wear: float = 0.0
    ending_tire_wear: float = 0.0

    def __post_init__(self):
        """Validate stint properties."""
        self.compound = str(self.compound).upper()
        get_compound_model(self.compound)

        if self.stint_number < 1:
            raise ValueError(f"stint_number must be >= 1, got {self.stint_number}")
        if self.start_lap < 1:
            raise ValueError(f"start_lap must be >= 1, got {self.start_lap}")
        if self.end_lap < self.start_lap:
            raise ValueError(f"end_lap ({self.end_lap}) must be >= start_lap ({self.start_lap})")
        if self.starting_fuel < 0.0:
            raise ValueError(f"starting_fuel cannot be negative, got {self.starting_fuel}")
        if self.ending_fuel < 0.0:
            raise ValueError(f"ending_fuel cannot be negative, got {self.ending_fuel}")
        if self.ending_fuel > self.starting_fuel:
            raise ValueError(f"ending_fuel ({self.ending_fuel}) cannot exceed starting_fuel ({self.starting_fuel})")
        if not (0.0 <= self.starting_tire_wear <= 100.0):
            raise ValueError(f"starting_tire_wear must be in [0, 100], got {self.starting_tire_wear}")
        if not (0.0 <= self.ending_tire_wear <= 100.0):
            raise ValueError(f"ending_tire_wear must be in [0, 100], got {self.ending_tire_wear}")
        if self.ending_tire_wear < self.starting_tire_wear:
            raise ValueError(f"ending_tire_wear ({self.ending_tire_wear}) cannot be less than starting_tire_wear ({self.starting_tire_wear})")

    @property
    def stint_laps(self) -> int:
        """Total number of laps completed in this stint."""
        return (self.end_lap - self.start_lap) + 1

    @property
    def fuel_consumed(self) -> float:
        """Total fuel consumed during this stint in kg."""
        return round(self.starting_fuel - self.ending_fuel, 3)

    @property
    def tire_wear_delta(self) -> float:
        """Total tire wear accumulated during this stint in %."""
        return round(self.ending_tire_wear - self.starting_tire_wear, 3)

    def to_dict(self) -> Dict[str, Any]:
        """Convert stint properties to dictionary representation."""
        return {
            "stint_id": self.stint_id,
            "stint_number": self.stint_number,
            "compound": self.compound,
            "start_lap": self.start_lap,
            "end_lap": self.end_lap,
            "stint_laps": self.stint_laps,
            "starting_fuel": self.starting_fuel,
            "ending_fuel": self.ending_fuel,
            "fuel_consumed": self.fuel_consumed,
            "starting_tire_wear": self.starting_tire_wear,
            "ending_tire_wear": self.ending_tire_wear,
            "tire_wear_delta": self.tire_wear_delta,
        }


def validate_stint_sequence(stints: List[Stint], expected_total_laps: int) -> bool:
    """
    Validates that a list of stints forms a continuous, non-overlapping race timeline from Lap 1 to expected_total_laps.
    """
    if not stints:
        raise ValueError("Stint sequence cannot be empty")

    sorted_stints = sorted(stints, key=lambda s: s.stint_number)

    if sorted_stints[0].start_lap != 1:
        raise ValueError(f"First stint must start at lap 1, got lap {sorted_stints[0].start_lap}")

    if sorted_stints[-1].end_lap != expected_total_laps:
        raise ValueError(
            f"Final stint end_lap ({sorted_stints[-1].end_lap}) does not match expected race total laps ({expected_total_laps})"
        )

    for i in range(len(sorted_stints)):
        current = sorted_stints[i]
        if current.stint_number != i + 1:
            raise ValueError(f"Stint sequence numbers must be contiguous starting from 1. Gap at index {i}")

        if i > 0:
            previous = sorted_stints[i - 1]
            if current.start_lap != previous.end_lap + 1:
                raise ValueError(
                    f"Stint overlap or gap detected between Stint {previous.stint_number} (end lap {previous.end_lap}) "
                    f"and Stint {current.stint_number} (start lap {current.start_lap})"
                )

    return True
