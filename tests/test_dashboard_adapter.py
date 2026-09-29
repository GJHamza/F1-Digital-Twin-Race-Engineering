# -*- coding: utf-8 -*-
"""
Comprehensive Unit & Integration Test Suite for G.4.6.1 Strategy Dashboard Adapter.
Verifies all 20 mandatory test categories plus end-to-end pipeline integration.
"""

import copy
import pytest
import pandas as pd
from typing import List

from ml.strategy import (
    OptimizationConfig,
    OptimizationCandidate,
    RankedStrategy,
    RankingResult,
    StrategyOptimizer,
    StrategyDashboardAdapter,
    RaceConfig,
    ScenarioConstraints,
    ScenarioGenerator,
    StrategySimulator,
    ConstraintValidator,
    SimulationResult,
    ValidationResult,
    Violation,
)


def create_sample_ranking_result() -> RankingResult:
    """Helper factory constructing a mock RankingResult with 3 ranked strategies."""
    cands = [
        OptimizationCandidate("SCN_001", "SOFT:1-25|MEDIUM:26-50", True, 0, 5000.0, 1, 5.0, 30.0),
        OptimizationCandidate("SCN_002", "HARD:1-30|MEDIUM:31-50", True, 1, 5015.5, 1, 8.0, 25.0),
        OptimizationCandidate("SCN_003", "SOFT:1-15|SOFT:16-30|MEDIUM:31-50", True, 0, 5040.0, 2, 4.0, 35.0),
    ]
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=10))
    return optimizer.optimize(cands)


# 1. RankingResult is accepted
def test_adapter_accepts_ranking_result():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    assert adapter.ranking_result == res


def test_adapter_rejects_none_ranking_result():
    with pytest.raises(ValueError, match="ranking_result cannot be None"):
        StrategyDashboardAdapter(None)


# 2. Empty RankingResult is handled correctly
def test_empty_ranking_result():
    optimizer = StrategyOptimizer()
    empty_res = optimizer.optimize([])
    adapter = StrategyDashboardAdapter(empty_res)

    df_lead = adapter.leaderboard_dataframe()
    assert isinstance(df_lead, pd.DataFrame)
    assert df_lead.empty
    assert list(df_lead.columns) == [
        "rank", "scenario_id", "canonical_key", "total_race_time_sec",
        "pit_stop_count", "final_fuel_kg", "avg_final_tire_wear_pct",
        "warning_count", "delta_to_leader_sec", "ranking_explanation"
    ]

    df_comp = adapter.comparison_dataframe()
    assert isinstance(df_comp, pd.DataFrame)
    assert df_comp.empty


# 3. Leaderboard DataFrame contains expected available columns
def test_leaderboard_columns():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df = adapter.leaderboard_dataframe()

    expected_cols = [
        "rank", "scenario_id", "canonical_key", "total_race_time_sec",
        "pit_stop_count", "final_fuel_kg", "avg_final_tire_wear_pct",
        "warning_count", "delta_to_leader_sec", "ranking_explanation"
    ]
    assert list(df.columns) == expected_cols


# 4. Row count matches ranked strategies
def test_leaderboard_row_count():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df = adapter.leaderboard_dataframe()
    assert len(df) == len(res.ranked_strategies)
    assert len(df) == 3


# 5. Values are preserved exactly
def test_values_preserved_exactly():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df = adapter.leaderboard_dataframe()

    top = res.ranked_strategies[0]
    row0 = df.iloc[0]
    assert row0["rank"] == top.rank
    assert row0["scenario_id"] == top.scenario_id
    assert row0["canonical_key"] == top.canonical_key
    assert row0["total_race_time_sec"] == round(top.total_race_time_sec, 3)
    assert row0["delta_to_leader_sec"] == 0.0
    assert row0["pit_stop_count"] == top.pit_stop_count
    assert row0["final_fuel_kg"] == round(top.final_fuel_kg, 3)


