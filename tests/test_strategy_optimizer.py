# -*- coding: utf-8 -*-
"""
Comprehensive Unit & Integration Test Suite for G.4.5.5 Strategy Optimizer.
Covers all 31 mandatory test categories including tie-breakers, determinism, Top-K, immutability, and end-to-end integration.
"""

import copy
import math
import pytest
from typing import List

from ml.strategy import (
    OptimizationConfig,
    OptimizationCandidate,
    RankedStrategy,
    RankingResult,
    StrategyOptimizer,
    DEFAULT_RANKING_EXPLANATION,
    ScenarioGenerator,
    ScenarioConstraints,
    StrategySimulator,
    ConstraintValidator,
    RaceConfig,
    SimulationResult,
    ValidationResult,
    Violation,
)


def create_sample_candidate(
    scenario_id: str,
    valid: bool = True,
    race_time: float = 5400.0,
    pit_stops: int = 1,
    fuel_kg: float = 5.0,
    tire_wear: float = 40.0,
    canonical_key: str = "SOFT:1-25|MEDIUM:26-50",
    warnings: int = 0,
) -> OptimizationCandidate:
    """Helper factory for creating mock OptimizationCandidate instances."""
    return OptimizationCandidate(
        scenario_id=scenario_id,
        canonical_key=canonical_key,
        valid=valid,
        warning_count=warnings,
        total_race_time_sec=race_time,
        pit_stop_count=pit_stops,
        final_fuel_kg=fuel_kg,
        avg_final_tire_wear_pct=tire_wear,
    )


# 1. Empty Input
def test_empty_input():
    optimizer = StrategyOptimizer()
    result = optimizer.optimize([])
    assert result.total_candidates == 0
    assert result.valid_candidates == 0
    assert result.excluded_candidates == 0
    assert result.is_empty
    assert len(result.ranked_strategies) == 0
    assert result.leader_scenario_id is None
    assert result.leader_race_time_sec is None


# 2. One Valid Candidate
def test_one_valid_candidate():
    optimizer = StrategyOptimizer()
    cand = create_sample_candidate("SCN_001", valid=True, race_time=5000.0)
    result = optimizer.optimize([cand])
    assert result.total_candidates == 1
    assert result.valid_candidates == 1
    assert result.excluded_candidates == 0
    assert len(result.ranked_strategies) == 1
    strat = result.ranked_strategies[0]
    assert strat.rank == 1
    assert strat.scenario_id == "SCN_001"
    assert strat.delta_to_leader_sec == 0.0


# 3. All Valid Candidates
def test_all_valid_candidates():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_001", race_time=5000.0),
        create_sample_candidate("SCN_002", race_time=4900.0),
        create_sample_candidate("SCN_003", race_time=5100.0),
    ]
    result = optimizer.optimize(cands)
    assert result.total_candidates == 3
    assert result.valid_candidates == 3
    assert result.excluded_candidates == 0
    assert len(result.ranked_strategies) == 3
    assert result.ranked_strategies[0].scenario_id == "SCN_002"
    assert result.ranked_strategies[1].scenario_id == "SCN_001"
    assert result.ranked_strategies[2].scenario_id == "SCN_003"


# 4. All Invalid Candidates
def test_all_invalid_candidates():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_001", valid=False),
        create_sample_candidate("SCN_002", valid=False),
    ]
    result = optimizer.optimize(cands)
    assert result.total_candidates == 2
    assert result.valid_candidates == 0
    assert result.excluded_candidates == 2
    assert result.is_empty
    assert len(result.ranked_strategies) == 0


# 5. Mixed Valid/Invalid Candidates
def test_mixed_valid_invalid():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_001", valid=False, race_time=4800.0),
        create_sample_candidate("SCN_002", valid=True, race_time=5000.0),
        create_sample_candidate("SCN_003", valid=True, race_time=4900.0),
    ]
    result = optimizer.optimize(cands)
    assert result.total_candidates == 3
    assert result.valid_candidates == 2
    assert result.excluded_candidates == 1
    assert [s.scenario_id for s in result.ranked_strategies] == ["SCN_003", "SCN_002"]


# 6. Warning Candidate Remains Ranked
def test_warning_candidate_remains_ranked():
    optimizer = StrategyOptimizer()
    cand1 = create_sample_candidate("SCN_001", valid=True, warnings=2, race_time=4900.0)
    cand2 = create_sample_candidate("SCN_002", valid=True, warnings=0, race_time=5000.0)
    result = optimizer.optimize([cand1, cand2])
    assert result.valid_candidates == 2
    assert result.ranked_strategies[0].scenario_id == "SCN_001"
    assert result.ranked_strategies[0].warning_count == 2


