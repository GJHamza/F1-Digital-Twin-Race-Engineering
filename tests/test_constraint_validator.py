# -*- coding: utf-8 -*-
"""
Unit and Integration Test Suite for Phase G.4.5.4 Constraint Validator.
Tests hard constraints, soft warnings, read-only guarantees, determinism, and G.4.5.2 -> G.4.5.3 -> G.4.5.4 pipeline.
"""

import os
import sys
import copy
import math
import pytest
from typing import List

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.strategy.race_config import RaceConfig
from ml.strategy.stint import Stint
from ml.strategy.pit_stop import PitStop
from ml.strategy.scenario_constraints import ScenarioConstraints
from ml.strategy.simulator import StrategySimulator, SimulationResult
from ml.strategy.scenario_generator import ScenarioGenerator
from ml.strategy.validation_result import Violation, ValidationResult
from ml.strategy.constraint_validator import ConstraintValidator


@pytest.fixture
def base_config():
    """Provides a standard 50-lap race configuration with sufficient fuel."""
    return RaceConfig(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        starting_fuel=110.0,
        initial_compound="SOFT",
        pit_stop_loss_sec=22.5,
        max_tire_wear=85.0,
        min_stint_laps=3,
    )


@pytest.fixture
def default_simulator(base_config):
    return StrategySimulator(config=base_config)


@pytest.fixture
def default_validator(base_config):
    return ConstraintValidator(config=base_config, constraints=ScenarioConstraints())


# 1. Valid Zero-Stop Race
def test_valid_zero_stop(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)
    val_res = default_validator.validate(res)

    assert val_res.valid is True
    assert val_res.violation_count == 0
    assert val_res.severity in ["NONE", "WARNING"]


# 2. Valid One-Stop Race
def test_valid_one_stop(base_config, default_simulator, default_validator):
    stints = [
        Stint("S1", 1, "SOFT", 1, 20, 110.0, 70.0, 0.0, 45.0),
        Stint("S2", 2, "HARD", 21, 50, 70.0, 10.0, 0.0, 30.0),
    ]
    pits = [PitStop("P1", 20, "SOFT", "HARD", 1, 2, 22.5)]
    res = default_simulator.simulate_strategy(stints, pits, base_lap_time_sec=90.0)
    val_res = default_validator.validate(res)

    assert val_res.valid is True
    assert val_res.violation_count == 0


# 3. Valid Two-Stop Race
def test_valid_two_stop(base_config, default_simulator, default_validator):
    stints = [
        Stint("S1", 1, "SOFT", 1, 15, 110.0, 80.0, 0.0, 35.0),
        Stint("S2", 2, "MEDIUM", 16, 30, 80.0, 50.0, 0.0, 25.0),
        Stint("S3", 3, "HARD", 31, 50, 50.0, 10.0, 0.0, 20.0),
    ]
    pits = [
        PitStop("P1", 15, "SOFT", "MEDIUM", 1, 2, 22.5),
        PitStop("P2", 30, "MEDIUM", "HARD", 2, 3, 22.5),
    ]
    res = default_simulator.simulate_strategy(stints, pits, base_lap_time_sec=90.0)
    val_res = default_validator.validate(res)

    assert val_res.valid is True
    assert val_res.violation_count == 0


# 4. Negative Fuel
def test_negative_fuel(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)
    
    # Mutate lap records to introduce negative fuel
    res.lap_records[30]["fuel_remaining_kg"] = -2.5
    res.final_fuel_kg = -2.5

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id in ["FUEL_DEPLETED", "FUEL_DEPLETED_ON_LAP"] for v in val_res.violations)


# 5. Tire Wear Exceeds Max
def test_tire_wear_exceeds_max(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    # Inject wear > 85%
    res.lap_records[40]["tire_wear_fl"] = 89.5
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "TIRE_WEAR_EXCEEDED_ON_LAP" for v in val_res.violations)


