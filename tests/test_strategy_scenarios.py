# -*- coding: utf-8 -*-
"""
Unit, Integration, Determinism, and Performance Tests for G.4.5.2 Strategy Scenario Builder.
"""

import os
import sys
import pytest
import time
import json
import tempfile

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from ml.strategy import (
    RaceConfig,
    Stint,
    PitStop,
    TireCompound,
    StrategySimulator,
    generate_canonical_key,
    generate_deterministic_scenario_id,
    Scenario,
    ScenarioDeduplicator,
    ScenarioConstraints,
    validate_scenario_hard_constraints,
    ScenarioGenerator,
    ScenarioGenerationLimitError,
    GenerationResult,
    determine_bounded_grid_step,
    ScenarioSerializer,
)


# =====================================================================
# 1. CANONICAL KEY & DETERMINISTIC SCENARIO ID TESTS
# =====================================================================

def test_canonical_key_formatting():
    """Verify canonical key format matches COMPOUND_1:START_1-END_1|COMPOUND_2:START_2-END_2."""
    stint1 = Stint("S1", 1, "SOFT", 1, 20, 85.0, 45.0, 0.0, 25.0)
    stint2 = Stint("S2", 2, "MEDIUM", 21, 50, 45.0, 0.0, 0.0, 20.0)
    key = generate_canonical_key([stint1, stint2])
    assert key == "SOFT:1-20|MEDIUM:21-50"


def test_deterministic_scenario_ids():
    """Verify deterministic scenario IDs start with SCN_ and produce identical hashes for identical inputs."""
    key = "SOFT:1-20|MEDIUM:21-50"
    id1 = generate_deterministic_scenario_id("RACE_MONZA_50", key)
    id2 = generate_deterministic_scenario_id("RACE_MONZA_50", key)
    id3 = generate_deterministic_scenario_id("RACE_SPA_50", key)

    assert id1.startswith("SCN_")
    assert len(id1) == 16  # SCN_ + 12 hex chars
    assert id1 == id2
    assert id1 != id3


# =====================================================================
# 2. DEDUPLICATION TESTS
# =====================================================================

def test_deduplication_using_canonical_key():
    """Verify deduplicator removes identical canonical scenarios."""
    dedup = ScenarioDeduplicator()

    stint1 = Stint("S1", 1, "SOFT", 1, 20, 85.0, 45.0, 0.0, 25.0)
    stint2 = Stint("S2", 2, "MEDIUM", 21, 50, 45.0, 0.0, 0.0, 20.0)
    pit1 = PitStop("P1", 20, "SOFT", "MEDIUM", 1, 2)

    s1 = Scenario("SCN_1", "RACE_1", 50, "SOFT", ["SOFT", "MEDIUM"], [stint1, stint2], [pit1], 1, 2)
    s2 = Scenario("SCN_1", "RACE_1", 50, "SOFT", ["SOFT", "MEDIUM"], [stint1, stint2], [pit1], 1, 2)

    assert dedup.process_scenario(s1) is True
    assert dedup.process_scenario(s2) is False

    metrics = dedup.get_metrics()
    assert metrics["generated_before_deduplication"] == 2
    assert metrics["duplicates_removed"] == 1
    assert metrics["final_unique_scenarios"] == 1


# =====================================================================
# 3. SCENARIO GENERATION TYPOLOGY TESTS
# =====================================================================

def test_zero_stop_scenario_generation():
    """Verify 0-stop single-stint scenario generation."""
    config = RaceConfig("RACE_20", total_laps=20, starting_fuel=40.0)
    constraints = ScenarioConstraints(max_stops=0, weather_mode="DRY", require_distinct_dry_compounds=False)

    generator = ScenarioGenerator(config, constraints)
    result = generator.generate_scenarios()

    assert result.final_scenario_count == 3  # SOFT, MEDIUM, HARD 0-stop
    for s in result.scenarios:
        assert s.number_of_stops == 0
        assert s.number_of_stints == 1
        assert len(s.stints) == 1
        assert s.stints[0].start_lap == 1
        assert s.stints[0].end_lap == 20


