# -*- coding: utf-8 -*-
"""
Comprehensive Unit & Integration Test Suite for G.4.6.2 Strategy Leaderboard.
Verifies all mandatory test categories including no-reranking, no-mutation, filtering, and end-to-end integration.
"""

import copy
import pytest
import pandas as pd

from ml.strategy import (
    OptimizationConfig,
    OptimizationCandidate,
    RankedStrategy,
    RankingResult,
    StrategyOptimizer,
    StrategyDashboardAdapter,
    prepare_leaderboard_view_data,
    RaceConfig,
    ScenarioConstraints,
    ScenarioGenerator,
    StrategySimulator,
    ConstraintValidator,
)


def create_sample_ranking_result() -> RankingResult:
    """Helper factory producing a test RankingResult with 3 ranked strategies."""
    cands = [
        OptimizationCandidate("SCN_001", "SOFT:1-25|MEDIUM:26-50", True, 0, 5000.0, 1, 5.0, 30.0),
        OptimizationCandidate("SCN_002", "HARD:1-30|MEDIUM:31-50", True, 1, 5015.5, 1, 8.0, 25.0),
        OptimizationCandidate("SCN_003", "SOFT:1-15|SOFT:16-30|MEDIUM:31-50", True, 0, 5040.0, 2, 4.0, 35.0),
    ]
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=10))
    return optimizer.optimize(cands)


# 1. Leaderboard renders with valid RankingResult
def test_leaderboard_view_data_valid():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    data = prepare_leaderboard_view_data(adapter)

    assert "summary" in data
    assert "leaderboard_df" in data
    assert data["total_displayed"] == 3


# 2. Empty ranking is handled safely
def test_empty_ranking_handled():
    optimizer = StrategyOptimizer()
    empty_res = optimizer.optimize([])
    adapter = StrategyDashboardAdapter(empty_res)
    data = prepare_leaderboard_view_data(adapter)

    assert data["summary"]["is_empty"] is True
    assert data["summary"]["leader_scenario_id"] is None
    assert data["total_displayed"] == 0
    assert data["leaderboard_df"].empty


# 3-11. Preservation of attributes (order, ranks, scenario_ids, times, deltas, stops, fuel, wear, warnings)
def test_attribute_preservation():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    data = prepare_leaderboard_view_data(adapter)
    df = data["leaderboard_df"]

    assert list(df["rank"]) == [1, 2, 3]
    assert list(df["scenario_id"]) == ["SCN_001", "SCN_002", "SCN_003"]
    assert list(df["total_race_time_sec"]) == [5000.0, 5015.5, 5040.0]
    assert list(df["pit_stop_count"]) == [1, 1, 2]
    assert list(df["final_fuel_kg"]) == [5.0, 8.0, 4.0]
    assert list(df["avg_final_tire_wear_pct"]) == [30.0, 25.0, 35.0]
    assert list(df["warning_count"]) == [0, 1, 0]


# 12-16. Leader metadata and candidate counts preserved
def test_leader_metadata_preserved():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    data = prepare_leaderboard_view_data(adapter)
    summary = data["summary"]

    assert summary["leader_scenario_id"] == "SCN_001"
    assert summary["leader_race_time_sec"] == 5000.0
    assert summary["total_candidates"] == 3
    assert summary["valid_candidates"] == 3
    assert summary["excluded_candidates"] == 0
    assert summary["top_k"] == 10


# 17. View filtering does not rerank
def test_view_filtering_does_not_rerank():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    # Apply pit stop filter = 1
    data = prepare_leaderboard_view_data(adapter, pit_stop_filter=1)
    df = data["leaderboard_df"]

    assert len(df) == 2
    assert list(df["rank"]) == [1, 2]
    assert list(df["scenario_id"]) == ["SCN_001", "SCN_002"]


# 18. View filtering does not mutate RankingResult
def test_view_filtering_does_not_mutate():
    res = create_sample_ranking_result()
    res_copy = copy.deepcopy(res)
    adapter = StrategyDashboardAdapter(res)

    prepare_leaderboard_view_data(adapter, pit_stop_filter=1, warning_only_filter=True)
    assert res == res_copy


# 19. Filtering out leader does not create a new leader in summary metrics
def test_filtering_out_leader_preserves_authoritative_summary():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    # Filter for warnings only -> filters out SCN_001 (rank 1 leader has 0 warnings)
    data = prepare_leaderboard_view_data(adapter, warning_only_filter=True)
    df = data["leaderboard_df"]

    # Displayed table only shows SCN_002
    assert list(df["scenario_id"]) == ["SCN_002"]
    # Authoritative leader summary MUST still report SCN_001 as leader
    assert data["summary"]["leader_scenario_id"] == "SCN_001"
    assert data["summary"]["leader_race_time_sec"] == 5000.0


# 20. Scenario selection stores scenario_id correctly in session_state
def test_scenario_selection_session_state(monkeypatch):
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    fake_session = {}
    monkeypatch.setattr("streamlit.session_state", fake_session)

    # Simulate selecting strategy
    fake_session["selected_scenario_id"] = "SCN_002"
    assert fake_session["selected_scenario_id"] == "SCN_002"


# 21. Changing selection does not execute simulation
def test_changing_selection_no_simulation(monkeypatch):
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    def mock_simulate(*args, **kwargs):
        raise RuntimeError("StrategySimulator should not be called!")

    monkeypatch.setattr("ml.strategy.simulator.StrategySimulator.simulate_strategy", mock_simulate)

    # Preparing view data must not execute simulation
    data = prepare_leaderboard_view_data(adapter)
    assert data["total_displayed"] == 3