# 7. Race-Time Ordering
def test_race_time_ordering():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_003", race_time=5050.0),
        create_sample_candidate("SCN_001", race_time=4950.0),
        create_sample_candidate("SCN_002", race_time=5000.0),
    ]
    result = optimizer.optimize(cands)
    times = [s.total_race_time_sec for s in result.ranked_strategies]
    assert times == [4950.0, 5000.0, 5050.0]


# 8. Pit-Stop Tie-Break
def test_pit_stop_tie_break():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_2STOPS", race_time=5000.0, pit_stops=2),
        create_sample_candidate("SCN_1STOP", race_time=5000.0, pit_stops=1),
    ]
    result = optimizer.optimize(cands)
    assert result.ranked_strategies[0].scenario_id == "SCN_1STOP"
    assert result.ranked_strategies[1].scenario_id == "SCN_2STOPS"


# 9. Final-Fuel Tie-Break
def test_final_fuel_tie_break():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_LOW_FUEL", race_time=5000.0, pit_stops=1, fuel_kg=2.0),
        create_sample_candidate("SCN_HIGH_FUEL", race_time=5000.0, pit_stops=1, fuel_kg=8.0),
    ]
    result = optimizer.optimize(cands)
    assert result.ranked_strategies[0].scenario_id == "SCN_HIGH_FUEL"
    assert result.ranked_strategies[1].scenario_id == "SCN_LOW_FUEL"


# 10. Tire-Wear Tie-Break
def test_tire_wear_tie_break():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_HIGH_WEAR", race_time=5000.0, pit_stops=1, fuel_kg=5.0, tire_wear=65.0),
        create_sample_candidate("SCN_LOW_WEAR", race_time=5000.0, pit_stops=1, fuel_kg=5.0, tire_wear=35.0),
    ]
    result = optimizer.optimize(cands)
    assert result.ranked_strategies[0].scenario_id == "SCN_LOW_WEAR"
    assert result.ranked_strategies[1].scenario_id == "SCN_HIGH_WEAR"


# 11. Canonical-Key Tie-Break
def test_canonical_key_tie_break():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_B", race_time=5000.0, pit_stops=1, fuel_kg=5.0, tire_wear=40.0, canonical_key="MEDIUM:1-25|HARD:26-50"),
        create_sample_candidate("SCN_A", race_time=5000.0, pit_stops=1, fuel_kg=5.0, tire_wear=40.0, canonical_key="HARD:1-25|MEDIUM:26-50"),
    ]
    result = optimizer.optimize(cands)
    assert result.ranked_strategies[0].canonical_key == "HARD:1-25|MEDIUM:26-50"
    assert result.ranked_strategies[1].canonical_key == "MEDIUM:1-25|HARD:26-50"


# 12. Scenario-ID Final Tie-Break
def test_scenario_id_final_tie_break():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_Z", race_time=5000.0, pit_stops=1, fuel_kg=5.0, tire_wear=40.0, canonical_key="KEY1"),
        create_sample_candidate("SCN_A", race_time=5000.0, pit_stops=1, fuel_kg=5.0, tire_wear=40.0, canonical_key="KEY1"),
    ]
    result = optimizer.optimize(cands)
    assert result.ranked_strategies[0].scenario_id == "SCN_A"
    assert result.ranked_strategies[1].scenario_id == "SCN_Z"


# 13. Deterministic Ranking
def test_deterministic_ranking():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_003", race_time=5000.0, pit_stops=2),
        create_sample_candidate("SCN_001", race_time=4900.0, pit_stops=1),
        create_sample_candidate("SCN_002", race_time=5000.0, pit_stops=1),
    ]
    res1 = optimizer.optimize(cands)
    res2 = optimizer.optimize(cands)
    assert [s.to_dict() for s in res1.ranked_strategies] == [s.to_dict() for s in res2.ranked_strategies]


# 14. Repeated Ranking (5x execution equality)
def test_repeated_ranking():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate(f"SCN_{i:03d}", race_time=5000.0 + (i % 7) * 10.0, pit_stops=i % 3)
        for i in range(20)
    ]
    results = [optimizer.optimize(cands) for _ in range(5)]
    first_dict = results[0].to_dict()
    for i in range(1, 5):
        assert results[i].to_dict() == first_dict


# 15. Top-K = 1
def test_top_k_1():
    config = OptimizationConfig(top_k=1)
    optimizer = StrategyOptimizer(config)
    cands = [
        create_sample_candidate("SCN_001", race_time=5000.0),
        create_sample_candidate("SCN_002", race_time=4900.0),
        create_sample_candidate("SCN_003", race_time=5100.0),
    ]
    result = optimizer.optimize(cands)
    assert len(result.ranked_strategies) == 1
    assert result.ranked_strategies[0].scenario_id == "SCN_002"