def test_one_stop_scenario_generation():
    """Verify 1-stop 2-stint candidate scenario generation."""
    config = RaceConfig("RACE_30", total_laps=30, starting_fuel=60.0)
    constraints = ScenarioConstraints(max_stops=1, min_stint_laps=5, weather_mode="DRY", require_distinct_dry_compounds=False)

    generator = ScenarioGenerator(config, constraints)
    result = generator.generate_scenarios()

    assert result.final_scenario_count > 0
    for s in result.scenarios:
        if s.number_of_stops == 1:
            assert len(s.stints) == 2
            assert len(s.pit_stops) == 1
            assert s.stints[0].start_lap == 1
            assert s.stints[1].end_lap == 30


def test_two_stop_scenario_generation():
    """Verify 2-stop 3-stint candidate scenario generation."""
    config = RaceConfig("RACE_40", total_laps=40, starting_fuel=80.0)
    constraints = ScenarioConstraints(max_stops=2, min_stint_laps=5, weather_mode="DRY", require_distinct_dry_compounds=True)

    generator = ScenarioGenerator(config, constraints)
    result = generator.generate_scenarios()

    two_stop_scenarios = [s for s in result.scenarios if s.number_of_stops == 2]
    assert len(two_stop_scenarios) > 0
    for s in two_stop_scenarios:
        assert len(s.stints) == 3
        assert len(s.pit_stops) == 2
        assert len(set(s.compound_sequence)) >= 2  # Enforces distinct dry compound policy


def test_same_compound_scenario():
    """Verify same-compound strategy generation (e.g. MEDIUM -> MEDIUM)."""
    config = RaceConfig("RACE_30", total_laps=30, starting_fuel=60.0)
    constraints = ScenarioConstraints(max_stops=1, weather_mode="DRY", require_distinct_dry_compounds=False)

    generator = ScenarioGenerator(config, constraints)
    result = generator.generate_scenarios()

    same_comp_scenarios = [s for s in result.scenarios if s.number_of_stops == 1 and s.compound_sequence[0] == s.compound_sequence[1]]
    assert len(same_comp_scenarios) > 0


# =====================================================================
# 4. HARD CONSTRAINTS & VALIDATION TESTS
# =====================================================================

def test_minimum_stint_length_constraint():
    """Verify candidate scenarios with stint length < min_stint_laps are rejected."""
    config = RaceConfig("RACE_50", total_laps=50)
    constraints = ScenarioConstraints(min_stint_laps=10)

    stint1 = Stint("S1", 1, "SOFT", 1, 5, 100.0, 90.0)  # Length 5 < min_stint 10
    stint2 = Stint("S2", 2, "MEDIUM", 6, 50, 90.0, 0.0)
    pit1 = PitStop("P1", 5, "SOFT", "MEDIUM", 1, 2)

    scenario = Scenario("SCN_TEST", "RACE_50", 50, "SOFT", ["SOFT", "MEDIUM"], [stint1, stint2], [pit1], 1, 2)
    is_valid, errors = validate_scenario_hard_constraints(scenario, constraints)

    assert is_valid is False
    assert any("below min_stint_laps" in err for err in errors)


def test_invalid_pit_lap_rejection():
    """Verify pit stop on illegal lap (outside stint bounds) fails validation."""
    config = RaceConfig("RACE_50", total_laps=50)
    constraints = ScenarioConstraints()

    stint1 = Stint("S1", 1, "SOFT", 1, 20, 100.0, 60.0)
    stint2 = Stint("S2", 2, "MEDIUM", 21, 50, 60.0, 0.0)
    pit1 = PitStop("P1", 25, "SOFT", "MEDIUM", 1, 2)  # Mismatched pit lap 25 != stint end lap 20

    scenario = Scenario("SCN_TEST", "RACE_50", 50, "SOFT", ["SOFT", "MEDIUM"], [stint1, stint2], [pit1], 1, 2)
    is_valid, errors = validate_scenario_hard_constraints(scenario, constraints)

    assert is_valid is False


def test_invalid_compound_rejection():
    """Verify unknown compound string raises error."""
    with pytest.raises(ValueError):
        Stint("S1", 1, "ULTRA_SOFT", 1, 20, 85.0, 45.0)


