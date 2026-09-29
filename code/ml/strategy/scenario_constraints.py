# -*- coding: utf-8 -*-
"""
Hard Constraint Engine and Weather Compatibility Policies for G.4.5.2.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from ml.strategy.compounds import TireCompound, validate_compound_transition, get_compound_model
from ml.strategy.stint import validate_stint_sequence
from ml.strategy.scenario import Scenario


DEFAULT_WEATHER_COMPOUND_MAP: Dict[str, List[str]] = {
    "DRY": ["SOFT", "MEDIUM", "HARD"],
    "WET": ["INTERMEDIATE", "WET"],
    "MIXED": ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"],
}


@dataclass
class ScenarioConstraints:
    """
    Configuration for scenario generation search boundaries and hard rules.

    Attributes:
        max_stops: Maximum pit stop count permitted (default 3).
        min_stint_laps: Minimum required laps per stint (default 3).
        pit_step_laps: Grid step interval for candidate pit laps (None = auto based on total_laps).
        max_candidates: Upper limit on generated candidate scenarios before raising error (default 100,000).
        weather_mode: Session weather mode ("DRY", "WET", "MIXED").
        allowed_compounds_by_weather: Dictionary mapping weather mode to allowed compounds.
        require_distinct_dry_compounds: Configurable simulation policy requiring >=2 distinct dry compounds in dry sessions.
    """
    max_stops: int = 3
    min_stint_laps: int = 3
    pit_step_laps: Optional[int] = None
    max_candidates: int = 100000
    weather_mode: str = "DRY"
    allowed_compounds_by_weather: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_WEATHER_COMPOUND_MAP.copy())
    require_distinct_dry_compounds: bool = True

    def __post_init__(self):
        """Validate constraints configuration."""
        self.weather_mode = str(self.weather_mode).upper()

        if self.max_stops < 0:
            raise ValueError(f"max_stops cannot be negative, got {self.max_stops}")
        if self.min_stint_laps <= 0:
            raise ValueError(f"min_stint_laps must be > 0, got {self.min_stint_laps}")
        if self.pit_step_laps is not None and self.pit_step_laps <= 0:
            raise ValueError(f"pit_step_laps must be > 0, got {self.pit_step_laps}")
        if self.max_candidates <= 0:
            raise ValueError(f"max_candidates must be > 0, got {self.max_candidates}")
        if self.weather_mode not in self.allowed_compounds_by_weather:
            raise ValueError(
                f"Unknown weather_mode '{self.weather_mode}'. Valid: {list(self.allowed_compounds_by_weather.keys())}"
            )

    def get_allowed_compounds(self) -> List[str]:
        """Returns allowed compound list for current weather mode."""
        return get_allowed_compounds_for_weather(self.weather_mode, self.allowed_compounds_by_weather)


def get_allowed_compounds_for_weather(weather_mode: str,
                                      mapping: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """Retrieves list of permitted tire compounds for a weather mode."""
    mode = str(weather_mode).upper()
    comp_map = mapping or DEFAULT_WEATHER_COMPOUND_MAP
    if mode not in comp_map:
        raise ValueError(f"Invalid weather_mode '{weather_mode}'. Valid modes: {list(comp_map.keys())}")
    return comp_map[mode]


def validate_scenario_hard_constraints(scenario: Scenario,
                                        constraints: ScenarioConstraints) -> Tuple[bool, List[str]]:
    """
    Evaluates hard constraints against a candidate scenario.

    Returns:
        Tuple of (is_valid: bool, error_messages: List[str]).
    """
    errors: List[str] = []

    # 1. Pit stop count boundary
    if scenario.number_of_stops > constraints.max_stops:
        errors.append(f"Number of pit stops ({scenario.number_of_stops}) exceeds max_stops ({constraints.max_stops})")

    # 2. Allowed compounds for weather mode
    allowed_compounds = get_allowed_compounds_for_weather(constraints.weather_mode, constraints.allowed_compounds_by_weather)
    for c in scenario.compound_sequence:
        if c not in allowed_compounds:
            errors.append(f"Compound '{c}' is not allowed in {constraints.weather_mode} weather mode (allowed: {allowed_compounds})")

    # 3. Minimum stint length
    for stint in scenario.stints:
        if stint.stint_laps < constraints.min_stint_laps:
            errors.append(f"Stint {stint.stint_number} length ({stint.stint_laps} laps) is below min_stint_laps ({constraints.min_stint_laps})")

    # 4. Stint timeline continuity
    try:
        validate_stint_sequence(scenario.stints, scenario.total_laps)
    except ValueError as e:
        errors.append(f"Stint sequence continuity error: {str(e)}")

    # 5. Compound transitions and pit lap boundary matching
    for pit in scenario.pit_stops:
        try:
            validate_compound_transition(pit.compound_before, pit.compound_after)
        except ValueError as e:
            errors.append(f"Pit stop compound transition error: {str(e)}")

        if pit.stint_before < 1 or pit.stint_before > len(scenario.stints):
            errors.append(f"PitStop stint_before ({pit.stint_before}) out of bounds")
        else:
            expected_pit_lap = scenario.stints[pit.stint_before - 1].end_lap
            if pit.pit_lap != expected_pit_lap:
                errors.append(
                    f"PitStop pit_lap ({pit.pit_lap}) does not match end lap of Stint {pit.stint_before} ({expected_pit_lap})"
                )

    # 6. Dry race distinct dry compounds policy
    if (constraints.require_distinct_dry_compounds and
        constraints.weather_mode == "DRY" and
        scenario.number_of_stops > 0):
        dry_set = set(scenario.compound_sequence)
        if len(dry_set) < 2:
            errors.append("Dry race simulation policy requires at least 2 distinct dry compounds for multi-stint strategies")

    is_valid = len(errors) == 0
    return is_valid, errors
