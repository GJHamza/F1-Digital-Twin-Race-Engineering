# -*- coding: utf-8 -*-
"""
Deterministic Strategy Simulator for G.4.5 Strategy Intelligence.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from ml.strategy.race_config import RaceConfig
from ml.strategy.stint import Stint, validate_stint_sequence
from ml.strategy.pit_stop import PitStop
from ml.strategy.compounds import get_compound_model
from ml.strategy.fuel_model import FuelModel
from ml.strategy.strategy_state import StrategyState, VehicleStatus


@dataclass
class SimulationResult:
    """
    Complete output container for a deterministic race strategy simulation run.

    Attributes:
        race_id: Race identifier.
        total_laps: Total race laps completed.
        total_race_time_sec: Calculated cumulative total race time (sec).
        pit_stop_count: Total pit stops completed.
        total_pit_time_sec: Cumulative time spent in pit stops (sec).
        final_fuel_kg: Fuel mass remaining at checkered flag (kg).
        total_fuel_consumed_kg: Total fuel consumed during race (kg).
        final_tire_wear: Final four-wheel tire wear dict (%).
        stint_summary: List of stint summaries.
        pit_summary: List of pit stop summaries.
        lap_records: List of per-lap telemetry state snapshots.
        is_feasible: Boolean indicating if all physical/regulatory constraints were met.
        warnings: List of validation or boundary warnings.
    """
    race_id: str
    total_laps: int
    total_race_time_sec: float
    pit_stop_count: int
    total_pit_time_sec: float
    final_fuel_kg: float
    total_fuel_consumed_kg: float
    final_tire_wear: Dict[str, float]
    stint_summary: List[Dict[str, Any]]
    pit_summary: List[Dict[str, Any]]
    lap_records: List[Dict[str, Any]]
    is_feasible: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "race_id": self.race_id,
            "total_laps": self.total_laps,
            "total_race_time_sec": round(self.total_race_time_sec, 3),
            "pit_stop_count": self.pit_stop_count,
            "total_pit_time_sec": round(self.total_pit_time_sec, 2),
            "final_fuel_kg": round(self.final_fuel_kg, 3),
            "total_fuel_consumed_kg": round(self.total_fuel_consumed_kg, 3),
            "final_tire_wear": {k: round(v, 2) for k, v in self.final_tire_wear.items()},
            "stint_count": len(self.stint_summary),
            "is_feasible": self.is_feasible,
            "warnings": self.warnings,
        }


class StrategySimulator:
    """
    Engine for executing deterministic step-by-step race strategy simulations.
    """

    def __init__(self, config: RaceConfig):
        self.config = config

    def simulate_strategy(self, stints: List[Stint], pit_stops: List[PitStop] = None,
                          base_lap_time_sec: float = 90.0) -> SimulationResult:
        """
        Executes a deterministic simulation of the provided stint schedule and pit stop events.

        Args:
            stints: List of Stint instances defining the race tire plan.
            pit_stops: Optional list of PitStop events occurring between stints.
            base_lap_time_sec: Base lap time in seconds (default 90.0s).

        Returns:
            SimulationResult containing full lap history and metrics.
        """
        pit_stops = pit_stops or []
        validate_stint_sequence(stints, self.config.total_laps)

        # Validate pit stops match stint transitions
        sorted_stints = sorted(stints, key=lambda s: s.stint_number)
        pit_dict: Dict[int, PitStop] = {ps.pit_lap: ps for ps in pit_stops}

        if len(pit_stops) != len(stints) - 1:
            raise ValueError(
                f"Mismatch between number of stints ({len(stints)}) and pit stops ({len(pit_stops)}). "
                f"Expected exactly {len(stints) - 1} pit stops."
            )

        fuel_model = FuelModel(starting_fuel=self.config.starting_fuel)
        current_stint_idx = 0
        current_stint = sorted_stints[current_stint_idx]

        tire_wear = {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0}
        total_race_time_sec = 0.0
        total_pit_time_sec = 0.0
        pit_stop_count = 0
        lap_records: List[Dict[str, Any]] = []
        warnings: List[str] = []
        is_feasible = True

        stint_wear_accumulated = 0.0
        stint_laps_completed = 0

        for lap in range(1, self.config.total_laps + 1):
            # Check if entering a new stint at this lap
            if lap > current_stint.end_lap:
                current_stint_idx += 1
                current_stint = sorted_stints[current_stint_idx]
                # Reset tire wear for new tire set
                tire_wear = {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0}
                stint_wear_accumulated = 0.0
                stint_laps_completed = 0

            compound_info = get_compound_model(current_stint.compound)
            
            # Tire wear increment for current lap (based on compound wear_multiplier)
            base_lap_wear = 0.8 * compound_info.wear_multiplier
            stint_laps_completed += 1

            tire_wear["FL"] = min(100.0, tire_wear["FL"] + base_lap_wear * 1.05)
            tire_wear["FR"] = min(100.0, tire_wear["FR"] + base_lap_wear * 1.02)
            tire_wear["RL"] = min(100.0, tire_wear["RL"] + base_lap_wear * 0.98)
            tire_wear["RR"] = min(100.0, tire_wear["RR"] + base_lap_wear * 0.95)

            avg_wear = sum(tire_wear.values()) / 4.0

            if avg_wear > self.config.max_tire_wear:
                is_feasible = False
                warnings.append(f"Tire wear exceeded limit ({avg_wear:.1f}% > {self.config.max_tire_wear:.1f}%) on Lap {lap}")

            # Fuel depletion
            fuel_state = fuel_model.consume_fuel(laps=1.0)
            if fuel_state.fuel_remaining < 0.0:
                is_feasible = False
                warnings.append(f"Fuel depleted on Lap {lap}")

            # Lap time calculation with fuel mass effect & wear degradation
            fuel_mass_effect = (fuel_state.fuel_remaining / self.config.starting_fuel) * 1.5  # Heavy fuel penalty
            wear_degradation_effect = (avg_wear / 100.0) * 2.0  # Worn tire penalty
            lap_time = base_lap_time_sec + fuel_mass_effect + wear_degradation_effect

            pit_loss_lap = 0.0
            vehicle_status = VehicleStatus.ON_TRACK

            # Check if pit stop occurs at end of this lap
            if lap in pit_dict:
                pit = pit_dict[lap]
                pit_loss_lap = pit.duration_sec
                total_pit_time_sec += pit_loss_lap
                pit_stop_count += 1
                vehicle_status = VehicleStatus.IN_PIT

            total_race_time_sec += (lap_time + pit_loss_lap)

            lap_records.append({
                "stint_id": f"STINT_{current_stint.stint_number:02d}",
                "stint_number": current_stint.stint_number,
                "tire_compound": current_stint.compound,
                "pit_stop_count": pit_stop_count,
                "vehicle_status": vehicle_status.value,
                "avg_tire_wear_pct": round(avg_wear, 3),
                "fuel_remaining_kg": round(fuel_state.fuel_remaining, 3),
                "race_lap": lap,
                "race_id": self.config.race_id,
                "tire_wear_fl": round(tire_wear["FL"], 2),
                "tire_wear_fr": round(tire_wear["FR"], 2),
                "tire_wear_rl": round(tire_wear["RL"], 2),
                "tire_wear_rr": round(tire_wear["RR"], 2),
                "lap_time_sec": round(lap_time, 3),
                "pit_loss_sec": round(pit_loss_lap, 2),
            })

        stint_summary = [s.to_dict() for s in sorted_stints]
        pit_summary = [p.to_dict() for p in pit_stops]

        return SimulationResult(
            race_id=self.config.race_id,
            total_laps=self.config.total_laps,
            total_race_time_sec=total_race_time_sec,
            pit_stop_count=pit_stop_count,
            total_pit_time_sec=total_pit_time_sec,
            final_fuel_kg=fuel_model.get_state().fuel_remaining,
            total_fuel_consumed_kg=fuel_model.get_state().fuel_consumed,
            final_tire_wear=tire_wear,
            stint_summary=stint_summary,
            pit_summary=pit_summary,
            lap_records=lap_records,
            is_feasible=is_feasible,
            warnings=warnings,
        )
