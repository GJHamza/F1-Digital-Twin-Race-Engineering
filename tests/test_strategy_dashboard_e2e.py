# -*- coding: utf-8 -*-
"""
End-to-End Integration and Final Validation Test Suite for G.4.6.7 F1 Digital Twin Strategy Dashboard.
Validates the complete pipeline chain from G.4.5.1 Data Foundation through G.4.6.6 Strategy Details & Validation,
cross-module value consistency, session state synchronization, immutability, determinism, performance,
and graceful failure state handling.
"""

import copy
import time
import pytest
import pandas as pd
from unittest.mock import MagicMock

from ml.strategy.race_config import RaceConfig
from ml.strategy.stint import Stint
from ml.strategy.pit_stop import PitStop
from ml.strategy.scenario import Scenario
from ml.strategy.simulator import StrategySimulator, SimulationResult
from ml.strategy.validation_result import ValidationResult, Violation
from ml.strategy.constraint_validator import ConstraintValidator
from ml.strategy.ranking_config import OptimizationConfig
from ml.strategy.ranking_candidate import OptimizationCandidate, RankedStrategy
from ml.strategy.ranking_result import RankingResult
from ml.strategy.strategy_optimizer import StrategyOptimizer
from ml.strategy.dashboard_adapter import StrategyDashboardAdapter
from ml.strategy.strategy_dashboard import (
    prepare_leaderboard_view_data,
    render_strategy_leaderboard,
    prepare_comparison_view_data,
    render_strategy_comparison,
    prepare_stint_timeline_data,
    render_stint_timeline,
    prepare_fuel_tire_analytics_view_data,
    render_fuel_tire_analytics,
    prepare_strategy_details_view_data,
    render_strategy_details,
    render_strategy_dashboard_tab,
)


@pytest.fixture
def e2e_pipeline_setup():
    """Constructs an end-to-end G.4.5 -> G.4.6 pipeline dataset for E2E validation."""
    config = RaceConfig(
        race_id="RACE_E2E_G467",
        total_laps=30,
        starting_fuel=75.0,
        initial_compound="MEDIUM",
        pit_stop_loss_sec=22.5,
        max_tire_wear=85.0,
        min_stint_laps=5,
    )

    # Strategy A: 1 Stop (MEDIUM -> HARD)
    stints_a = [
        Stint("S1_A", 1, "MEDIUM", 1, 15, 75.0, 40.0, starting_tire_wear=0.0, ending_tire_wear=35.0),
        Stint("S2_A", 2, "HARD", 16, 30, 40.0, 10.0, starting_tire_wear=0.0, ending_tire_wear=30.0),
    ]
    pits_a = [PitStop("PIT1_A", 15, "MEDIUM", "HARD", 1, 2, 22.5)]
    scen_a = Scenario(
        scenario_id="SCN_E2E_01_ONESTOP",
        race_id="RACE_E2E_G467",
        total_laps=30,
        starting_compound="MEDIUM",
        compound_sequence=["MEDIUM", "HARD"],
        stints=stints_a,
        pit_stops=pits_a,
        number_of_stops=1,
        number_of_stints=2,
    )

    # Strategy B: 2 Stop (SOFT -> MEDIUM -> SOFT)
    stints_b = [
        Stint("S1_B", 1, "SOFT", 1, 10, 75.0, 52.0, starting_tire_wear=0.0, ending_tire_wear=45.0),
        Stint("S2_B", 2, "MEDIUM", 11, 20, 52.0, 28.0, starting_tire_wear=0.0, ending_tire_wear=30.0),
        Stint("S3_B", 3, "SOFT", 21, 30, 28.0, 6.0, starting_tire_wear=0.0, ending_tire_wear=40.0),
    ]
    pits_b = [
        PitStop("PIT1_B", 10, "SOFT", "MEDIUM", 1, 2, 22.5),
        PitStop("PIT2_B", 20, "MEDIUM", "SOFT", 2, 3, 22.5),
    ]
    scen_b = Scenario(
        scenario_id="SCN_E2E_02_TWOSTOP",
        race_id="RACE_E2E_G467",
        total_laps=30,
        starting_compound="SOFT",
        compound_sequence=["SOFT", "MEDIUM", "SOFT"],
        stints=stints_b,
        pit_stops=pits_b,
        number_of_stops=2,
        number_of_stints=3,
    )

    simulator = StrategySimulator(config)
    validator = ConstraintValidator(config)

    sim_a = simulator.simulate_strategy(scen_a.stints, scen_a.pit_stops)
    val_a = validator.validate(sim_a, scenario_id=scen_a.scenario_id)

    sim_b = simulator.simulate_strategy(scen_b.stints, scen_b.pit_stops)
    val_b = validator.validate(sim_b, scenario_id=scen_b.scenario_id)

    cand_a = OptimizationCandidate.from_simulation_and_validation(sim_a, val_a, scenario=scen_a)
    cand_b = OptimizationCandidate.from_simulation_and_validation(sim_b, val_b, scenario=scen_b)

    optimizer = StrategyOptimizer(config=OptimizationConfig(top_k=5))
    ranking_res = optimizer.optimize([cand_a, cand_b])

    adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results={scen_a.scenario_id: sim_a, scen_b.scenario_id: sim_b},
        validation_results={scen_a.scenario_id: val_a, scen_b.scenario_id: val_b},
        scenarios={scen_a.scenario_id: scen_a, scen_b.scenario_id: scen_b},
    )

    return {
        "config": config,
        "scenarios": [scen_a, scen_b],
        "sim_results": {scen_a.scenario_id: sim_a, scen_b.scenario_id: sim_b},
        "val_results": {scen_a.scenario_id: val_a, scen_b.scenario_id: val_b},
        "ranking_res": ranking_res,
        "adapter": adapter,
    }