# 16. Top-K = 5
def test_top_k_5():
    config = OptimizationConfig(top_k=5)
    optimizer = StrategyOptimizer(config)
    cands = [create_sample_candidate(f"SCN_{i:03d}", race_time=5000.0 + i * 10) for i in range(10)]
    result = optimizer.optimize(cands)
    assert len(result.ranked_strategies) == 5
    assert [s.rank for s in result.ranked_strategies] == [1, 2, 3, 4, 5]


# 17. Top-K = 10
def test_top_k_10():
    config = OptimizationConfig(top_k=10)
    optimizer = StrategyOptimizer(config)
    cands = [create_sample_candidate(f"SCN_{i:03d}", race_time=5000.0 + i * 10) for i in range(15)]
    result = optimizer.optimize(cands)
    assert len(result.ranked_strategies) == 10


# 18. K > Candidate Count
def test_k_greater_than_candidate_count():
    config = OptimizationConfig(top_k=10)
    optimizer = StrategyOptimizer(config)
    cands = [
        create_sample_candidate("SCN_001", race_time=5000.0),
        create_sample_candidate("SCN_002", race_time=4900.0),
    ]
    result = optimizer.optimize(cands)
    assert len(result.ranked_strategies) == 2
    assert result.valid_candidates == 2


# 19. K <= 0 Validation
def test_k_less_equal_zero():
    with pytest.raises(ValueError, match="top_k must be > 0"):
        OptimizationConfig(top_k=0)
    with pytest.raises(ValueError, match="top_k must be > 0"):
        OptimizationConfig(top_k=-5)

    optimizer = StrategyOptimizer()
    with pytest.raises(ValueError, match="top_k must be an integer > 0"):
        optimizer.optimize([create_sample_candidate("SCN_001")], override_top_k=0)


# 20. Duplicate Scenario ID
def test_duplicate_scenario_id():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_DUP", race_time=5000.0),
        create_sample_candidate("SCN_DUP", race_time=4900.0),
    ]
    with pytest.raises(ValueError, match="Duplicate scenario_id detected"):
        optimizer.optimize(cands)


# 21. NaN Race Time
def test_nan_race_time():
    with pytest.raises(ValueError, match="Invalid numeric value for total_race_time_sec"):
        create_sample_candidate("SCN_NAN", race_time=float("nan"))


# 22. Inf Race Time
def test_inf_race_time():
    with pytest.raises(ValueError, match="Invalid numeric value for total_race_time_sec"):
        create_sample_candidate("SCN_INF", race_time=float("inf"))


# 23. Negative Race Time
def test_negative_race_time():
    with pytest.raises(ValueError, match="total_race_time_sec cannot be negative"):
        create_sample_candidate("SCN_NEG", race_time=-100.0)


# 24. Immutable Input Verification
def test_immutable_input():
    optimizer = StrategyOptimizer()
    cand1 = create_sample_candidate("SCN_001", race_time=5000.0)
    cand2 = create_sample_candidate("SCN_002", race_time=4900.0)
    input_list = [cand1, cand2]
    original_list_copy = list(input_list)
    cand1_copy = copy.deepcopy(cand1)
    cand2_copy = copy.deepcopy(cand2)

    optimizer.optimize(input_list)

    assert input_list == original_list_copy
    assert cand1 == cand1_copy
    assert cand2 == cand2_copy


# 25. Delta-to-Leader Calculation
def test_delta_to_leader_calculation():
    optimizer = StrategyOptimizer()
    cands = [
        create_sample_candidate("SCN_LEADER", race_time=5000.0),
        create_sample_candidate("SCN_SECOND", race_time=5012.345),
        create_sample_candidate("SCN_THIRD", race_time=5045.600),
    ]
    result = optimizer.optimize(cands)
    strats = result.ranked_strategies
    assert strats[0].delta_to_leader_sec == 0.0
    assert pytest.approx(strats[1].delta_to_leader_sec, abs=1e-5) == 12.345
    assert pytest.approx(strats[2].delta_to_leader_sec, abs=1e-5) == 45.600


# 26. Ranking Explanation Determinism
def test_ranking_explanation_determinism():
    optimizer = StrategyOptimizer()
    cand = create_sample_candidate("SCN_001")
    result = optimizer.optimize([cand])
    strat = result.ranked_strategies[0]
    assert strat.ranking_explanation == DEFAULT_RANKING_EXPLANATION
    assert "Ranked primarily by total race time" in strat.ranking_explanation


