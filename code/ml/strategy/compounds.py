# -*- coding: utf-8 -*-
"""
Tire Compound Model and Compound Transitions for G.4.5 Strategy Intelligence.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Union
from ml.strategy.config import COMPOUND_PROPERTIES


class TireCompound(str, Enum):
    """Supported F1 Tire Compounds."""
    SOFT = "SOFT"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"

    @classmethod
    def has_value(cls, value: str) -> bool:
        """Check if string representation is a valid compound."""
        if not isinstance(value, str):
            return False
        return value.upper() in cls._value2member_map_


@dataclass(frozen=True)
class CompoundModel:
    """
    Deterministic compound characteristics model.
    
    Attributes:
        compound: Tire compound name.
        grip_factor: Base relative mechanical grip (1.0 = baseline medium).
        degradation_factor: Relative degradation rate multiplier.
        wear_multiplier: Wear scaling per lap.
        warmup_laps: Laps required to reach thermal peak grip.
        temp_optimum_c: Optimal working thermal window (Celsius).
    """
    compound: str
    grip_factor: float
    degradation_factor: float
    wear_multiplier: float
    warmup_laps: int
    temp_optimum_c: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert compound properties to dictionary representation."""
        return {
            "compound": self.compound,
            "grip_factor": self.grip_factor,
            "degradation_factor": self.degradation_factor,
            "wear_multiplier": self.wear_multiplier,
            "warmup_laps": self.warmup_laps,
            "temp_optimum_c": self.temp_optimum_c,
        }


def get_compound_model(compound: Union[str, TireCompound]) -> CompoundModel:
    """
    Retrieves the deterministic CompoundModel for a specified tire compound.
    Raises ValueError for unsupported compounds.
    """
    comp_str = compound.value if isinstance(compound, TireCompound) else str(compound).upper()
    
    if comp_str not in COMPOUND_PROPERTIES:
        valid_compounds = list(COMPOUND_PROPERTIES.keys())
        raise ValueError(f"Invalid tire compound '{compound}'. Valid options: {valid_compounds}")

    props = COMPOUND_PROPERTIES[comp_str]
    return CompoundModel(
        compound=comp_str,
        grip_factor=props["grip_factor"],
        degradation_factor=props["degradation_factor"],
        wear_multiplier=props["wear_multiplier"],
        warmup_laps=props["warmup_laps"],
        temp_optimum_c=props["temp_optimum_c"],
    )


def validate_compound_transition(compound_before: Union[str, TireCompound],
                                  compound_after: Union[str, TireCompound]) -> bool:
    """
    Validates transition from compound_before to compound_after.
    Compound transition is valid if both compounds are recognized.
    Note: Dynamic compound swap (e.g. SOFT -> MEDIUM) is recommended during pit stop.
    """
    c1 = compound_before.value if isinstance(compound_before, TireCompound) else str(compound_before).upper()
    c2 = compound_after.value if isinstance(compound_after, TireCompound) else str(compound_after).upper()

    if not TireCompound.has_value(c1):
        raise ValueError(f"Invalid starting compound '{compound_before}'")
    if not TireCompound.has_value(c2):
        raise ValueError(f"Invalid ending compound '{compound_after}'")

    return True