# 6. Ranking order is preserved
def test_ranking_order_preserved():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df = adapter.leaderboard_dataframe()
    ranks = df["rank"].tolist()
    assert ranks == [1, 2, 3]
    scen_ids = df["scenario_id"].tolist()
    assert scen_ids == ["SCN_001", "SCN_002", "SCN_003"]


# 7. Adapter does not rerank
def test_adapter_does_not_rerank():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df_comp = adapter.comparison_dataframe()
    # Confirm exact rank order from optimizer is retained
    assert df_comp["scenario_id"].tolist() == [s.scenario_id for s in res.ranked_strategies]


# 8. Adapter does not mutate RankingResult
def test_immutability_ranking_result():
    res = create_sample_ranking_result()
    res_copy = copy.deepcopy(res)
    adapter = StrategyDashboardAdapter(res)
    adapter.leaderboard_dataframe()
    adapter.comparison_dataframe()

    assert res == res_copy


# 9. Adapter does not mutate RankedStrategy
def test_immutability_ranked_strategy():
    res = create_sample_ranking_result()
    strat_copy = copy.deepcopy(res.ranked_strategies[0])
    adapter = StrategyDashboardAdapter(res)
    adapter.selected_strategy_dataframe("SCN_001")

    assert res.ranked_strategies[0] == strat_copy


# 10. Same input produces deterministic output
def test_deterministic_output():
    res = create_sample_ranking_result()
    adapter1 = StrategyDashboardAdapter(res)
    adapter2 = StrategyDashboardAdapter(res)

    df1 = adapter1.leaderboard_dataframe()
    df2 = adapter2.leaderboard_dataframe()
    pd.testing.assert_frame_equal(df1, df2)


# 11. scenario_id lookup works
def test_selected_strategy_lookup():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df_sel = adapter.selected_strategy_dataframe("SCN_002")

    assert len(df_sel) == 1
    assert df_sel.iloc[0]["scenario_id"] == "SCN_002"
    assert df_sel.iloc[0]["rank"] == 2


# 12. Unknown scenario_id produces a clear error
def test_unknown_scenario_id_error():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    with pytest.raises(ValueError, match="Scenario ID 'SCN_UNKNOWN' not found in ranking result"):
        adapter.selected_strategy_dataframe("SCN_UNKNOWN")