# 27. Full-Sort vs Top-K Consistency (CRITICAL CROSS-CHECK)
def test_full_sort_vs_top_k_consistency():
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
    cands = [
        create_sample_candidate(
            f"SCN_{i:03d}",
            race_time=5000.0 + (i * 37 % 100),
            pit_stops=i % 3,
            fuel_kg=10.0 - (i % 5),
            tire_wear=30.0 + (i % 10),
            canonical_key=f"KEY_{i % 4}",
        )
        for i in range(50)
    ]

    # Full sort manually
    sorted_full = sorted(cands, key=lambda c: (c.total_race_time_sec, c.pit_stop_count, -c.final_fuel_kg, c.avg_final_tire_wear_pct, c.canonical_key, c.scenario_id))
    expected_top5_ids = [c.scenario_id for c in sorted_full[:5]]

    # Optimizer Top-5
    res = optimizer.optimize(cands, override_top_k=5)
    actual_top5_ids = [s.scenario_id for s in res.ranked_strategies]

    assert actual_top5_ids == expected_top5_ids


# 28. Large Candidate Benchmark
def test_large_candidate_benchmark():
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=10))
    cands = [
        create_sample_candidate(
            f"SCN_{i:06d}",
            race_time=5000.0 + (i * 13 % 1000),
            pit_stops=i % 4,
            fuel_kg=1.0 + (i % 10),
            tire_wear=10.0 + (i % 50),
            canonical_key=f"KEY_{i % 8}",
        )
        for i in range(1000)  # 1,000 candidates test
    ]
    res = optimizer.optimize(cands)
    assert res.total_candidates == 1000
    assert len(res.ranked_strategies) == 10


# 29. G.4.5.2 Integration (Scenario -> OptimizationCandidate)
def test_g452_integration():
    race_cfg = RaceConfig(race_id="MONZA", total_laps=20, starting_fuel=60.0)
    constraints = ScenarioConstraints(pit_step_laps=5)
    generator = ScenarioGenerator(race_cfg, constraints)
    gen_res = generator.generate_scenarios()

    scenarios = gen_res.scenarios[:5]
    cands = []
    for idx, scenario in enumerate(scenarios):
        cand = OptimizationCandidate(
            scenario_id=scenario.scenario_id,
            canonical_key=scenario.canonical_key,
            valid=True,
            warning_count=0,
            total_race_time_sec=1800.0 + idx * 5.0,
            pit_stop_count=scenario.number_of_stops,
            final_fuel_kg=5.0,
            avg_final_tire_wear_pct=30.0,
        )
        cands.append(cand)

    optimizer = StrategyOptimizer()
    result = optimizer.optimize(cands)
    assert result.total_candidates == len(scenarios)
    assert result.ranked_strategies[0].scenario_id == scenarios[0].scenario_id


# 30. G.4.5.3 Integration (SimulationResult -> OptimizationCandidate)
def test_g453_integration():
    race_cfg = RaceConfig(race_id="TEST_RACE", total_laps=10, starting_fuel=30.0)
    sim = StrategySimulator(race_cfg)
    constraints = ScenarioConstraints(pit_step_laps=5)
    gen = ScenarioGenerator(race_cfg, constraints)
    gen_res = gen.generate_scenarios()

    scenarios = gen_res.scenarios[:2]
    optimizer = StrategyOptimizer()
    cands = []
    for scenario in scenarios:
        sim_res = sim.simulate_strategy(scenario.stints, scenario.pit_stops, base_lap_time_sec=90.0)
        val_res = ValidationResult(scenario_id=scenario.scenario_id, race_id="TEST_RACE", valid=True, severity="NONE")

        cand = OptimizationCandidate.from_simulation_and_validation(sim_res, val_res, scenario=scenario)
        cands.append(cand)

    result = optimizer.optimize(cands)
    assert result.total_candidates == len(scenarios)
    assert result.valid_candidates == len(scenarios)


# 31. G.4.5.4 Integration (Full Pipeline End-to-End: G.4.5.2 -> G.4.5.3 -> G.4.5.4 -> G.4.5.5)
def test_g454_integration():
    race_cfg = RaceConfig(race_id="MONZA_50", total_laps=20, starting_fuel=60.0)
    sim = StrategySimulator(race_cfg)
    validator = ConstraintValidator(race_cfg)
    constraints = ScenarioConstraints(pit_step_laps=5)
    generator = ScenarioGenerator(race_cfg, constraints)
    gen_res = generator.generate_scenarios()

    scenarios = gen_res.scenarios[:5]
    pairs = []
    for scenario in scenarios:
        sim_res = sim.simulate_strategy(scenario.stints, scenario.pit_stops, base_lap_time_sec=80.0)
        val_res = validator.validate(sim_res, scenario.scenario_id)
        pairs.append((sim_res, val_res, scenario))

    optimizer = StrategyOptimizer(OptimizationConfig(top_k=3))
    ranking_res = optimizer.optimize(pairs)

    assert ranking_res.total_candidates == len(scenarios)
    assert ranking_res.valid_candidates <= len(scenarios)
    assert len(ranking_res.ranked_strategies) <= 3
    if len(ranking_res.ranked_strategies) > 0:
        leader = ranking_res.ranked_strategies[0]
        assert leader.rank == 1
        assert leader.delta_to_leader_sec == 0.0