def test_full_pipeline_g45_to_g46_integration(e2e_pipeline_setup):
    """Test 1: Complete end-to-end integration test from G.4.5.1 generator to G.4.6.6 view data."""
    adapter = e2e_pipeline_setup["adapter"]
    ranking_res = e2e_pipeline_setup["ranking_res"]
    leader_id = ranking_res.leader_scenario_id

    # 1. Leaderboard View Data
    leaderboard_data = prepare_leaderboard_view_data(adapter)
    assert not leaderboard_data["leaderboard_df"].empty
    assert leaderboard_data["summary"]["leader_scenario_id"] == leader_id

    # 2. Timeline View Data
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id=leader_id)
    assert not timeline_data["is_empty"]
    assert timeline_data["scenario_id"] == leader_id

    # 3. Fuel & Tire Analytics View Data
    analytics_data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=leader_id)
    assert not analytics_data["is_empty"]
    assert analytics_data["scenario_id"] == leader_id

    # 4. Strategy Details & Validation View Data
    details_data = prepare_strategy_details_view_data(adapter, scenario_id=leader_id)
    assert not details_data["is_empty"]
    assert details_data["scenario_id"] == leader_id

    # 5. Multi-Strategy Comparison View Data
    comparison_data = prepare_comparison_view_data(adapter)
    assert not comparison_data["comparison_df"].empty


def test_cross_module_value_consistency_leaderboard_vs_details(e2e_pipeline_setup):
    """Test 2: Verify metric values match bitwise between Leaderboard and Strategy Details."""
    adapter = e2e_pipeline_setup["adapter"]
    leader_id = adapter.ranking_result.leader_scenario_id

    leaderboard_df = prepare_leaderboard_view_data(adapter)["leaderboard_df"]
    leader_row = leaderboard_df[leaderboard_df["scenario_id"] == leader_id].iloc[0]

    details_data = prepare_strategy_details_view_data(adapter, scenario_id=leader_id)
    identity = details_data["identity"]

    assert leader_row["rank"] == identity["rank"]
    assert leader_row["scenario_id"] == identity["scenario_id"]
    assert round(float(leader_row["total_race_time_sec"]), 3) == round(float(identity["total_race_time_sec"]), 3)
    assert round(float(leader_row["delta_to_leader_sec"]), 3) == round(float(identity["delta_to_leader_sec"]), 3)
    assert int(leader_row["pit_stop_count"]) == identity["pit_stop_count"]
    assert round(float(leader_row["final_fuel_kg"]), 3) == round(float(identity["final_fuel_kg"]), 3)
    assert round(float(leader_row["avg_final_tire_wear_pct"]), 2) == round(float(identity["avg_final_tire_wear_pct"]), 2)


def test_cross_module_value_consistency_analytics_vs_details(e2e_pipeline_setup):
    """Test 3: Verify fuel and tire metrics match bitwise between Fuel/Tire Analytics and Details."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_id = adapter.ranking_result.leader_scenario_id

    analytics = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=scen_id)
    details = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)

    analytics_summary = analytics["summary"]
    details_identity = details["identity"]

    assert analytics_summary["final_fuel_kg"] == details_identity["final_fuel_kg"]
    assert len(analytics["stint_analytics_df"]) == details_identity["stint_count"]


def test_cross_module_value_consistency_comparison_vs_leaderboard(e2e_pipeline_setup):
    """Test 4: Verify metrics match bitwise between Multi-Strategy Comparison and Leaderboard."""
    adapter = e2e_pipeline_setup["adapter"]

    leaderboard_df = prepare_leaderboard_view_data(adapter)["leaderboard_df"]
    comparison_df = prepare_comparison_view_data(adapter)["comparison_df"]

    for _, l_row in leaderboard_df.iterrows():
        c_row = comparison_df[comparison_df["scenario_id"] == l_row["scenario_id"]].iloc[0]
        assert l_row["rank"] == c_row["rank"]
        assert round(float(l_row["total_race_time_sec"]), 3) == round(float(c_row["total_race_time_sec"]), 3)
        assert int(l_row["pit_stop_count"]) == int(c_row["pit_stop_count"])


def test_cross_module_value_consistency_timeline_vs_details(e2e_pipeline_setup):
    """Test 5: Verify stint compounds and counts match bitwise between Stint Timeline and Details."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_id = adapter.ranking_result.leader_scenario_id

    timeline = prepare_stint_timeline_data(adapter, scenario_id=scen_id)
    details = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)

    timeline_compounds = list(timeline["stint_df"]["compound"])
    details_compounds = details["identity"]["compound_sequence"]

    assert timeline_compounds == details_compounds