# 13. Stint DataFrame uses real upstream stint data
def test_stint_dataframe():
    res = create_sample_ranking_result()
    sim_res = SimulationResult(
        race_id="RACE_1",
        total_laps=50,
        total_race_time_sec=5000.0,
        pit_stop_count=1,
        total_pit_time_sec=22.5,
        final_fuel_kg=5.0,
        total_fuel_consumed_kg=95.0,
        final_tire_wear={"FL": 30.0, "FR": 30.0, "RL": 30.0, "RR": 30.0},
        stint_summary=[
            {"stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 25, "stint_laps": 25, "starting_fuel": 100.0, "ending_fuel": 50.0},
            {"stint_number": 2, "compound": "MEDIUM", "start_lap": 26, "end_lap": 50, "stint_laps": 25, "starting_fuel": 50.0, "ending_fuel": 5.0},
        ],
        pit_summary=[],
        lap_records=[],
    )
    sim_res.scenario_id = "SCN_001"  # Attach scenario_id attribute

    adapter = StrategyDashboardAdapter(res, simulation_results={"SCN_001": sim_res})
    df_stint = adapter.stint_dataframe("SCN_001")

    assert len(df_stint) == 2
    assert list(df_stint["compound"]) == ["SOFT", "MEDIUM"]
    assert list(df_stint["stint_laps"]) == [25, 25]


# 14. Lap DataFrame uses real upstream lap data
def test_lap_dataframe():
    res = create_sample_ranking_result()
    sim_res = SimulationResult(
        race_id="RACE_1",
        total_laps=2,
        total_race_time_sec=180.0,
        pit_stop_count=0,
        total_pit_time_sec=0.0,
        final_fuel_kg=96.0,
        total_fuel_consumed_kg=4.0,
        final_tire_wear={"FL": 5.0, "FR": 5.0, "RL": 5.0, "RR": 5.0},
        stint_summary=[],
        pit_summary=[],
        lap_records=[
            {"lap_number": 1, "stint_number": 1, "compound": "SOFT", "tire_age_laps": 1, "fuel_kg": 98.0, "fuel_consumed_kg": 2.0, "tire_wear_fl": 2.5, "tire_wear_fr": 2.5, "tire_wear_rl": 2.5, "tire_wear_rr": 2.5, "avg_tire_wear": 2.5, "lap_time_sec": 90.0, "pit_loss_sec": 0.0, "cum_time_sec": 90.0},
            {"lap_number": 2, "stint_number": 1, "compound": "SOFT", "tire_age_laps": 2, "fuel_kg": 96.0, "fuel_consumed_kg": 2.0, "tire_wear_fl": 5.0, "tire_wear_fr": 5.0, "tire_wear_rl": 5.0, "tire_wear_rr": 5.0, "avg_tire_wear": 5.0, "lap_time_sec": 90.0, "pit_loss_sec": 0.0, "cum_time_sec": 180.0},
        ],
    )

    adapter = StrategyDashboardAdapter(res, simulation_results={"SCN_001": sim_res})
    df_lap = adapter.lap_dataframe("SCN_001")

    assert len(df_lap) == 2
    assert list(df_lap["lap_number"]) == [1, 2]
    assert list(df_lap["fuel_kg"]) == [98.0, 96.0]


# 15. Validation DataFrame uses authoritative validation data
def test_validation_dataframe():
    res = create_sample_ranking_result()
    viol = Violation("FUEL_DEPLETED", "FUEL", "CRITICAL", "Fuel depleted at lap 48", 0.0, 5.0, lap_number=48)
    val_res = ValidationResult("SCN_001", "RACE_1", False, "CRITICAL_VIOLATION", violations=(viol,), warnings=("Low fuel alert",))

    adapter = StrategyDashboardAdapter(res, validation_results={"SCN_001": val_res})
    df_val = adapter.validation_dataframe("SCN_001")

    assert len(df_val) == 1
    assert df_val.iloc[0]["constraint_id"] == "FUEL_DEPLETED"
    assert df_val.iloc[0]["category"] == "FUEL"
    assert df_val.iloc[0]["lap_number"] == 48


# 16. Missing optional dashboard data is handled explicitly
def test_missing_optional_data_handling():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)  # No sim_results or val_results supplied

    with pytest.raises(ValueError, match="Stint details unavailable for scenario ID 'SCN_001'"):
        adapter.stint_dataframe("SCN_001")

    with pytest.raises(ValueError, match="Lap telemetry unavailable for scenario ID 'SCN_001'"):
        adapter.lap_dataframe("SCN_001")


# 17. No fabricated tire temperature fields
def test_no_fabricated_tire_temperatures():
    res = create_sample_ranking_result()
    sim_res = SimulationResult(
        race_id="RACE_1", total_laps=1, total_race_time_sec=90.0, pit_stop_count=0,
        total_pit_time_sec=0.0, final_fuel_kg=98.0, total_fuel_consumed_kg=2.0,
        final_tire_wear={"FL": 2.0}, stint_summary=[], pit_summary=[],
        lap_records=[{"lap_number": 1, "lap_time_sec": 90.0}],
    )
    adapter = StrategyDashboardAdapter(res, simulation_results={"SCN_001": sim_res})
    df_lap = adapter.lap_dataframe("SCN_001")

    assert "tire_temperatures" not in df_lap.columns
    assert "tire_temp" not in df_lap.columns