# 6. Tire Wear Negative
def test_tire_wear_negative(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.lap_records[10]["tire_wear_fr"] = -5.0
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "INVALID_TIRE_WEAR" for v in val_res.violations)


# 7. Negative Lap Time
def test_negative_lap_time(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.lap_records[5]["lap_time_sec"] = -90.0
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "NEGATIVE_LAP_TIME" for v in val_res.violations)


# 8. Zero Lap Time
def test_zero_lap_time(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.lap_records[5]["lap_time_sec"] = 0.0
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "ZERO_LAP_TIME" for v in val_res.violations)


# 9. NaN Lap Time
def test_nan_lap_time(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.lap_records[8]["lap_time_sec"] = float("nan")
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "NUMERICAL_ANOMALY_NAN" for v in val_res.violations)


# 10. Inf Lap Time / Wear
def test_inf_lap_time(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.lap_records[12]["tire_wear_fl"] = float("inf")
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "NUMERICAL_ANOMALY_NAN" for v in val_res.violations)


# 11. Stint Gap
def test_stint_gap(base_config, default_validator):
    # Stint 1 ends lap 20, Stint 2 starts lap 22 (gap at lap 21)
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=1,
        total_pit_time_sec=22.5,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 20, "stint_laps": 20},
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "HARD", "start_lap": 22, "end_lap": 50, "stint_laps": 29},
        ],
        pit_summary=[{"pit_stop_id": "P1", "pit_lap": 20, "compound_before": "SOFT", "compound_after": "HARD", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5}],
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "STINT_GAP" for v in val_res.violations)


# 12. Stint Overlap
def test_stint_overlap(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=1,
        total_pit_time_sec=22.5,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 25, "stint_laps": 25},
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "HARD", "start_lap": 24, "end_lap": 50, "stint_laps": 27},
        ],
        pit_summary=[{"pit_stop_id": "P1", "pit_lap": 24, "compound_before": "SOFT", "compound_after": "HARD", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5}],
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "STINT_OVERLAP" for v in val_res.violations)


# 13. Stint Below Minimum Length
def test_stint_below_minimum(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=1,
        total_pit_time_sec=22.5,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 2, "stint_laps": 2}, # 2 laps < min 3
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "HARD", "start_lap": 3, "end_lap": 50, "stint_laps": 48},
        ],
        pit_summary=[{"pit_stop_id": "P1", "pit_lap": 2, "compound_before": "SOFT", "compound_after": "HARD", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5}],
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "STINT_TOO_SHORT" for v in val_res.violations)


# 14. Invalid Pit Lap
def test_invalid_pit_lap(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=1,
        total_pit_time_sec=22.5,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 20, "stint_laps": 20},
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "HARD", "start_lap": 21, "end_lap": 50, "stint_laps": 30},
        ],
        pit_summary=[{"pit_stop_id": "P1", "pit_lap": 55, "compound_before": "SOFT", "compound_after": "HARD", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5}], # pit_lap 55 > 50
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "PIT_LAP_OUT_OF_BOUNDS" for v in val_res.violations)


# 15. Duplicate Pit Stop
def test_duplicate_pit_stop(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=2,
        total_pit_time_sec=45.0,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 20, "stint_laps": 20},
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "MEDIUM", "start_lap": 21, "end_lap": 35, "stint_laps": 15},
            {"stint_id": "STINT_03", "stint_number": 3, "compound": "HARD", "start_lap": 36, "end_lap": 50, "stint_laps": 15},
        ],
        pit_summary=[
            {"pit_stop_id": "P1", "pit_lap": 20, "compound_before": "SOFT", "compound_after": "MEDIUM", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5},
            {"pit_stop_id": "P2", "pit_lap": 20, "compound_before": "MEDIUM", "compound_after": "HARD", "stint_before": 2, "stint_after": 3, "duration_sec": 22.5}, # Duplicate pit lap 20
        ],
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "DUPLICATE_PIT_LAP" for v in val_res.violations)


