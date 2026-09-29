# -*- coding: utf-8 -*-
"""
Bounded Scenario Generation Engine for G.4.5.2 Strategy Scenario Builder.
"""

import time
import itertools
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional, Set

from ml.strategy.race_config import RaceConfig
from ml.strategy.stint import Stint
from ml.strategy.pit_stop import PitStop
from ml.strategy.compounds import get_compound_model
from ml.strategy.scenario import Scenario
from ml.strategy.scenario_id import generate_canonical_key, generate_deterministic_scenario_id
from ml.strategy.scenario_deduplication import ScenarioDeduplicator
from ml.strategy.scenario_constraints import (
    ScenarioConstraints,
    get_allowed_compounds_for_weather,
    validate_scenario_hard_constraints,
)


class ScenarioGenerationLimitError(ValueError):
    """Exception raised when scenario candidate generation exceeds max_candidates limit."""
    pass


@dataclass
class GenerationResult:
    """
    Summary and output container for a scenario generation run.

    Attributes:
        race_id: Race configuration identifier.
        total_laps: Race distance in laps.
        scenarios: List of valid, deduplicated Scenario objects.
        theoretical_candidate_count: Estimated unconstrained candidate space size.
        candidates_generated: Total candidate combinations generated before filtering.
        candidates_rejected: Count of candidates failing hard constraints.
        duplicates_removed: Count of duplicate canonical strategies removed.
        final_scenario_count: Total valid unique scenarios produced.
        generation_duration_sec: Execution time in seconds.
        generation_metadata: Full configuration and execution metadata.
    """
    race_id: str
    total_laps: int
    scenarios: List[Scenario]
    theoretical_candidate_count: int
    candidates_generated: int
    candidates_rejected: int
    duplicates_removed: int
    final_scenario_count: int
    generation_duration_sec: float
    generation_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert generation summary to dictionary."""
        return {
            "race_id": self.race_id,
            "total_laps": self.total_laps,
            "theoretical_candidate_count": self.theoretical_candidate_count,
            "candidates_generated": self.candidates_generated,
            "candidates_rejected": self.candidates_rejected,
            "duplicates_removed": self.duplicates_removed,
            "final_scenario_count": self.final_scenario_count,
            "generation_duration_sec": round(self.generation_duration_sec, 4),
            "generation_metadata": self.generation_metadata,
        }


def determine_bounded_grid_step(total_laps: int, override_step: Optional[int] = None) -> int:
    """
    Determines bounded pit-lap step interval based on race distance.
    Policy:
        total_laps <= 30  -> step = 1
        30 < total_laps <= 70 -> step = 2
        total_laps > 70   -> step = 5
    """
    if override_step is not None:
        return max(1, override_step)

    if total_laps <= 30:
        return 1
    elif total_laps <= 70:
        return 2
    else:
        return 5


class ScenarioGenerator:
    """
    Deterministic candidate scenario generator enforcing bounded grid step and hard constraints.
    """

    def __init__(self, config: RaceConfig, constraints: Optional[ScenarioConstraints] = None):
        self.config = config
        self.constraints = constraints or ScenarioConstraints()
        self.deduplicator = ScenarioDeduplicator()

    def generate_scenarios(self) -> GenerationResult:
        """
        Executes bounded candidate generation across 0-stop, 1-stop, 2-stop, and 3-stop strategies.

        Returns:
            GenerationResult containing valid, deduplicated scenarios and audit metrics.
        """
        t0 = time.perf_counter()
        self.deduplicator.reset()

        total_laps = self.config.total_laps
        min_stint = self.constraints.min_stint_laps
        max_stops = min(self.constraints.max_stops, total_laps // min_stint)
        pit_step = determine_bounded_grid_step(total_laps, self.constraints.pit_step_laps)

        allowed_compounds = get_allowed_compounds_for_weather(
            self.constraints.weather_mode,
            self.constraints.allowed_compounds_by_weather,
        )

        candidates_generated = 0
        candidates_rejected = 0
        valid_scenarios: List[Scenario] = []

        # 0. Theoretical candidate space estimation
        theoretical_count = self._estimate_theoretical_space(total_laps, max_stops, len(allowed_compounds), min_stint)

        for stops in range(0, max_stops + 1):
            stint_count = stops + 1

            # Scale pit_step for stops >= 3 to maintain bounded candidate space
            effective_step = pit_step
            if stops >= 3 and self.constraints.pit_step_laps is None:
                effective_step = max(pit_step, 4)

            # Generate compound combinations and pre-filter invalid ones early
            raw_comp_combos = list(itertools.product(allowed_compounds, repeat=stint_count))
            compound_combos = []

            for comp_seq in raw_comp_combos:
                # Filter out single-compound sequences if dry distinct compound policy requires distinct dry compounds
                if (stops > 0 and
                    self.constraints.require_distinct_dry_compounds and
                    self.constraints.weather_mode == "DRY" and
                    len(set(comp_seq)) < 2):
                    continue

                # Filter out illegal compound transitions
                valid_trans = True
                for i in range(len(comp_seq) - 1):
                    try:
                        from ml.strategy.compounds import validate_compound_transition
                        validate_compound_transition(comp_seq[i], comp_seq[i+1])
                    except ValueError:
                        valid_trans = False
                        break
                if valid_trans:
                    compound_combos.append(comp_seq)

            # Generate pit lap boundary combinations
            pit_lap_combos = self._generate_pit_lap_combinations(total_laps, stops, min_stint, effective_step)

            for comp_seq in compound_combos:
                for pit_laps in pit_lap_combos:
                    candidates_generated += 1

                    if candidates_generated > self.constraints.max_candidates:
                        raise ScenarioGenerationLimitError(
                            f"Scenario generation exceeded max_candidates limit ({self.constraints.max_candidates}). "
                            f"Consider increasing pit_step_laps (current: {pit_step}) or lowering max_stops."
                        )

                    # Build candidate Scenario object
                    scenario = self._build_candidate_scenario(comp_seq, pit_laps, pit_step)

                    # Validate hard constraints
                    is_valid, errors = validate_scenario_hard_constraints(scenario, self.constraints)

                    if not is_valid:
                        candidates_rejected += 1
                        scenario.validation_status = "INVALID"
                        scenario.validation_errors = errors
                        continue

                    # Deduplicate
                    if self.deduplicator.process_scenario(scenario):
                        valid_scenarios.append(scenario)

        t1 = time.perf_counter()
        duration_sec = t1 - t0

        dedup_metrics = self.deduplicator.get_metrics()

        metadata = {
            "race_id": self.config.race_id,
            "total_laps": total_laps,
            "max_stops": self.constraints.max_stops,
            "min_stint_laps": min_stint,
            "pit_step_laps": pit_step,
            "weather_mode": self.constraints.weather_mode,
            "allowed_compounds": allowed_compounds,
            "require_distinct_dry_compounds": self.constraints.require_distinct_dry_compounds,
            "max_candidates_ceiling": self.constraints.max_candidates,
        }

        return GenerationResult(
            race_id=self.config.race_id,
            total_laps=total_laps,
            scenarios=valid_scenarios,
            theoretical_candidate_count=theoretical_count,
            candidates_generated=candidates_generated,
            candidates_rejected=candidates_rejected,
            duplicates_removed=dedup_metrics["duplicates_removed"],
            final_scenario_count=len(valid_scenarios),
            generation_duration_sec=duration_sec,
            generation_metadata=metadata,
        )

    def _generate_pit_lap_combinations(self, total_laps: int, stops: int, min_stint: int, step: int) -> List[Tuple[int, ...]]:
        """Generates bounded pit lap combination tuples."""
        if stops == 0:
            return [()]

        valid_pit_range = list(range(min_stint, total_laps - min_stint + 1, step))
        # Ensure final boundary lap is included if step > 1
        last_possible = total_laps - min_stint
        if last_possible > min_stint and last_possible not in valid_pit_range:
            valid_pit_range.append(last_possible)
            valid_pit_range.sort()

        combinations = []
        for combo in itertools.combinations(valid_pit_range, stops):
            # Check stint length constraint for intermediate stints
            valid_combo = True
            prev_lap = 0
            for lap in combo:
                if (lap - prev_lap) < min_stint:
                    valid_combo = False
                    break
                prev_lap = lap

            if (total_laps - prev_lap) < min_stint:
                valid_combo = False

            if valid_combo:
                combinations.append(combo)

        return combinations

    def _build_candidate_scenario(self, comp_seq: Tuple[str, ...], pit_laps: Tuple[int, ...], pit_step: int) -> Scenario:
        """Constructs a candidate Scenario object from compound sequence and pit laps."""
        total_laps = self.config.total_laps
        starting_fuel = self.config.starting_fuel
        fuel_per_lap = 2.0  # Simulation assumption

        stints: List[Stint] = []
        pit_stops: List[PitStop] = []

        stint_starts = [1] + [lap + 1 for lap in pit_laps]
        stint_ends = list(pit_laps) + [total_laps]

        current_fuel = starting_fuel

        for i, (start, end) in enumerate(zip(stint_starts, stint_ends)):
            comp = comp_seq[i]
            stint_laps = (end - start) + 1
            fuel_burned = stint_laps * fuel_per_lap
            ending_fuel = max(0.0, current_fuel - fuel_burned)

            stint = Stint(
                stint_id=f"STINT_{i+1:02d}",
                stint_number=i + 1,
                compound=comp,
                start_lap=start,
                end_lap=end,
                starting_fuel=current_fuel,
                ending_fuel=ending_fuel,
                starting_tire_wear=0.0,
                ending_tire_wear=min(100.0, stint_laps * 1.2),
            )
            stints.append(stint)
            current_fuel = ending_fuel

            if i < len(pit_laps):
                pit = PitStop(
                    pit_stop_id=f"PIT_{i+1:02d}",
                    pit_lap=pit_laps[i],
                    compound_before=comp_seq[i],
                    compound_after=comp_seq[i+1],
                    stint_before=i + 1,
                    stint_after=i + 2,
                    duration_sec=self.config.pit_stop_loss_sec,
                )
                pit_stops.append(pit)

        canonical_key = generate_canonical_key(stints)
        scenario_id = generate_deterministic_scenario_id(self.config.race_id, canonical_key)

        return Scenario(
            scenario_id=scenario_id,
            race_id=self.config.race_id,
            total_laps=total_laps,
            starting_compound=comp_seq[0],
            compound_sequence=list(comp_seq),
            stints=stints,
            pit_stops=pit_stops,
            number_of_stops=len(pit_stops),
            number_of_stints=len(stints),
            generation_method=f"BOUNDED_GRID_STEP_{pit_step}",
            validation_status="VALID",
            validation_errors=[],
            generation_metadata={"pit_step_laps": pit_step},
        )

    def _estimate_theoretical_space(self, total_laps: int, max_stops: int, compounds_count: int, min_stint: int) -> int:
        """Estimates total unconstrained candidate space size for reference metadata."""
        count = 0
        for k in range(0, max_stops + 1):
            comp_perms = compounds_count ** (k + 1)
            # Theoretical unconstrained combinations
            n_choices = total_laps - k * min_stint + k
            if n_choices >= k and k >= 0:
                import math
                combos = math.comb(n_choices, k)
            else:
                combos = 1
            count += comp_perms * combos
        return count
