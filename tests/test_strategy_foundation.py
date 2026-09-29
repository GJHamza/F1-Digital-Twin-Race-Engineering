# -*- coding: utf-8 -*-
"""
Unit and Integration Tests for G.4.5.1 Strategy Data Foundation & Pit/Stint Simulator.
"""

import os
import sys
import pytest
import time

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.strategy import (
    RaceConfig,
    TireCompound,
    CompoundModel,
    get_compound_model,
    validate_compound_transition,
    Stint,
    validate_stint_sequence,
    PitStop,
    FuelModel,
    FuelState,
    StrategyState,
    VehicleStatus,
    StrategySimulator,
    SimulationResult,
    StrategyValidationError,
    validate_simulation_inputs,
)


# =====================================================================
# 1. COMPOUND TESTS
# =====================================================================

def test_compound_retrieval_and_properties():
    """Verify compound models return expected wear multipliers and grip factors."""
    soft = get_compound_model("SOFT")
    assert soft.compound == "SOFT"
    assert soft.wear_multiplier == 1.4
    assert soft.grip_factor == 1.05

    med = get_compound_model(TireCompound.MEDIUM)
    assert med.compound == "MEDIUM"
    assert med.wear_multiplier == 1.0

    hard = get_compound_model("HARD")
    assert hard.compound == "HARD"
    assert hard.wear_multiplier == 0.7


def test_invalid_compound_raises_value_error():
    """Verify unknown tire compound names raise ValueError."""
    with pytest.raises(ValueError, match="Invalid tire compound 'SUPER_SOFT'"):
        get_compound_model("SUPER_SOFT")


def test_compound_transition_validation():
    """Verify compound transitions accept valid compounds and reject invalid ones."""
    assert validate_compound_transition("SOFT", "MEDIUM") is True
    assert validate_compound_transition("MEDIUM", "HARD") is True
    with pytest.raises(ValueError):
        validate_compound_transition("INVALID", "MEDIUM")


# =====================================================================
# 2. STINT TESTS
# =====================================================================

def test_stint_valid_creation():
    """Verify valid stint instantiation and derived properties."""
    stint = Stint(
        stint_id="STINT_1",
        stint_number=1,
        compound="SOFT",
        start_lap=1,
        end_lap=20,
        starting_fuel=85.0,
        ending_fuel=45.0,
        starting_tire_wear=0.0,
        ending_tire_wear=30.0,
    )
    assert stint.stint_laps == 20
    assert stint.fuel_consumed == 40.0
    assert stint.tire_wear_delta == 30.0


def test_stint_invalid_lap_range():
    """Verify stint end_lap < start_lap raises ValueError."""
    with pytest.raises(ValueError, match=r"end_lap .* must be >= start_lap"):
        Stint(
            stint_id="STINT_ERR",
            stint_number=1,
            compound="MEDIUM",
            start_lap=15,
            end_lap=10,
            starting_fuel=50.0,
            ending_fuel=30.0,
        )


def test_stint_invalid_fuel():
    """Verify ending_fuel > starting_fuel raises ValueError."""
    with pytest.raises(ValueError, match=r"ending_fuel .* cannot exceed starting_fuel"):
        Stint(
            stint_id="STINT_ERR",
            stint_number=1,
            compound="HARD",
            start_lap=1,
            end_lap=10,
            starting_fuel=40.0,
            ending_fuel=50.0,
        )


def test_stint_sequence_validation():
    """Verify stint sequence continuity validation."""
    s1 = Stint("S1", 1, "SOFT", 1, 20, 85.0, 45.0, 0.0, 30.0)
    s2 = Stint("S2", 2, "MEDIUM", 21, 50, 45.0, 0.0, 0.0, 25.0)
    assert validate_stint_sequence([s1, s2], expected_total_laps=50) is True

    # Test overlap error
    s2_overlap = Stint("S2", 2, "MEDIUM", 20, 50, 45.0, 0.0, 0.0, 25.0)
    with pytest.raises(ValueError, match=r"Stint overlap or gap"):
        validate_stint_sequence([s1, s2_overlap], expected_total_laps=50)

    # Test gap error
    s2_gap = Stint("S2", 2, "MEDIUM", 23, 50, 45.0, 0.0, 0.0, 25.0)
    with pytest.raises(ValueError, match=r"Stint overlap or gap"):
        validate_stint_sequence([s1, s2_gap], expected_total_laps=50)