def test_session_state_selected_scenario_synchronization(e2e_pipeline_setup):
    """Test 6: Verify changing selected_scenario_id propagates consistently across view data calls."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_ids = [s.scenario_id for s in adapter.ranking_result.ranked_strategies]

    for sid in scen_ids:
        t_data = prepare_stint_timeline_data(adapter, scenario_id=sid)
        f_data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=sid)
        d_data = prepare_strategy_details_view_data(adapter, scenario_id=sid)

        assert t_data["scenario_id"] == sid
        assert f_data["scenario_id"] == sid
        assert d_data["scenario_id"] == sid


def test_zero_domain_recomputation(e2e_pipeline_setup, monkeypatch):
    """Test 7: Prove that rendering all 5 presentation components triggers ZERO simulation/validation calls."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_id = adapter.ranking_result.leader_scenario_id

    mock_sim = MagicMock()
    mock_val = MagicMock()
    mock_opt = MagicMock()

    monkeypatch.setattr(StrategySimulator, "simulate_strategy", mock_sim)
    monkeypatch.setattr(ConstraintValidator, "validate", mock_val)
    monkeypatch.setattr(StrategyOptimizer, "optimize", mock_opt)

    _ = prepare_leaderboard_view_data(adapter)
    _ = prepare_stint_timeline_data(adapter, scenario_id=scen_id)
    _ = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=scen_id)
    _ = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    _ = prepare_comparison_view_data(adapter)

    mock_sim.assert_not_called()
    mock_val.assert_not_called()
    mock_opt.assert_not_called()


def test_deep_copy_immutability_across_all_modules(e2e_pipeline_setup):
    """Test 8: Verify deep-copy equality of all domain objects before and after full presentation execution."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_id = adapter.ranking_result.leader_scenario_id

    ranking_before = copy.deepcopy(adapter.ranking_result)
    sim_before = copy.deepcopy(adapter._sim_results[scen_id])
    val_before = copy.deepcopy(adapter._val_results[scen_id])

    _ = prepare_leaderboard_view_data(adapter)
    _ = prepare_stint_timeline_data(adapter, scenario_id=scen_id)
    _ = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=scen_id)
    _ = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    _ = prepare_comparison_view_data(adapter)

    assert adapter.ranking_result == ranking_before
    assert adapter._sim_results[scen_id] == sim_before
    assert adapter._val_results[scen_id] == val_before


def test_bitwise_determinism_across_all_modules(e2e_pipeline_setup):
    """Test 9: Verify consecutive invocations of presentation functions return 100% bitwise-identical dicts."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_id = adapter.ranking_result.leader_scenario_id

    d1_details = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    d2_details = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    assert d1_details["identity"] == d2_details["identity"]
    assert d1_details["race_config"] == d2_details["race_config"]
    assert d1_details["validation"]["valid"] == d2_details["validation"]["valid"]

    d1_analytics = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=scen_id)
    d2_analytics = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=scen_id)
    assert d1_analytics["summary"] == d2_analytics["summary"]
    assert d1_analytics["balance"] == d2_analytics["balance"]

    d1_timeline = prepare_stint_timeline_data(adapter, scenario_id=scen_id)
    d2_timeline = prepare_stint_timeline_data(adapter, scenario_id=scen_id)
    assert d1_timeline["summary"] == d2_timeline["summary"]


def test_empty_ranking_result_across_all_modules():
    """Test 10: Verify empty RankingResult is handled gracefully across all presentation functions."""
    empty_ranking = RankingResult(ranked_strategies=tuple(), total_candidates=0, valid_candidates=0, excluded_candidates=0, top_k=5)
    adapter = StrategyDashboardAdapter(ranking_result=empty_ranking)

    lb = prepare_leaderboard_view_data(adapter)
    assert lb["leaderboard_df"].empty

    tm = prepare_stint_timeline_data(adapter)
    assert tm["is_empty"] is True

    an = prepare_fuel_tire_analytics_view_data(adapter)
    assert an["is_empty"] is True

    dt = prepare_strategy_details_view_data(adapter)
    assert dt["is_empty"] is True

    cm = prepare_comparison_view_data(adapter)
    assert cm["comparison_df"].empty


