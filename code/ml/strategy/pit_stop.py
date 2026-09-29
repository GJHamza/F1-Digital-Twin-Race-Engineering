# -*- coding: utf-8 -*-
"""
Pit Stop Event Model for G.4.5 Strategy Intelligence.
"""

from dataclasses import dataclass
from typing import Dict, Any, Union
from ml.strategy.config import DEFAULT_PIT_STOP_LOSS_SEC, MIN_PIT_STOP_DURATION_SEC
from ml.strategy.compounds import validate_compound_transition, get_compound_model


@dataclass
class PitStop:
    """
    Representation of a pit stop event occurring between race stints.

    Attributes:
        pit_stop_id: Unique string identifier for pit stop event.
        pit_lap: Lap number on which pit entry occurs.
        duration_sec: Total pit stop time loss in seconds (stationary + pit lane loss).
        compound_before: Tire compound unmounted at pit stop.
        compound_after: Tire compound mounted during pit stop.
        stint_before: Stint index preceding pit stop.
        stint_after: Stint index following pit stop.
    """
    pit_stop_id: str
    pit_lap: int
    compound_before: str
    compound_after: str
    stint_before: int
    stint_after: int
    duration_sec: float = DEFAULT_PIT_STOP_LOSS_SEC

    def __post_init__(self):
        """Validate pit stop parameters."""
        self.compound_before = str(self.compound_before).upper()
        self.compound_after = str(self.compound_after).upper()

        validate_compound_transition(self.compound_before, self.compound_after)

        if self.pit_lap < 1:
            raise ValueError(f"pit_lap must be >= 1, got {self.pit_lap}")
        if self.duration_sec < MIN_PIT_STOP_DURATION_SEC:
            raise ValueError(f"duration_sec must be >= {MIN_PIT_STOP_DURATION_SEC} sec, got {self.duration_sec}")
        if self.stint_before < 1:
            raise ValueError(f"stint_before must be >= 1, got {self.stint_before}")
        if self.stint_after != self.stint_before + 1:
            raise ValueError(f"stint_after ({self.stint_after}) must equal stint_before + 1 ({self.stint_before + 1})")

    def to_dict(self) -> Dict[str, Any]:
        """Convert pit stop properties to dictionary representation."""
        return {
            "pit_stop_id": self.pit_stop_id,
            "pit_lap": self.pit_lap,
            "duration_sec": self.duration_sec,
            "compound_before": self.compound_before,
            "compound_after": self.compound_after,
            "stint_before": self.stint_before,
            "stint_after": self.stint_after,
        }