# 18. No fabricated vehicle setup fields
def test_no_fabricated_vehicle_setup():
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)
    df_lead = adapter.leaderboard_dataframe()

    assert "vehicle_setup" not in df_lead.columns
    assert "wing_angle" not in df_lead.columns


# 19. No simulation is executed by the adapter
def test_no_simulation_executed(monkeypatch):
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    def mock_simulate(*args, **kwargs):
        raise RuntimeError("StrategySimulator.simulate_strategy should not be called by adapter!")

    monkeypatch.setattr("ml.strategy.simulator.StrategySimulator.simulate_strategy", mock_simulate)

    # Calling adapter methods must not invoke simulator
    adapter.leaderboard_dataframe()
    adapter.comparison_dataframe()
    adapter.selected_strategy_dataframe("SCN_001")


# 20. No optimization is executed by the adapter
def test_no_optimization_executed(monkeypatch):
    res = create_sample_ranking_result()
    adapter = StrategyDashboardAdapter(res)

    def mock_optimize(*args, **kwargs):
        raise RuntimeError("StrategyOptimizer.optimize should not be called by adapter!")

    monkeypatch.setattr("ml.strategy.strategy_optimizer.StrategyOptimizer.optimize", mock_optimize)

    adapter.leaderboard_dataframe()
    adapter.comparison_dataframe()
    adapter.selected_strategy_dataframe("SCN_001")


# 21. FULL INTEGRATION TEST (ScenarioGenerator -> StrategySimulator -> ConstraintValidator -> StrategyOptimizer -> StrategyDashboardAdapter)
def test_end_to_end_pipeline_adapter_integration():
    race_cfg = RaceConfig(race_id="E2E_MONZA_50", total_laps=20, starting_fuel=60.0)
    constraints = ScenarioConstraints(pit_step_laps=5)
    generator = ScenarioGenerator(race_cfg, constraints)
    gen_res = generator.generate_scenarios()

    scenarios = gen_res.scenarios[:3]
    simulator = StrategySimulator(race_cfg)
    validator = ConstraintValidator(race_cfg)

    sim_dict = {}
    val_dict = {}
    scen_dict = {}
    pairs = []

    for scenario in scenarios:
        sim_res = simulator.simulate_strategy(scenario.stints, scenario.pit_stops, base_lap_time_sec=80.0)
        val_res = validator.validate(sim_res, scenario.scenario_id)

        sim_dict[scenario.scenario_id] = sim_res
        val_dict[scenario.scenario_id] = val_res
        scen_dict[scenario.scenario_id] = scenario
        pairs.append((sim_res, val_res, scenario))

    optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
    ranking_res = optimizer.optimize(pairs)

    # Instantiate Dashboard Adapter
    adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results=sim_dict,
        validation_results=val_dict,
        scenarios=scen_dict,
    )

    # Verify Leaderboard DataFrame
    df_lead = adapter.leaderboard_dataframe()
    assert len(df_lead) == len(ranking_res.ranked_strategies)
    top_strat = ranking_res.ranked_strategies[0]
    assert df_lead.iloc[0]["scenario_id"] == top_strat.scenario_id
    assert df_lead.iloc[0]["rank"] == 1
    assert df_lead.iloc[0]["delta_to_leader_sec"] == 0.0

    # Verify Stint DataFrame for leader
    df_stint = adapter.stint_dataframe(top_strat.scenario_id)
    assert len(df_stint) == top_strat.pit_stop_count + 1

    # Verify Lap DataFrame for leader
    df_lap = adapter.lap_dataframe(top_strat.scenario_id)
    assert len(df_lap) == 20
    assert df_lap.iloc[0]["lap_number"] == 1
    assert df_lap.iloc[-1]["lap_number"] == 20

    # Verify Validation DataFrame for leader
    df_val = adapter.validation_dataframe(top_strat.scenario_id)
    assert bool(df_val.iloc[0]["valid"]) is True
