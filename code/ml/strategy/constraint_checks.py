# -*- coding: utf-8 -*-
"""
Constraint Checkers Module for G.4.5.4 Strategy Constraint Validator.
Provides modular, read-only validation functions evaluating G.4.5.3 SimulationResult.
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from ml.strategy.race_config import RaceConfig
from ml.strategy.config import MIN_PIT_STOP_DURATION_SEC
from ml.strategy.compounds import TireCompound, validate_compound_transition, get_compound_model
from ml.strategy.stint import validate_stint_sequence
from ml.strategy.scenario_constraints import ScenarioConstraints, get_allowed_compounds_for_weather
from ml.strategy.simulator import SimulationResult
from ml.strategy.validation_result import Violation


def check_fuel_constraints(result: SimulationResult,
                           config: RaceConfig,
                           constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates hard and soft fuel constraints."""
    violations: List[Violation] = []
    warnings: List[str] = []

    # 1. Inspect overall final fuel
    if result.final_fuel_kg < 0.0:
        violations.append(Violation(
            constraint_id="FUEL_DEPLETED",
            category="FUEL",
            severity="CRITICAL",
            message=f"Final fuel remaining ({result.final_fuel_kg:.3f} kg) is negative.",
            actual_value=result.final_fuel_kg,
            expected_value=">= 0.0",
        ))

    # 2. Inspect per-lap fuel levels
    for record in result.lap_records:
        fuel = record.get("fuel_remaining_kg", 0.0)
        lap = record.get("race_lap", None)
        if math.isnan(fuel) or math.isinf(fuel):
            violations.append(Violation(
                constraint_id="NUMERICAL_ANOMALY_NAN",
                category="FUEL",
                severity="CRITICAL",
                message=f"Fuel remaining on lap {lap} contains NaN/Inf.",
                actual_value=fuel,
                expected_value="Valid float",
                lap_number=lap,
            ))
        elif fuel < 0.0:
            violations.append(Violation(
                constraint_id="FUEL_DEPLETED_ON_LAP",
                category="FUEL",
                severity="CRITICAL",
                message=f"Fuel depleted on lap {lap} ({fuel:.3f} kg remaining).",
                actual_value=fuel,
                expected_value=">= 0.0",
                lap_number=lap,
                stint_id=record.get("stint_id"),
            ))

    # 3. Soft condition: low fuel margin alert (final fuel < 5.0 kg)
    if result.final_fuel_kg >= 0.0 and result.final_fuel_kg < 5.0:
        warnings.append(f"Low fuel margin: final fuel remaining ({result.final_fuel_kg:.2f} kg) is below 5.0 kg soft warning threshold.")

    return violations, warnings