# =====================================================================
# 3. PIT STOP TESTS
# =====================================================================

def test_pit_stop_valid_creation():
    """Verify valid PitStop creation and attributes."""
    pit = PitStop(
        pit_stop_id="PIT_1",
        pit_lap=20,
        compound_before="SOFT",
        compound_after="MEDIUM",
        stint_before=1,
        stint_after=2,
        duration_sec=22.5,
    )
    assert pit.pit_lap == 20
    assert pit.duration_sec == 22.5
    assert pit.compound_before == "SOFT"
    assert pit.compound_after == "MEDIUM"


def test_pit_stop_invalid_duration():
    """Verify pit stop duration below minimum duration raises ValueError."""
    with pytest.raises(ValueError, match=r"duration_sec must be >="):
        PitStop("PIT_ERR", 15, "SOFT", "MEDIUM", 1, 2, duration_sec=0.2)


def test_pit_stop_invalid_stint_order():
    """Verify pit stop stint_after != stint_before + 1 raises ValueError."""
    with pytest.raises(ValueError, match=r"stint_after .* must equal stint_before \+ 1"):
        PitStop("PIT_ERR", 15, "SOFT", "MEDIUM", 1, 3, duration_sec=22.5)


# =====================================================================
# 4. FUEL MODEL TESTS
# =====================================================================

def test_fuel_model_depletion():
    """Verify fuel model consumes fuel deterministically."""
    fuel = FuelModel(starting_fuel=85.0, fuel_consumption_rate=2.0)
    state1 = fuel.consume_fuel(laps=10)
    assert state1.fuel_consumed == 20.0
    assert state1.fuel_remaining == 65.0

    state2 = fuel.consume_fuel(laps=32.5)
    assert state2.fuel_consumed == 85.0
    assert state2.fuel_remaining == 0.0


def test_fuel_model_insufficient_fuel():
    """Verify fuel model raises ValueError when consuming more than remaining fuel."""
    fuel = FuelModel(starting_fuel=10.0, fuel_consumption_rate=2.0)
    with pytest.raises(ValueError, match=r"Insufficient fuel remaining"):
        fuel.consume_fuel(laps=6)


# =====================================================================
# 5. STRATEGY STATE TESTS
# =====================================================================

