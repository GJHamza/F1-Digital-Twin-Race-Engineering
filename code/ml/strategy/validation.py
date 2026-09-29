# -*- coding: utf-8 -*-
"""
Validation Utility Functions for G.4.5 Strategy Intelligence.
"""

from typing import List, Dict, Any, Union
from ml.strategy.race_config import RaceConfig
from ml.strategy.stint import Stint, validate_stint_sequence
from ml.strategy.pit_stop import PitStop
from ml.strategy.compounds import get_compound_model, validate_compound_transition
from ml.strategy.fuel_model import FuelState
from ml.strategy.strategy_state import StrategyState


class StrategyValidationError(ValueError):
    """Explicit exception raised when strategy validation rules are violated."""
    pass


def validate_race_config(config: RaceConfig) -> bool:
    """Validates RaceConfig object rules."""
    if not isinstance(config, RaceConfig):
        raise StrategyValidationError(f"Expected RaceConfig instance, got {type(config)}")
    return True


def validate_stint(stint: Stint) -> bool:
    """Validates Stint object rules."""
    if not isinstance(stint, Stint):
        raise StrategyValidationError(f"Expected Stint instance, got {type(stint)}")
    return True


def validate_pit_stop(pit_stop: PitStop) -> bool:
    """Validates PitStop object rules."""
    if not isinstance(pit_stop, PitStop):
        raise StrategyValidationError(f"Expected PitStop instance, got {type(pit_stop)}")
    return True


def validate_fuel_state(fuel_state: FuelState) -> bool:
    """Validates FuelState object rules."""
    if not isinstance(fuel_state, FuelState):
        raise StrategyValidationError(f"Expected FuelState instance, got {type(fuel_state)}")
    return True


def validate_strategy_state(state: StrategyState) -> bool:
    """Validates StrategyState object rules."""
    if not isinstance(state, StrategyState):
        raise StrategyValidationError(f"Expected StrategyState instance, got {type(state)}")
    return True


def validate_simulation_inputs(config: RaceConfig, stints: List[Stint], pit_stops: List[PitStop] = None) -> bool:
    """
    Comprehensive input validator ensuring that config, stint plan, and pit stop schedule
    are physically and logically consistent before executing simulation.
    """
    validate_race_config(config)
    pit_stops = pit_stops or []

    for s in stints:
        validate_stint(s)

    for p in pit_stops:
        validate_pit_stop(p)

    # Validate stint sequence timeline matches race length
    validate_stint_sequence(stints, config.total_laps)

    # Validate pit stops match stint boundary laps
    sorted_stints = sorted(stints, key=lambda s: s.stint_number)
    for p in pit_stops:
        if p.stint_before < 1 or p.stint_before >= len(sorted_stints):
            raise StrategyValidationError(
                f"PitStop stint_before ({p.stint_before}) out of bounds for stint count ({len(sorted_stints)})"
            )
        expected_pit_lap = sorted_stints[p.stint_before - 1].end_lap
        if p.pit_lap != expected_pit_lap:
            raise StrategyValidationError(
                f"PitStop pit_lap ({p.pit_lap}) does not match ending lap of Stint {p.stint_before} ({expected_pit_lap})"
            )

    return True