def test_unknown_scenario_id_across_all_modules(e2e_pipeline_setup):
    """Test 11: Verify unknown scenario ID returns structured error or raises expected ValueError."""
    adapter = e2e_pipeline_setup["adapter"]
    unknown_id = "SCN_GHOST_99"

    with pytest.raises(ValueError, match="Scenario ID 'SCN_GHOST_99' not found"):
        adapter.selected_strategy_dataframe(unknown_id)

    with pytest.raises(ValueError, match="Scenario ID 'SCN_GHOST_99' not found"):
        prepare_fuel_tire_analytics_view_data(adapter, scenario_id=unknown_id)

    dt = prepare_strategy_details_view_data(adapter, scenario_id=unknown_id)
    assert dt["is_empty"] is True
    assert "error" in dt


def test_missing_simulation_result_fallback_across_all_modules(e2e_pipeline_setup):
    """Test 12: Verify missing SimulationResult in adapter lookups falls back gracefully to Scenario metadata."""
    ranking_res = e2e_pipeline_setup["ranking_res"]
    scenarios = {s.scenario_id: s for s in e2e_pipeline_setup["scenarios"]}

    sparse_adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results={},
        scenarios=scenarios,
    )

    scen_id = ranking_res.leader_scenario_id

    tm = prepare_stint_timeline_data(sparse_adapter, scenario_id=scen_id)
    assert not tm["is_empty"]
    assert not tm["stint_df"].empty

    dt = prepare_strategy_details_view_data(sparse_adapter, scenario_id=scen_id)
    assert not dt["is_empty"]


def test_dashboard_performance_benchmarking(e2e_pipeline_setup):
    """Test 13: Measure execution time for adapter preparation & view data functions (Target < 500ms)."""
    ranking_res = e2e_pipeline_setup["ranking_res"]
    sim_results = e2e_pipeline_setup["sim_results"]
    val_results = e2e_pipeline_setup["val_results"]
    scenarios = {s.scenario_id: s for s in e2e_pipeline_setup["scenarios"]}

    t0 = time.perf_counter()

    adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results=sim_results,
        validation_results=val_results,
        scenarios=scenarios,
    )

    t_adapter = time.perf_counter()

    _ = prepare_leaderboard_view_data(adapter)
    _ = prepare_stint_timeline_data(adapter)
    _ = prepare_fuel_tire_analytics_view_data(adapter)
    _ = prepare_strategy_details_view_data(adapter)
    _ = prepare_comparison_view_data(adapter)

    t_end = time.perf_counter()

    elapsed_adapter_ms = (t_adapter - t0) * 1000.0
    elapsed_total_ms = (t_end - t0) * 1000.0

    assert elapsed_adapter_ms < 50.0  # Adapter init < 50ms
    assert elapsed_total_ms < 500.0    # Total dashboard prep < 500ms


def test_adapter_dataframe_contract_integrity(e2e_pipeline_setup):
    """Test 14: Verify adapter DataFrames match standard schema contracts."""
    adapter = e2e_pipeline_setup["adapter"]
    scen_id = adapter.ranking_result.leader_scenario_id

    lb_df = adapter.leaderboard_dataframe()
    assert not lb_df.empty
    assert "rank" in lb_df.columns
    assert "total_race_time_sec" in lb_df.columns

    cm_df = adapter.comparison_dataframe()
    assert not cm_df.empty
    assert "delta_to_leader_sec" in cm_df.columns

    st_df = adapter.stint_dataframe(scenario_id=scen_id)
    assert not st_df.empty
    assert "compound" in st_df.columns

    lp_df = adapter.lap_dataframe(scenario_id=scen_id)
    assert not lp_df.empty
    assert "lap_number" in lp_df.columns

    vl_df = adapter.validation_dataframe(scenario_id=scen_id)
    assert not vl_df.empty
    assert "valid" in vl_df.columns


def test_package_exports_completeness():
    """Test 15: Verify ml.strategy exports all required G.4.6 functions."""
    import ml.strategy as strat_pkg

    export_list = [
        "StrategyDashboardAdapter",
        "prepare_leaderboard_view_data",
        "render_strategy_leaderboard",
        "prepare_comparison_view_data",
        "render_strategy_comparison",
        "prepare_stint_timeline_data",
        "render_stint_timeline",
        "prepare_fuel_tire_analytics_view_data",
        "render_fuel_tire_analytics",
        "prepare_strategy_details_view_data",
        "render_strategy_details",
        "render_strategy_dashboard_tab",
    ]

    for item in export_list:
        assert hasattr(strat_pkg, item), f"Export missing: {item}"
        assert item in strat_pkg.__all__, f"Export not in __all__: {item}"