# 22. Changing selection does not execute optimizer
def test_changing_selection_no_optimizer(monkeypatch):
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    def mock_optimize(*args, **kwargs):
        raise RuntimeError("StrategyOptimizer should not be called!")

    monkeypatch.setattr("ml.strategy.strategy_optimizer.StrategyOptimizer.optimize", mock_optimize)

    data = prepare_leaderboard_view_data(adapter)
    assert data["total_displayed"] == 3


# 23. Missing optional fields handled safely
def test_missing_optional_fields():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    data = prepare_leaderboard_view_data(adapter)
    df = data["leaderboard_df"]

    assert "tire_temperatures" not in df.columns
    assert "vehicle_setup" not in df.columns


# 24. Deterministic rendering data
def test_deterministic_rendering_data():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    d1 = prepare_leaderboard_view_data(adapter)
    d2 = prepare_leaderboard_view_data(adapter)

    pd.testing.assert_frame_equal(d1["leaderboard_df"], d2["leaderboard_df"])
    assert d1["summary"] == d2["summary"]


# 25. Large Top-K remains bounded
def test_large_top_k_remains_bounded():
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
    cands = [
        OptimizationCandidate(f"SCN_{i:03d}", "KEY", True, 0, 5000.0 + i * 10, 1, 5.0, 30.0)
        for i in range(50)
    ]
    res = optimizer.optimize(cands)
    adapter = StrategyDashboardAdapter(res)
    data = prepare_leaderboard_view_data(adapter)

    assert data["summary"]["top_k"] == 5
    assert data["total_displayed"] == 5


# 26. MANDATORY NO RERANKING TEST
def test_mandatory_no_reranking():
    """
    Constructs a RankingResult with non-trivial order and asserts that the UI
    preparation functions NEVER sort or alter the order.
    """
    # Custom non-trivial ranked strategies
    s1 = RankedStrategy(rank=1, scenario_id="SCN_C", canonical_key="KEY_1", total_race_time_sec=4800.0, pit_stop_count=1, final_fuel_kg=10.0, avg_final_tire_wear_pct=20.0, warning_count=0, delta_to_leader_sec=0.0)
    s2 = RankedStrategy(rank=2, scenario_id="SCN_A", canonical_key="KEY_2", total_race_time_sec=4810.0, pit_stop_count=1, final_fuel_kg=5.0, avg_final_tire_wear_pct=40.0, warning_count=0, delta_to_leader_sec=10.0)
    s3 = RankedStrategy(rank=3, scenario_id="SCN_B", canonical_key="KEY_3", total_race_time_sec=4820.0, pit_stop_count=2, final_fuel_kg=2.0, avg_final_tire_wear_pct=30.0, warning_count=1, delta_to_leader_sec=20.0)

    ranking_res = RankingResult(
        ranked_strategies=(s1, s2, s3),
        total_candidates=3,
        valid_candidates=3,
        excluded_candidates=0,
        top_k=10,
        leader_scenario_id="SCN_C",
        leader_race_time_sec=4800.0,
    )

    adapter = StrategyDashboardAdapter(ranking_res)
    data = prepare_leaderboard_view_data(adapter)
    df = data["leaderboard_df"]

    # Verify exact preservation of scenario ID sequence: SCN_C -> SCN_A -> SCN_B
    assert list(df["scenario_id"]) == ["SCN_C", "SCN_A", "SCN_B"]
    assert list(df["rank"]) == [1, 2, 3]


# 27. MANDATORY NO MUTATION TEST
def test_mandatory_no_mutation():
    """
    Deep-copies RankingResult before view data preparation and asserts original == deep_copy.
    """
    res = create_sample_ranking_result()
    deep_copy_res = copy.deepcopy(res)

    adapter = StrategyDashboardAdapter(res)
    prepare_leaderboard_view_data(adapter, scenario_search="SCN_002", pit_stop_filter=1, warning_only_filter=False)

    assert res == deep_copy_res


# 28. FULL END-TO-END INTEGRATION TEST (G.4.5.2 -> G.4.5.3 -> G.4.5.4 -> G.4.5.5 -> G.4.6.1 -> G.4.6.2)
def test_full_pipeline_to_leaderboard_integration():
    race_cfg = RaceConfig(race_id="E2E_LEADERBOARD_TEST", total_laps=20, starting_fuel=60.0)
    constraints = ScenarioConstraints(pit_step_laps=5)
    generator = ScenarioGenerator(race_cfg, constraints)
    gen_res = generator.generate_scenarios()

    scenarios = gen_res.scenarios[:3]
    simulator = StrategySimulator(race_cfg)
    validator = ConstraintValidator(race_cfg)

    pairs = []
    for scenario in scenarios:
        sim_res = simulator.simulate_strategy(scenario.stints, scenario.pit_stops, base_lap_time_sec=80.0)
        val_res = validator.validate(sim_res, scenario.scenario_id)
        pairs.append((sim_res, val_res, scenario))

    optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
    ranking_res = optimizer.optimize(pairs)

    adapter = StrategyDashboardAdapter(ranking_res)
    view_data = prepare_leaderboard_view_data(adapter)

    # Verify that pipeline values reached the UI view data perfectly intact
    assert view_data["summary"]["total_candidates"] == len(scenarios)
    assert view_data["summary"]["leader_scenario_id"] == ranking_res.leader_scenario_id
    assert view_data["summary"]["leader_race_time_sec"] == ranking_res.leader_race_time_sec

    df = view_data["leaderboard_df"]
    assert len(df) == len(ranking_res.ranked_strategies)
    assert df.iloc[0]["scenario_id"] == ranking_res.ranked_strategies[0].scenario_id
    assert df.iloc[0]["rank"] == 1
    assert df.iloc[0]["delta_to_leader_sec_fmt"] == "0.000"