def test_invalid_transition_rejection():
    """Verify invalid compound transition in pit stop raises error."""
    with pytest.raises(ValueError):
        PitStop("P1", 20, "INVALID_COMPOUND", "MEDIUM", 1, 2)


def test_weather_mode_compound_filtering():
    """Verify slick compounds rejected in WET weather mode and rain compounds rejected in DRY mode."""
    config = RaceConfig("RACE_WET", total_laps=30)
    constraints_wet = ScenarioConstraints(weather_mode="WET", require_distinct_dry_compounds=False)

    stint1 = Stint("S1", 1, "SOFT", 1, 30, 60.0, 0.0)  # SOFT is illegal in WET mode
    scenario_dry_tire = Scenario("SCN_TEST", "RACE_WET", 30, "SOFT", ["SOFT"], [stint1], [], 0, 1)

    is_valid, errors = validate_scenario_hard_constraints(scenario_dry_tire, constraints_wet)
    assert is_valid is False
    assert any("not allowed in WET weather mode" in err for err in errors)


def test_dry_compound_rule_enforcement():
    """Verify require_distinct_dry_compounds rejects single-compound multi-stint dry strategies."""
    config = RaceConfig("RACE_DRY", total_laps=50)
    constraints = ScenarioConstraints(weather_mode="DRY", require_distinct_dry_compounds=True)

    stint1 = Stint("S1", 1, "MEDIUM", 1, 25, 100.0, 50.0)
    stint2 = Stint("S2", 2, "MEDIUM", 26, 50, 50.0, 0.0)
    pit1 = PitStop("P1", 25, "MEDIUM", "MEDIUM", 1, 2)

    scenario_single_dry = Scenario("SCN_TEST", "RACE_DRY", 50, "MEDIUM", ["MEDIUM", "MEDIUM"], [stint1, stint2], [pit1], 1, 2)
    is_valid, errors = validate_scenario_hard_constraints(scenario_single_dry, constraints)

    assert is_valid is False
    assert any("at least 2 distinct dry compounds" in err for err in errors)


# =====================================================================
# 5. DETERMINISM & BOUNDS TESTS
# =====================================================================

def test_deterministic_scenario_generation():
    """Verify that generating scenarios for identical RaceConfig twice produces 100% identical outputs."""
    config = RaceConfig("RACE_DET_50", total_laps=50, starting_fuel=100.0)
    constraints = ScenarioConstraints(max_stops=2, min_stint_laps=5)

    gen1 = ScenarioGenerator(config, constraints)
    res1 = gen1.generate_scenarios()

    gen2 = ScenarioGenerator(config, constraints)
    res2 = gen2.generate_scenarios()

    assert res1.final_scenario_count == res2.final_scenario_count
    assert [s.scenario_id for s in res1.scenarios] == [s.scenario_id for s in res2.scenarios]
    assert [s.canonical_key for s in res1.scenarios] == [s.canonical_key for s in res2.scenarios]


def test_max_stop_limit_constraint():
    """Verify max_stops limits generated scenario stop counts."""
    config = RaceConfig("RACE_50", total_laps=50)
    constraints = ScenarioConstraints(max_stops=1)

    generator = ScenarioGenerator(config, constraints)
    result = generator.generate_scenarios()

    for s in result.scenarios:
        assert s.number_of_stops <= 1


def test_max_candidates_limit_ceiling():
    """Verify ScenarioGenerationLimitError is raised when max_candidates is exceeded."""
    config = RaceConfig("RACE_50", total_laps=50)
    constraints = ScenarioConstraints(max_candidates=5)  # Set artificially low limit

    generator = ScenarioGenerator(config, constraints)
    with pytest.raises(ScenarioGenerationLimitError, match="max_candidates limit"):
        generator.generate_scenarios()


def test_stint_timeline_continuity():
    """Verify no gaps or overlaps exist in generated stint sequences."""
    config = RaceConfig("RACE_50", total_laps=50)
    generator = ScenarioGenerator(config)
    result = generator.generate_scenarios()

    for scenario in result.scenarios:
        prev_end = 0
        for stint in scenario.stints:
            assert stint.start_lap == prev_end + 1
            prev_end = stint.end_lap