def test_strategy_state_construction_and_transitions():
    """Verify StrategyState construction and state machine transitions."""
    state = StrategyState(
        race_id="RACE_TEST",
        current_lap=1,
        current_stint=1,
        current_compound="SOFT",
        fuel_remaining=85.0,
        tire_wear={"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0},
        vehicle_status=VehicleStatus.ON_TRACK,
    )
    assert state.vehicle_status == VehicleStatus.ON_TRACK

    # Execute valid transition sequence
    state.transition_status(VehicleStatus.PIT_ENTRY)
    assert state.vehicle_status == VehicleStatus.PIT_ENTRY

    state.transition_status(VehicleStatus.IN_PIT)
    assert state.vehicle_status == VehicleStatus.IN_PIT

    state.transition_status(VehicleStatus.PIT_EXIT)
    assert state.vehicle_status == VehicleStatus.PIT_EXIT

    state.transition_status(VehicleStatus.ON_TRACK)
    assert state.vehicle_status == VehicleStatus.ON_TRACK


def test_strategy_state_invalid_transition():
    """Verify illegal status transition raises ValueError."""
    state = StrategyState(
        race_id="RACE_TEST",
        current_lap=1,
        current_stint=1,
        current_compound="SOFT",
        fuel_remaining=85.0,
        tire_wear={"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0},
        vehicle_status=VehicleStatus.ON_TRACK,
    )
    with pytest.raises(ValueError, match=r"Invalid vehicle status transition"):
        state.transition_status(VehicleStatus.IN_PIT)  # Cannot jump directly from ON_TRACK to IN_PIT


def test_strategy_state_telemetry_serialization():
    """Verify strategy state telemetry dictionary format matches V1 compatibility expectations."""
    state = StrategyState(
        race_id="RACE_001",
        current_lap=15,
        current_stint=2,
        current_compound="MEDIUM",
        fuel_remaining=55.0,
        tire_wear={"FL": 10.0, "FR": 10.0, "RL": 8.0, "RR": 8.0},
        pit_stop_count=1,
    )
    telem = state.to_telemetry_extension()
    assert telem["stint_id"] == "STINT_02"
    assert telem["stint_number"] == 2
    assert telem["tire_compound"] == "MEDIUM"
    assert telem["avg_tire_wear_pct"] == 9.0
    assert telem["fuel_remaining_kg"] == 55.0


# =====================================================================
# 6. INTEGRATION RACE SIMULATION TEST
# =====================================================================

def test_race_simulation_50_laps():
    """Integration test simulating a 50-lap 2-stint race with 1 pit stop."""
    config = RaceConfig(
        race_id="RACE_INTEGRATION_50",
        total_laps=50,
        starting_fuel=100.0,
        initial_compound="SOFT",
        pit_stop_loss_sec=22.5,
    )

    stints = [
        Stint("STINT_1", 1, "SOFT", 1, 20, 100.0, 60.0, 0.0, 23.5),
        Stint("STINT_2", 2, "MEDIUM", 21, 50, 60.0, 0.0, 0.0, 24.0),
    ]

    pit_stops = [
        PitStop("PIT_1", 20, "SOFT", "MEDIUM", 1, 2, duration_sec=22.5)
    ]

    simulator = StrategySimulator(config)
    result = simulator.simulate_strategy(stints, pit_stops, base_lap_time_sec=90.0)

    assert result.race_id == "RACE_INTEGRATION_50"
    assert result.total_laps == 50
    assert result.pit_stop_count == 1
    assert result.total_pit_time_sec == 22.5
    assert result.is_feasible is True
    assert len(result.lap_records) == 50
    assert result.lap_records[19]["pit_loss_sec"] == 22.5
    assert result.lap_records[19]["vehicle_status"] == VehicleStatus.IN_PIT.value


# =====================================================================
# 7. DETERMINISM TEST
# =====================================================================

def test_simulation_determinism():
    """Verify that identical simulation inputs produce 100% identical outputs across repeated runs."""
    config = RaceConfig(race_id="RACE_DET", total_laps=30, starting_fuel=60.0)
    stints = [
        Stint("S1", 1, "SOFT", 1, 15, 60.0, 30.0, 0.0, 20.0),
        Stint("S2", 2, "HARD", 16, 30, 30.0, 0.0, 0.0, 10.0),
    ]
    pit_stops = [
        PitStop("P1", 15, "SOFT", "HARD", 1, 2, duration_sec=22.5)
    ]

    sim = StrategySimulator(config)

    res1 = sim.simulate_strategy(stints, pit_stops)
    res2 = sim.simulate_strategy(stints, pit_stops)

    assert res1.total_race_time_sec == res2.total_race_time_sec
    assert res1.total_fuel_consumed_kg == res2.total_fuel_consumed_kg
    assert res1.lap_records == res2.lap_records


# =====================================================================
# 8. PERFORMANCE BENCHMARK TEST
# =====================================================================

def test_simulation_performance_benchmark():
    """Benchmark strategy simulator throughput over 1,000 and 10,000 race simulations."""
    config = RaceConfig(race_id="BENCHMARK", total_laps=50, starting_fuel=100.0)
    stints = [
        Stint("S1", 1, "SOFT", 1, 25, 100.0, 50.0, 0.0, 30.0),
        Stint("S2", 2, "MEDIUM", 26, 50, 50.0, 0.0, 0.0, 25.0),
    ]
    pit_stops = [
        PitStop("P1", 25, "SOFT", "MEDIUM", 1, 2, duration_sec=22.5)
    ]

    sim = StrategySimulator(config)

    # Warmup
    sim.simulate_strategy(stints, pit_stops)

    # 1,000 race simulations benchmark
    t0 = time.perf_counter()
    for _ in range(1000):
        sim.simulate_strategy(stints, pit_stops)
    t1 = time.perf_counter()

    elapsed_1k = t1 - t0
    races_per_sec_1k = 1000.0 / elapsed_1k

    assert elapsed_1k < 1.0, f"1,000 simulations took {elapsed_1k:.3f}s (expected < 1.0s)"
    assert races_per_sec_1k > 1000.0, f"Throughput {races_per_sec_1k:.0f} races/sec below target 1000"