def check_tire_constraints(result: SimulationResult,
                           config: RaceConfig,
                           constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates hard and soft tire wear/degradation constraints across all four wheels."""
    violations: List[Violation] = []
    warnings: List[str] = []

    max_wear = config.max_tire_wear

    # 1. Final tire wear check
    for wheel, wear in result.final_tire_wear.items():
        if math.isnan(wear) or math.isinf(wear):
            violations.append(Violation(
                constraint_id="NUMERICAL_ANOMALY_NAN",
                category="TIRE",
                severity="CRITICAL",
                message=f"Final tire wear on wheel {wheel} contains NaN/Inf.",
                actual_value=wear,
                expected_value=f"[0.0, {max_wear:.1f}]",
            ))
        elif wear > max_wear:
            violations.append(Violation(
                constraint_id="TIRE_WEAR_EXCEEDED",
                category="TIRE",
                severity="CRITICAL",
                message=f"Final tire wear on wheel {wheel} ({wear:.1f}%) exceeds maximum limit ({max_wear:.1f}%).",
                actual_value=wear,
                expected_value=f"<= {max_wear:.1f}",
            ))

    # 2. Per-lap tire wear & degradation check
    high_wear_warned_laps = set()
    for record in result.lap_records:
        lap = record.get("race_lap", None)
        stint_id = record.get("stint_id")
        wheels = ["fl", "fr", "rl", "rr"]
        
        # Check individual wheel wear
        for w in wheels:
            col_wear = f"tire_wear_{w}"
            wear_val = record.get(col_wear, 0.0)

            if math.isnan(wear_val) or math.isinf(wear_val):
                violations.append(Violation(
                    constraint_id="NUMERICAL_ANOMALY_NAN",
                    category="TIRE",
                    severity="CRITICAL",
                    message=f"Tire wear on wheel {w.upper()} on lap {lap} contains NaN/Inf.",
                    actual_value=wear_val,
                    expected_value=f"[0.0, {max_wear:.1f}]",
                    lap_number=lap,
                    stint_id=stint_id,
                ))
            elif wear_val < 0.0:
                violations.append(Violation(
                    constraint_id="INVALID_TIRE_WEAR",
                    category="TIRE",
                    severity="CRITICAL",
                    message=f"Negative tire wear ({wear_val:.2f}%) recorded on wheel {w.upper()} on lap {lap}.",
                    actual_value=wear_val,
                    expected_value=">= 0.0",
                    lap_number=lap,
                    stint_id=stint_id,
                ))
            elif wear_val > max_wear:
                violations.append(Violation(
                    constraint_id="TIRE_WEAR_EXCEEDED_ON_LAP",
                    category="TIRE",
                    severity="CRITICAL",
                    message=f"Tire wear on wheel {w.upper()} ({wear_val:.1f}%) exceeded maximum limit ({max_wear:.1f}%) on lap {lap}.",
                    actual_value=wear_val,
                    expected_value=f"<= {max_wear:.1f}",
                    lap_number=lap,
                    stint_id=stint_id,
                ))
            elif wear_val > 80.0 and lap not in high_wear_warned_laps:
                high_wear_warned_laps.add(lap)
                warnings.append(f"High tire degradation: tire wear on lap {lap} ({wear_val:.1f}%) exceeds 80.0% soft warning threshold.")

        # Check degradation non-negativity
        for w in wheels:
            col_deg = f"degradation_{w}"
            if col_deg in record:
                deg_val = record[col_deg]
                if math.isnan(deg_val) or math.isinf(deg_val):
                    violations.append(Violation(
                        constraint_id="NUMERICAL_ANOMALY_NAN",
                        category="TIRE",
                        severity="CRITICAL",
                        message=f"Degradation on wheel {w.upper()} on lap {lap} contains NaN/Inf.",
                        actual_value=deg_val,
                        expected_value=">= 0.0",
                        lap_number=lap,
                        stint_id=stint_id,
                    ))
                elif deg_val < 0.0:
                    violations.append(Violation(
                        constraint_id="NEGATIVE_DEGRADATION",
                        category="TIRE",
                        severity="HIGH",
                        message=f"Negative degradation delta ({deg_val:.3f}) recorded on wheel {w.upper()} on lap {lap}.",
                        actual_value=deg_val,
                        expected_value=">= 0.0",
                        lap_number=lap,
                        stint_id=stint_id,
                    ))

    return violations, warnings


def check_stint_constraints(result: SimulationResult,
                            config: RaceConfig,
                            constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates stint timeline continuity, min stint length, and index consistency."""
    violations: List[Violation] = []
    warnings: List[str] = []

    stints = result.stint_summary
    if not stints:
        violations.append(Violation(
            constraint_id="EMPTY_STINT_SUMMARY",
            category="STINT",
            severity="CRITICAL",
            message="Simulation result contains empty stint summary.",
            actual_value=0,
            expected_value=">= 1 stint",
        ))
        return violations, warnings

    sorted_stints = sorted(stints, key=lambda s: s.get("stint_number", 0))

    # 1. Start lap check
    first_stint = sorted_stints[0]
    if first_stint.get("start_lap") != 1:
        violations.append(Violation(
            constraint_id="STINT_START_LAP_INVALID",
            category="STINT",
            severity="CRITICAL",
            message=f"First stint starts on lap {first_stint.get('start_lap')}, expected lap 1.",
            actual_value=first_stint.get("start_lap"),
            expected_value=1,
            lap_number=first_stint.get("start_lap"),
            stint_id=first_stint.get("stint_id"),
        ))

    # 2. Final stint end lap check
    final_stint = sorted_stints[-1]
    if final_stint.get("end_lap") != config.total_laps:
        violations.append(Violation(
            constraint_id="STINT_END_LAP_INVALID",
            category="STINT",
            severity="CRITICAL",
            message=f"Final stint ends on lap {final_stint.get('end_lap')}, expected race distance ({config.total_laps}).",
            actual_value=final_stint.get("end_lap"),
            expected_value=config.total_laps,
            lap_number=final_stint.get("end_lap"),
            stint_id=final_stint.get("stint_id"),
        ))

    # 3. Contiguity & min length checks
    stint_ids_seen = set()
    for i, s in enumerate(sorted_stints):
        stint_no = s.get("stint_number", i + 1)
        stint_id = s.get("stint_id", f"STINT_{stint_no:02d}")
        start_lap = s.get("start_lap", 0)
        end_lap = s.get("end_lap", 0)
        stint_laps = s.get("stint_laps", (end_lap - start_lap) + 1)

        # Unique ID check
        if stint_id in stint_ids_seen:
            violations.append(Violation(
                constraint_id="DUPLICATE_STINT_ID",
                category="STINT",
                severity="HIGH",
                message=f"Duplicate stint ID '{stint_id}' detected.",
                actual_value=stint_id,
                expected_value="Unique stint_id",
                stint_id=stint_id,
            ))
        stint_ids_seen.add(stint_id)

        # Min stint length check
        if stint_laps < config.min_stint_laps:
            violations.append(Violation(
                constraint_id="STINT_TOO_SHORT",
                category="STINT",
                severity="HIGH",
                message=f"Stint {stint_no} length ({stint_laps} laps) is below minimum required length ({config.min_stint_laps} laps).",
                actual_value=stint_laps,
                expected_value=f">= {config.min_stint_laps}",
                lap_number=start_lap,
                stint_id=stint_id,
            ))

        # Soft warning for long stints (> 35 laps)
        if stint_laps > 35:
            warnings.append(f"Extended stint length: Stint {stint_no} ({stint_laps} laps) exceeds 35-lap soft warning threshold.")

        # Timeline continuity with previous stint
        if i > 0:
            prev = sorted_stints[i - 1]
            prev_end = prev.get("end_lap", 0)
            if start_lap > prev_end + 1:
                violations.append(Violation(
                    constraint_id="STINT_GAP",
                    category="STINT",
                    severity="CRITICAL",
                    message=f"Timeline gap detected between Stint {prev.get('stint_number')} (ends lap {prev_end}) and Stint {stint_no} (starts lap {start_lap}).",
                    actual_value=start_lap - prev_end - 1,
                    expected_value=0,
                    lap_number=start_lap,
                    stint_id=stint_id,
                ))
            elif start_lap <= prev_end:
                violations.append(Violation(
                    constraint_id="STINT_OVERLAP",
                    category="STINT",
                    severity="CRITICAL",
                    message=f"Timeline overlap detected between Stint {prev.get('stint_number')} (ends lap {prev_end}) and Stint {stint_no} (starts lap {start_lap}).",
                    actual_value=prev_end - start_lap + 1,
                    expected_value=0,
                    lap_number=start_lap,
                    stint_id=stint_id,
                ))

    return violations, warnings


def check_pit_stop_constraints(result: SimulationResult,
                               config: RaceConfig,
                               constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates pit stop laps, durations, compound transitions, and count matching."""
    violations: List[Violation] = []
    warnings: List[str] = []

    pit_summary = result.pit_summary
    stint_summary = result.stint_summary
    stint_count = len(stint_summary)

    # 1. Pit stop count vs stint count check
    expected_pit_count = max(0, stint_count - 1)
    if result.pit_stop_count != expected_pit_count:
        violations.append(Violation(
            constraint_id="PIT_COUNT_MISMATCH",
            category="PIT_STOP",
            severity="CRITICAL",
            message=f"Pit stop count ({result.pit_stop_count}) does not match expected count ({expected_pit_count}) for {stint_count} stints.",
            actual_value=result.pit_stop_count,
            expected_value=expected_pit_count,
        ))

    # 2. Validate individual pit stop events
    pit_laps_seen = set()
    total_duration = 0.0

    for idx, pit in enumerate(pit_summary):
        pit_lap = pit.get("pit_lap", 0)
        duration = pit.get("duration_sec", 0.0)
        c_before = pit.get("compound_before", "")
        c_after = pit.get("compound_after", "")
        stint_b = pit.get("stint_before", 0)
        stint_a = pit.get("stint_after", 0)

        total_duration += duration

        # Pit lap bounds check
        if pit_lap < 1 or pit_lap >= config.total_laps:
            violations.append(Violation(
                constraint_id="PIT_LAP_OUT_OF_BOUNDS",
                category="PIT_STOP",
                severity="CRITICAL",
                message=f"Pit stop lap {pit_lap} is outside valid race bounds [1, {config.total_laps - 1}].",
                actual_value=pit_lap,
                expected_value=f"1..{config.total_laps - 1}",
                lap_number=pit_lap,
            ))

        # Duplicate pit lap check
        if pit_lap in pit_laps_seen:
            violations.append(Violation(
                constraint_id="DUPLICATE_PIT_LAP",
                category="PIT_STOP",
                severity="CRITICAL",
                message=f"Multiple pit stops recorded on lap {pit_lap}.",
                actual_value=pit_lap,
                expected_value="Unique pit_lap",
                lap_number=pit_lap,
            ))
        pit_laps_seen.add(pit_lap)

        # Min pit duration check
        if duration < MIN_PIT_STOP_DURATION_SEC:
            violations.append(Violation(
                constraint_id="PIT_DURATION_TOO_SHORT",
                category="PIT_STOP",
                severity="HIGH",
                message=f"Pit stop duration ({duration:.2f}s) is below minimum threshold ({MIN_PIT_STOP_DURATION_SEC}s).",
                actual_value=duration,
                expected_value=f">= {MIN_PIT_STOP_DURATION_SEC}s",
                lap_number=pit_lap,
            ))

        # Stint transition matching check
        if stint_a != stint_b + 1:
            violations.append(Violation(
                constraint_id="PIT_STINT_ORDER_INVALID",
                category="PIT_STOP",
                severity="HIGH",
                message=f"Pit stop connects non-adjacent stints ({stint_b} to {stint_a}).",
                actual_value=f"{stint_b}->{stint_a}",
                expected_value=f"{stint_b}->{stint_b + 1}",
                lap_number=pit_lap,
            ))

        # Compound transition matching check against stint summary
        if 1 <= stint_b <= len(stint_summary) and 1 <= stint_a <= len(stint_summary):
            actual_comp_b = stint_summary[stint_b - 1].get("compound", "")
            actual_comp_a = stint_summary[stint_a - 1].get("compound", "")

            if c_before.upper() != actual_comp_b.upper():
                violations.append(Violation(
                    constraint_id="COMPOUND_TRANSITION_MISMATCH",
                    category="PIT_STOP",
                    severity="HIGH",
                    message=f"Pit stop unmounted compound '{c_before}' does not match Stint {stint_b} compound '{actual_comp_b}'.",
                    actual_value=c_before,
                    expected_value=actual_comp_b,
                    lap_number=pit_lap,
                ))

            if c_after.upper() != actual_comp_a.upper():
                violations.append(Violation(
                    constraint_id="COMPOUND_TRANSITION_MISMATCH",
                    category="PIT_STOP",
                    severity="HIGH",
                    message=f"Pit stop mounted compound '{c_after}' does not match Stint {stint_a} compound '{actual_comp_a}'.",
                    actual_value=c_after,
                    expected_value=actual_comp_a,
                    lap_number=pit_lap,
                ))

    # 3. Pit duration sum reconciliation
    if not math.isclose(total_duration, result.total_pit_time_sec, abs_tol=1e-3):
        violations.append(Violation(
            constraint_id="TOTAL_PIT_TIME_MISMATCH",
            category="PIT_STOP",
            severity="HIGH",
            message=f"Sum of pit stop durations ({total_duration:.2f}s) does not match total pit time ({result.total_pit_time_sec:.2f}s).",
            actual_value=result.total_pit_time_sec,
            expected_value=round(total_duration, 2),
        ))

    return violations, warnings


def check_compound_constraints(result: SimulationResult,
                               config: RaceConfig,
                               constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates tire compound recognition, weather mode compatibility, and dry race regulations."""
    violations: List[Violation] = []
    warnings: List[str] = []

    stints = result.stint_summary
    compounds_used: List[str] = []

    allowed_compounds = get_allowed_compounds_for_weather(
        constraints.weather_mode,
        constraints.allowed_compounds_by_weather,
    )

    for s in stints:
        comp_str = str(s.get("compound", "")).upper()
        stint_no = s.get("stint_number")

        # 1. Recognized compound check
        if not TireCompound.has_value(comp_str):
            violations.append(Violation(
                constraint_id="UNKNOWN_COMPOUND",
                category="COMPOUND",
                severity="CRITICAL",
                message=f"Unrecognized tire compound '{comp_str}' in Stint {stint_no}.",
                actual_value=comp_str,
                expected_value="Valid TireCompound",
                stint_id=s.get("stint_id"),
            ))
            continue

        # 2. Weather mode compatibility check
        if comp_str not in allowed_compounds:
            violations.append(Violation(
                constraint_id="WEATHER_COMPOUND_ILLEGAL",
                category="COMPOUND",
                severity="CRITICAL",
                message=f"Compound '{comp_str}' is not permitted in {constraints.weather_mode} weather mode.",
                actual_value=comp_str,
                expected_value=allowed_compounds,
                stint_id=s.get("stint_id"),
            ))

        compounds_used.append(comp_str)

    # 3. Transition validity check
    for i in range(len(compounds_used) - 1):
        c1 = compounds_used[i]
        c2 = compounds_used[i + 1]
        try:
            validate_compound_transition(c1, c2)
        except ValueError as e:
            violations.append(Violation(
                constraint_id="ILLEGAL_COMPOUND_TRANSITION",
                category="COMPOUND",
                severity="HIGH",
                message=f"Illegal compound transition from '{c1}' to '{c2}': {str(e)}",
                actual_value=f"{c1}->{c2}",
                expected_value="Valid transition",
            ))

    # 4. Dry race distinct dry compounds policy check
    if (constraints.require_distinct_dry_compounds and
        constraints.weather_mode == "DRY" and
        len(stints) > 1):
        unique_compounds = set(compounds_used)
        if len(unique_compounds) < 2:
            violations.append(Violation(
                constraint_id="DRY_RACE_SINGLE_COMPOUND_POLICY",
                category="COMPOUND",
                severity="HIGH",
                message="Dry race strategy policy requires using at least 2 distinct dry compounds for multi-stint races.",
                actual_value=list(unique_compounds),
                expected_value=">= 2 distinct dry compounds",
            ))

    return violations, warnings


def check_race_distance_constraints(result: SimulationResult,
                                    config: RaceConfig,
                                    constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates race distance, total laps matching, and lap counts."""
    violations: List[Violation] = []
    warnings: List[str] = []

    # 1. Total laps matching check
    if result.total_laps != config.total_laps:
        violations.append(Violation(
            constraint_id="RACE_DISTANCE_MISMATCH",
            category="DISTANCE",
            severity="CRITICAL",
            message=f"Simulation total laps ({result.total_laps}) does not match RaceConfig total laps ({config.total_laps}).",
            actual_value=result.total_laps,
            expected_value=config.total_laps,
        ))

    # 2. Lap records count check
    actual_record_count = len(result.lap_records)
    if actual_record_count != config.total_laps:
        violations.append(Violation(
            constraint_id="LAP_RECORDS_COUNT_MISMATCH",
            category="DISTANCE",
            severity="CRITICAL",
            message=f"Total lap records count ({actual_record_count}) does not match planned race distance ({config.total_laps}).",
            actual_value=actual_record_count,
            expected_value=config.total_laps,
        ))

    return violations, warnings


def check_lap_record_constraints(result: SimulationResult,
                                 config: RaceConfig,
                                 constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates individual lap records for valid numbers, positive lap times, monotonicity, and missing/duplicate laps."""
    violations: List[Violation] = []
    warnings: List[str] = []

    lap_records = result.lap_records
    laps_seen = set()
    prev_cum_time = 0.0

    for i, record in enumerate(lap_records):
        lap = record.get("race_lap", i + 1)
        lap_time = record.get("lap_time_sec", 0.0)
        pit_loss = record.get("pit_loss_sec", 0.0)
        cum_time = record.get("cumulative_race_time_sec", 0.0)

        # Duplicate lap check
        if lap in laps_seen:
            violations.append(Violation(
                constraint_id="DUPLICATE_LAP_RECORD",
                category="LAP",
                severity="CRITICAL",
                message=f"Duplicate lap record detected for lap {lap}.",
                actual_value=lap,
                expected_value="Unique lap number",
                lap_number=lap,
            ))
        laps_seen.add(lap)

        # Missing sequence check
        expected_lap = i + 1
        if lap != expected_lap:
            violations.append(Violation(
                constraint_id="MISSING_LAP_RECORD",
                category="LAP",
                severity="CRITICAL",
                message=f"Expected lap {expected_lap} at index {i}, but found lap {lap}.",
                actual_value=lap,
                expected_value=expected_lap,
                lap_number=expected_lap,
            ))

        # Lap time positivity and NaN check
        if math.isnan(lap_time) or math.isinf(lap_time):
            violations.append(Violation(
                constraint_id="NUMERICAL_ANOMALY_NAN",
                category="LAP",
                severity="CRITICAL",
                message=f"Lap time on lap {lap} contains NaN/Inf.",
                actual_value=lap_time,
                expected_value="> 0.0",
                lap_number=lap,
            ))
        elif lap_time == 0.0:
            violations.append(Violation(
                constraint_id="ZERO_LAP_TIME",
                category="LAP",
                severity="CRITICAL",
                message=f"Zero lap time recorded on lap {lap}.",
                actual_value=0.0,
                expected_value="> 0.0",
                lap_number=lap,
            ))
        elif lap_time < 0.0:
            violations.append(Violation(
                constraint_id="NEGATIVE_LAP_TIME",
                category="LAP",
                severity="CRITICAL",
                message=f"Negative lap time ({lap_time:.3f}s) recorded on lap {lap}.",
                actual_value=lap_time,
                expected_value="> 0.0",
                lap_number=lap,
            ))

        # Cumulative time monotonicity check
        if i > 0 and cum_time > 0.0 and cum_time <= prev_cum_time:
            violations.append(Violation(
                constraint_id="NON_MONOTONIC_RACE_TIME",
                category="LAP",
                severity="HIGH",
                message=f"Cumulative race time on lap {lap} ({cum_time:.3f}s) is not strictly greater than previous lap ({prev_cum_time:.3f}s).",
                actual_value=cum_time,
                expected_value=f"> {prev_cum_time:.3f}",
                lap_number=lap,
            ))
        if cum_time > 0.0:
            prev_cum_time = cum_time

    return violations, warnings


def check_simulation_consistency(result: SimulationResult,
                                 config: RaceConfig,
                                 constraints: ScenarioConstraints) -> Tuple[List[Violation], List[str]]:
    """Evaluates mathematical consistency between race metrics, lap record sums, and final states."""
    violations: List[Violation] = []
    warnings: List[str] = []

    lap_records = result.lap_records
    if not lap_records:
        return violations, warnings

    # 1. Total race time reconciliation: sum(lap_time) + sum(pit_time) == total_race_time
    sum_lap_times = sum(r.get("lap_time_sec", 0.0) for r in lap_records)
    sum_pit_times = sum(r.get("pit_loss_sec", 0.0) for r in lap_records)
    calculated_total = sum_lap_times + sum_pit_times

    # Tolerance 0.05s allows for accumulation of 50 laps of 3-decimal lap time rounding
    if not math.isclose(calculated_total, result.total_race_time_sec, abs_tol=0.05):
        violations.append(Violation(
            constraint_id="RACE_TIME_MISMATCH",
            category="CONSISTENCY",
            severity="HIGH",
            message=f"Calculated total race time ({calculated_total:.3f}s) does not match result.total_race_time_sec ({result.total_race_time_sec:.3f}s).",
            actual_value=result.total_race_time_sec,
            expected_value=round(calculated_total, 3),
        ))

    # 2. Final fuel reconciliation
    last_lap_fuel = lap_records[-1].get("fuel_remaining_kg", 0.0)
    if not math.isclose(last_lap_fuel, result.final_fuel_kg, abs_tol=1e-3):
        violations.append(Violation(
            constraint_id="FINAL_FUEL_MISMATCH",
            category="CONSISTENCY",
            severity="HIGH",
            message=f"Reported final_fuel_kg ({result.final_fuel_kg:.3f} kg) does not match final lap record fuel ({last_lap_fuel:.3f} kg).",
            actual_value=result.final_fuel_kg,
            expected_value=round(last_lap_fuel, 3),
            lap_number=lap_records[-1].get("race_lap"),
        ))

    # 3. Final tire wear reconciliation
    last_lap_record = lap_records[-1]
    for w in ["FL", "FR", "RL", "RR"]:
        reported_wear = result.final_tire_wear.get(w, 0.0)
        last_lap_wear = last_lap_record.get(f"tire_wear_{w.lower()}", 0.0)
        if not math.isclose(reported_wear, last_lap_wear, abs_tol=1e-2):
            violations.append(Violation(
                constraint_id="FINAL_TIRE_WEAR_MISMATCH",
                category="CONSISTENCY",
                severity="HIGH",
                message=f"Reported final tire wear for {w} ({reported_wear:.2f}%) does not match final lap record wear ({last_lap_wear:.2f}%).",
                actual_value=reported_wear,
                expected_value=round(last_lap_wear, 2),
                lap_number=last_lap_record.get("race_lap"),
            ))

    return violations, warnings