# 16. Compound Mismatch
def test_compound_mismatch(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=1,
        total_pit_time_sec=22.5,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 20, "stint_laps": 20},
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "HARD", "start_lap": 21, "end_lap": 50, "stint_laps": 30},
        ],
        pit_summary=[{"pit_stop_id": "P1", "pit_lap": 20, "compound_before": "SOFT", "compound_after": "MEDIUM", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5}], # HARD vs MEDIUM
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "COMPOUND_TRANSITION_MISMATCH" for v in val_res.violations)


# 17. Wrong Pit Count
def test_wrong_pit_count(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=50,
        total_race_time_sec=4500.0,
        pit_stop_count=2, # Claimed 2 pit stops for 2 stints
        total_pit_time_sec=22.5,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[
            {"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 20, "stint_laps": 20},
            {"stint_id": "STINT_02", "stint_number": 2, "compound": "HARD", "start_lap": 21, "end_lap": 50, "stint_laps": 30},
        ],
        pit_summary=[{"pit_stop_id": "P1", "pit_lap": 20, "compound_before": "SOFT", "compound_after": "HARD", "stint_before": 1, "stint_after": 2, "duration_sec": 22.5}],
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(50)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "PIT_COUNT_MISMATCH" for v in val_res.violations)


# 18. Wrong Race Distance
def test_wrong_race_distance(base_config, default_validator):
    res = SimulationResult(
        race_id="RACE_VALIDATOR_TEST",
        total_laps=48, # 48 total laps vs 50 expected
        total_race_time_sec=4500.0,
        pit_stop_count=0,
        total_pit_time_sec=0.0,
        final_fuel_kg=10.0,
        total_fuel_consumed_kg=100.0,
        final_tire_wear={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
        stint_summary=[{"stint_id": "STINT_01", "stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 48, "stint_laps": 48}],
        pit_summary=[],
        lap_records=[{"race_lap": i+1, "lap_time_sec": 90.0, "fuel_remaining_kg": 100.0 - i*2, "tire_wear_fl": 10.0} for i in range(48)],
    )

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id in ["RACE_DISTANCE_MISMATCH", "LAP_RECORDS_COUNT_MISMATCH"] for v in val_res.violations)


# 19. Missing Lap Record
def test_missing_lap(base_config, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    sim = StrategySimulator(base_config)
    res = sim.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    # Delete lap record #15
    del res.lap_records[14]
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id in ["MISSING_LAP_RECORD", "LAP_RECORDS_COUNT_MISMATCH"] for v in val_res.violations)


# 20. Duplicate Lap Record
def test_duplicate_lap(base_config, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    sim = StrategySimulator(base_config)
    res = sim.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    # Set lap 15 race_lap to 14
    res.lap_records[14]["race_lap"] = 14
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "DUPLICATE_LAP_RECORD" for v in val_res.violations)


# 21. Invalid Weather Compound
def test_invalid_weather_compound(base_config, default_simulator):
    wet_constraints = ScenarioConstraints(weather_mode="WET")
    wet_validator = ConstraintValidator(config=base_config, constraints=wet_constraints)

    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)] # SOFT in WET weather
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)
    val_res = wet_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "WEATHER_COMPOUND_ILLEGAL" for v in val_res.violations)


# 22. Total Race Time Mismatch
def test_total_time_mismatch(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.total_race_time_sec += 100.0 # Corrupt overall total time
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "RACE_TIME_MISMATCH" for v in val_res.violations)


# 23. Final Fuel Mismatch
def test_final_fuel_mismatch(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.final_fuel_kg = 50.0 # Corrupt final fuel
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "FINAL_FUEL_MISMATCH" for v in val_res.violations)


