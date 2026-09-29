# -*- coding: utf-8 -*-
"""
Immutable Candidate and Ranked Strategy Data Structures for G.4.5.5 Strategy Optimizer.
"""

import math
from dataclasses import dataclass
from typing import Dict, Any, Optional
from ml.strategy.simulator import SimulationResult
from ml.strategy.validation_result import ValidationResult
from ml.strategy.scenario import Scenario

DEFAULT_RANKING_EXPLANATION = (
    "Ranked primarily by total race time, then by pit-stop count, "
    "final fuel margin, tire wear, and deterministic scenario ID."
)


@dataclass(frozen=True)
class OptimizationCandidate:
    """
    Immutable candidate representation containing only metrics required for strategy ranking.

    Attributes:
        scenario_id: Canonical identifier of the strategy scenario.
        canonical_key: Stint sequence string representation.
        valid: Hard validation status flag from G.4.5.4.
        warning_count: Total non-invalidating warning count.
        total_race_time_sec: Total race completion time (sec).
        pit_stop_count: Number of completed pit stops.
        final_fuel_kg: Remaining fuel mass at finish line (kg).
        avg_final_tire_wear_pct: Average four-wheel tire wear percentage at finish line (%).
    """
    scenario_id: str
    canonical_key: str
    valid: bool
    warning_count: int
    total_race_time_sec: float
    pit_stop_count: int
    final_fuel_kg: float
    avg_final_tire_wear_pct: float

    def __post_init__(self):
        """Validate candidate fields and numeric parameters."""
        if not self.scenario_id:
            raise ValueError("scenario_id cannot be empty")
        if not self.canonical_key:
            raise ValueError("canonical_key cannot be empty")
        if isinstance(self.warning_count, bool) or not isinstance(self.warning_count, int) or self.warning_count < 0:
            raise ValueError(f"warning_count must be a non-negative integer, got {self.warning_count}")
        if isinstance(self.pit_stop_count, bool) or not isinstance(self.pit_stop_count, int) or self.pit_stop_count < 0:
            raise ValueError(f"pit_stop_count must be a non-negative integer, got {self.pit_stop_count}")

        # Numerical safety checks
        for name, val in [
            ("total_race_time_sec", self.total_race_time_sec),
            ("final_fuel_kg", self.final_fuel_kg),
            ("avg_final_tire_wear_pct", self.avg_final_tire_wear_pct),
        ]:
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"Invalid numeric value for {name}: {val}")

        if self.total_race_time_sec < 0:
            raise ValueError(f"total_race_time_sec cannot be negative, got {self.total_race_time_sec}")

    @classmethod
    def from_simulation_and_validation(
        cls,
        sim_result: SimulationResult,
        val_result: ValidationResult,
        scenario: Optional[Scenario] = None,
        canonical_key: Optional[str] = None,
    ) -> "OptimizationCandidate":
        """
        Creates an immutable OptimizationCandidate from upstream G.4.5 simulation and validation results.
        """
        if sim_result is None:
            raise ValueError("sim_result cannot be None")
        if val_result is None:
            raise ValueError("val_result cannot be None")

        key = canonical_key
        if key is None and scenario is not None:
            key = scenario.canonical_key
        if key is None:
            # Reconstruct simple canonical key from stint_summary if scenario not supplied
            if hasattr(sim_result, "stint_summary") and sim_result.stint_summary:
                stint_tokens = []
                for s in sim_result.stint_summary:
                    compound = str(s.get("compound", "UNKNOWN")).upper()
                    start = s.get("start_lap", 1)
                    end = s.get("end_lap", start + s.get("stint_laps", 1) - 1)
                    stint_tokens.append(f"{compound}:{start}-{end}")
                key = "|".join(stint_tokens)
            else:
                key = "UNKNOWN"

        # Calculate average tire wear across 4 wheels
        if sim_result.final_tire_wear:
            wear_vals = list(sim_result.final_tire_wear.values())
            avg_wear = sum(wear_vals) / len(wear_vals)
        else:
            avg_wear = 0.0

        return cls(
            scenario_id=val_result.scenario_id,
            canonical_key=key,
            valid=val_result.valid,
            warning_count=val_result.warning_count,
            total_race_time_sec=sim_result.total_race_time_sec,
            pit_stop_count=sim_result.pit_stop_count,
            final_fuel_kg=sim_result.final_fuel_kg,
            avg_final_tire_wear_pct=avg_wear,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert candidate to dictionary representation."""
        return {
            "scenario_id": self.scenario_id,
            "canonical_key": self.canonical_key,
            "valid": self.valid,
            "warning_count": self.warning_count,
            "total_race_time_sec": round(self.total_race_time_sec, 3),
            "pit_stop_count": self.pit_stop_count,
            "final_fuel_kg": round(self.final_fuel_kg, 3),
            "avg_final_tire_wear_pct": round(self.avg_final_tire_wear_pct, 2),
        }


@dataclass(frozen=True)
class RankedStrategy:
    """
    Immutable output element representing a strategy's final position in the optimization ranking.

    Attributes:
        rank: 1-based ordinal rank position.
        scenario_id: Strategy canonical scenario ID.
        canonical_key: Strategy stint sequence canonical representation.
        total_race_time_sec: Total race completion time (sec).
        pit_stop_count: Number of completed pit stops.
        final_fuel_kg: Remaining fuel mass at finish line (kg).
        avg_final_tire_wear_pct: Average four-wheel tire wear percentage at finish line (%).
        warning_count: Non-invalidating warning count.
        delta_to_leader_sec: Race time difference compared to rank 1 leader (sec).
        ranking_explanation: Human-readable deterministic explanation of ranking decision.
    """
    rank: int
    scenario_id: str
    canonical_key: str
    total_race_time_sec: float
    pit_stop_count: int
    final_fuel_kg: float
    avg_final_tire_wear_pct: float
    warning_count: int
    delta_to_leader_sec: float
    ranking_explanation: str = DEFAULT_RANKING_EXPLANATION

    def __post_init__(self):
        """Validate ranked strategy attributes."""
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError(f"rank must be an integer >= 1, got {self.rank}")
        if not self.scenario_id:
            raise ValueError("scenario_id cannot be empty")
        if not self.canonical_key:
            raise ValueError("canonical_key cannot be empty")
        if isinstance(self.delta_to_leader_sec, (int, float)):
            if math.isnan(self.delta_to_leader_sec) or math.isinf(self.delta_to_leader_sec) or self.delta_to_leader_sec < 0:
                raise ValueError(f"Invalid delta_to_leader_sec: {self.delta_to_leader_sec}")

    @classmethod
    def from_candidate(
        cls,
        candidate: OptimizationCandidate,
        rank: int,
        leader_race_time_sec: float,
        explanation: str = DEFAULT_RANKING_EXPLANATION,
    ) -> "RankedStrategy":
        """
        Builds a RankedStrategy from an OptimizationCandidate and leader race time.
        """
        delta = candidate.total_race_time_sec - leader_race_time_sec
        # Numerical safeguard against small negative float delta due to precision
        if delta < 0 and math.isclose(candidate.total_race_time_sec, leader_race_time_sec, abs_tol=1e-12):
            delta = 0.0

        return cls(
            rank=rank,
            scenario_id=candidate.scenario_id,
            canonical_key=candidate.canonical_key,
            total_race_time_sec=candidate.total_race_time_sec,
            pit_stop_count=candidate.pit_stop_count,
            final_fuel_kg=candidate.final_fuel_kg,
            avg_final_tire_wear_pct=candidate.avg_final_tire_wear_pct,
            warning_count=candidate.warning_count,
            delta_to_leader_sec=delta,
            ranking_explanation=explanation,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert ranked strategy to dictionary representation."""
        return {
            "rank": self.rank,
            "scenario_id": self.scenario_id,
            "canonical_key": self.canonical_key,
            "total_race_time_sec": round(self.total_race_time_sec, 3),
            "pit_stop_count": self.pit_stop_count,
            "final_fuel_kg": round(self.final_fuel_kg, 3),
            "avg_final_tire_wear_pct": round(self.avg_final_tire_wear_pct, 2),
            "warning_count": self.warning_count,
            "delta_to_leader_sec": round(self.delta_to_leader_sec, 3),
            "ranking_explanation": self.ranking_explanation,
        }