def test_final_lap_race_coverage():
    """Verify last stint of every generated scenario ends on total_laps."""
    config = RaceConfig("RACE_50", total_laps=50)
    generator = ScenarioGenerator(config)
    result = generator.generate_scenarios()

    for scenario in result.scenarios:
        assert scenario.stints[-1].end_lap == 50


# =====================================================================
# 6. MULTI-RACE DISTANCE TESTS & BENCHMARK
# =====================================================================

def test_20_lap_race_scenario_generation():
    """End-to-end test generating scenarios for 20-lap race."""
    config = RaceConfig("RACE_20", total_laps=20)
    result = ScenarioGenerator(config).generate_scenarios()
    assert result.final_scenario_count > 0


def test_50_lap_race_scenario_generation():
    """End-to-end test generating scenarios for 50-lap race."""
    config = RaceConfig("RACE_50", total_laps=50)
    result = ScenarioGenerator(config).generate_scenarios()
    assert result.final_scenario_count > 0


def test_100_lap_race_scenario_generation():
    """End-to-end test generating scenarios for 100-lap race."""
    config = RaceConfig("RACE_100", total_laps=100)
    result = ScenarioGenerator(config).generate_scenarios()
    assert result.final_scenario_count > 0


def test_300_lap_race_scenario_generation_benchmark():
    """Benchmark candidate scenario generation for 300-lap race with bounded grid step."""
    config = RaceConfig("BENCHMARK_300", total_laps=300)
    constraints = ScenarioConstraints(max_stops=2, min_stint_laps=10)

    t0 = time.perf_counter()
    result = ScenarioGenerator(config, constraints).generate_scenarios()
    t1 = time.perf_counter()

    duration = t1 - t0
    assert duration < 2.0, f"300-lap generation took {duration:.3f}s (expected < 2.0s)"
    assert result.final_scenario_count > 0


# =====================================================================
# 7. SERIALIZATION & G.4.5.1 INTEGRATION TESTS
# =====================================================================

def test_json_serialization_and_deserialization():
    """Verify JSON export and import parity."""
    config = RaceConfig("RACE_JSON_50", total_laps=50)
    result = ScenarioGenerator(config).generate_scenarios()

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "test_scenarios.json")
        ScenarioSerializer.save_json(result.scenarios, json_path)

        loaded_scenarios = ScenarioSerializer.load_json(json_path)
        assert len(loaded_scenarios) == len(result.scenarios)
        assert loaded_scenarios[0].scenario_id == result.scenarios[0].scenario_id
        assert loaded_scenarios[0].canonical_key == result.scenarios[0].canonical_key


def test_parquet_serialization_and_dataframe_conversion():
    """Verify Parquet export and DataFrame conversion."""
    config = RaceConfig("RACE_PQ_50", total_laps=50)
    result = ScenarioGenerator(config).generate_scenarios()

    df = ScenarioSerializer.to_dataframe(result.scenarios)
    assert len(df) == len(result.scenarios)
    assert "scenario_id" in df.columns
    assert "canonical_key" in df.columns

    with tempfile.TemporaryDirectory() as tmpdir:
        pq_path = os.path.join(tmpdir, "test_scenarios.parquet")
        ScenarioSerializer.save_parquet(result.scenarios, pq_path)
        assert os.path.exists(pq_path)


def test_g451_simulator_end_to_end_integration():
    """Verify passing generated Scenario directly into G.4.5.1 StrategySimulator."""
    config = RaceConfig("RACE_INTEG_50", total_laps=50, starting_fuel=100.0)
    gen_result = ScenarioGenerator(config).generate_scenarios()

    scenario = gen_result.scenarios[0]
    stints, pit_stops, sim_config = scenario.to_g451_payload()

    simulator = StrategySimulator(sim_config)
    sim_result = simulator.simulate_strategy(stints, pit_stops)

    assert sim_result.total_laps == 50
    assert sim_result.is_feasible is True
    assert len(sim_result.lap_records) == 50