# 24. Final Tire Wear Mismatch
def test_final_tire_mismatch(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.final_tire_wear["FL"] = 99.0 # Corrupt final tire wear dict
    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert any(v.constraint_id == "FINAL_TIRE_WEAR_MISMATCH" for v in val_res.violations)


# 25. Deterministic Replay
def test_deterministic_replay(base_config, default_simulator, default_validator):
    stints = [
        Stint("S1", 1, "SOFT", 1, 20, 110.0, 70.0, 0.0, 45.0),
        Stint("S2", 2, "HARD", 21, 50, 70.0, 10.0, 0.0, 30.0),
    ]
    pits = [PitStop("P1", 20, "SOFT", "HARD", 1, 2, 22.5)]
    res = default_simulator.simulate_strategy(stints, pits, base_lap_time_sec=90.0)

    val1 = default_validator.validate(res)
    for _ in range(4):
        val_i = default_validator.validate(res)
        assert val1 == val_i
        assert val1.to_dict() == val_i.to_dict()


# 26. Read-Only Input Verification
def test_read_only_input_verification(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res_snapshot = copy.deepcopy(res)
    val_res = default_validator.validate(res)

    assert res.total_race_time_sec == res_snapshot.total_race_time_sec
    assert res.final_fuel_kg == res_snapshot.final_fuel_kg
    assert res.final_tire_wear == res_snapshot.final_tire_wear
    assert res.lap_records == res_snapshot.lap_records


# 27. Soft Warning Does Not Invalidate
def test_soft_warning_does_not_invalidate(base_config, default_simulator, default_validator):
    # Create scenario with wear > 80% but <= 85%
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    res.lap_records[35]["tire_wear_fl"] = 82.5 # High wear soft warning
    val_res = default_validator.validate(res)

    assert val_res.valid is True
    assert val_res.violation_count == 0
    assert val_res.warning_count > 0
    assert val_res.severity == "WARNING"


# 28. Multiple Violations Deterministic Ordering
def test_multiple_violations_deterministic_ordering(base_config, default_simulator, default_validator):
    stints = [Stint("S1", 1, "SOFT", 1, 50, 110.0, 10.0, 0.0, 40.0)]
    res = default_simulator.simulate_strategy(stints, [], base_lap_time_sec=90.0)

    # Introduce multiple violations at different laps
    res.lap_records[30]["fuel_remaining_kg"] = -5.0 # Lap 31 fuel depleted
    res.lap_records[10]["tire_wear_fl"] = 95.0       # Lap 11 wear exceeded
    res.lap_records[5]["lap_time_sec"] = -10.0       # Lap 6 negative lap time

    val_res = default_validator.validate(res)

    assert val_res.valid is False
    assert val_res.violation_count >= 3

    # Check lap_number ordering of violations: Lap 6 before Lap 11 before Lap 31
    lap_nums = [v.lap_number for v in val_res.violations if v.lap_number is not None]
    assert lap_nums == sorted(lap_nums)


# 29. End-to-End Pipeline Integration: G.4.5.2 -> G.4.5.3 -> G.4.5.4
def test_g452_g453_g454_end_to_end_integration(base_config):
    generator = ScenarioGenerator(config=base_config)
    gen_result = generator.generate_scenarios()
    scenarios = gen_result.scenarios
    assert len(scenarios) > 0

    simulator = StrategySimulator(config=base_config)
    validator = ConstraintValidator(config=base_config, constraints=ScenarioConstraints())

    valid_count = 0
    invalid_count = 0

    for sc in scenarios[:10]:
        stints, pit_stops, cfg = sc.to_g451_payload(pit_stop_loss_sec=22.5, starting_fuel=110.0)
        sim_res = simulator.simulate_strategy(stints, pit_stops)
        val_res = validator.validate(sim_res, scenario_id=sc.scenario_id)

        assert isinstance(val_res, ValidationResult)
        assert val_res.scenario_id == sc.scenario_id
        if val_res.valid:
            valid_count += 1
        else:
            invalid_count += 1

    assert valid_count + invalid_count == 10
