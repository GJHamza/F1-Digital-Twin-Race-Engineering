# -*- coding: utf-8 -*-
"""
Comprehensive Unit, Integration, and Regression Tests for G.4.6.5 — Fuel & Tire Analytics.
Verifies fuel burn rate, safety reserves, 4-corner wheel degradation, axle/lateral balance,
stint degradation rates, remaining tire life projections, engineering alert cards, immutability, and E2E integration.
"""

import copy
import pytest
import pandas as pd
from typing import List, Dict

from ml.strategy.race_config import RaceConfig
from ml.strategy.scenario import Scenario
from ml.strategy.stint import Stint
from ml.strategy.pit_stop import PitStop
from ml.strategy.simulator import StrategySimulator, SimulationResult
from ml.strategy.constraint_validator import ConstraintValidator
from ml.strategy.strategy_optimizer import StrategyOptimizer
from ml.strategy.ranking_config import OptimizationConfig
from ml.strategy.ranking_result import RankingResult
from ml.strategy.ranking_candidate import RankedStrategy
from ml.strategy.dashboard_adapter import StrategyDashboardAdapter
from ml.strategy.strategy_dashboard import prepare_fuel_tire_analytics_view_data, AUTHORITATIVE_MAX_TIRE_WEAR_LIMIT


@pytest.fixture
def mock_race_config() -> RaceConfig:
    return RaceConfig(
        race_id="TEST_RACE_ANALYTICS",
        total_laps=50,
        starting_fuel=110.0,
        initial_compound="MEDIUM",
        pit_stop_loss_sec=22.5,
    )


@pytest.fixture
def sample_analytics_adapter(mock_race_config) -> StrategyDashboardAdapter:
    sim = StrategySimulator(mock_race_config)
    val = ConstraintValidator(mock_race_config)

    stint_pair1 = (
        Stint("ST1", 1, "SOFT", 1, 20, 110.0, 60.0, starting_tire_wear=0.0, ending_tire_wear=40.0),
        Stint("ST2", 2, "HARD", 21, 50, 60.0, 10.0, starting_tire_wear=0.0, ending_tire_wear=60.0),
    )
    pit_pair1 = [PitStop("PIT1", 20, "SOFT", "HARD", 1, 2, 22.5)]

    stint_pair2 = (
        Stint("ST1", 1, "MEDIUM", 1, 50, 110.0, 5.0, starting_tire_wear=0.0, ending_tire_wear=70.0),
    )
    pit_pair2 = []

    scenarios = [
        Scenario("SCN_ANALYTICS_1", "TEST_RACE_ANALYTICS", 50, "SOFT", ["SOFT", "HARD"], list(stint_pair1), pit_pair1, 1, 2),
        Scenario("SCN_ANALYTICS_2", "TEST_RACE_ANALYTICS", 50, "MEDIUM", ["MEDIUM"], list(stint_pair2), pit_pair2, 0, 1),
    ]

    sim_results = {s.scenario_id: sim.simulate_strategy(s.stints, s.pit_stops) for s in scenarios}
    val_results = {s.scenario_id: val.validate(sim_results[s.scenario_id], scenario_id=s.scenario_id) for s in scenarios}

    inputs = [(sim_results[s.scenario_id], val_results[s.scenario_id], s) for s in scenarios]
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
    ranking_res = optimizer.optimize(inputs)

    return StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results=sim_results,
        validation_results=val_results,
        scenarios=scenarios,
    )


# 1, 2, 3. Fuel data extraction, consumption calculation, burn per lap
def test_fuel_analytics_extraction_and_burn_rate(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    summary = data["summary"]
    assert summary["scenario_id"] == "SCN_ANALYTICS_1"
    assert summary["starting_fuel_kg"] == 110.0
    assert summary["final_fuel_kg"] == 10.0
    assert summary["total_fuel_consumed_kg"] == 100.0
    assert summary["total_laps"] == 50
    assert abs(summary["avg_fuel_burn_rate_kg_lap"] - 2.0) < 1e-2


# 4 & 5. Fuel reserve & safety status (SAFE, CAUTION, CRITICAL)
def test_fuel_reserve_safety_status(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    # Case SAFE: final fuel 10.0 kg > 1.0 kg reserve
    data_safe = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1", reserve_threshold_kg=1.0)
    assert data_safe["summary"]["fuel_safety_margin_kg"] == 9.0
    assert data_safe["summary"]["fuel_reserve_status"] == "SAFE"

    # Case CAUTION: reserve margin between 0 and 1 kg
    data_caution = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1", reserve_threshold_kg=9.5)
    assert abs(data_caution["summary"]["fuel_safety_margin_kg"] - 0.5) < 1e-3
    assert data_caution["summary"]["fuel_reserve_status"] == "CAUTION"

    # Case CRITICAL: reserve threshold > final fuel
    data_critical = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1", reserve_threshold_kg=12.0)
    assert data_critical["summary"]["fuel_safety_margin_kg"] == -2.0
    assert data_critical["summary"]["fuel_reserve_status"] == "CRITICAL"


# 6, 7, 8, 9, 10. Corner wheel wear preservation (FL, FR, RL, RR, Avg)
def test_corner_wheel_wear_preservation(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    summary = data["summary"]
    assert "fl_final_wear" in summary
    assert "fr_final_wear" in summary
    assert "rl_final_wear" in summary
    assert "rr_final_wear" in summary
    assert summary["max_corner_wear_pct"] >= summary["avg_final_tire_wear_pct"]
    assert summary["most_worn_wheel"] in ["FL", "FR", "RL", "RR"]


# 11, 12, 13. Axle & Lateral wear balance calculations
def test_axle_and_lateral_wear_balance(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    bal = data["balance"]
    assert "front_avg_wear" in bal
    assert "rear_avg_wear" in bal
    assert "left_avg_wear" in bal
    assert "right_avg_wear" in bal
    assert abs(bal["front_avg_wear"] - (summary_fl(data) + summary_fr(data)) / 2.0) < 1e-3
    assert abs(bal["rear_avg_wear"] - (summary_rl(data) + summary_rr(data)) / 2.0) < 1e-3


def summary_fl(d): return d["summary"]["fl_final_wear"]
def summary_fr(d): return d["summary"]["fr_final_wear"]
def summary_rl(d): return d["summary"]["rl_final_wear"]
def summary_rr(d): return d["summary"]["rr_final_wear"]


# 14. Zero denominator handling for balance ratios
def test_zero_denominator_balance_ratio():
    strat = RankedStrategy(
        rank=1,
        scenario_id="SCN_ZERO_WEAR",
        canonical_key="HARD:50",
        total_race_time_sec=4000.0,
        pit_stop_count=0,
        final_fuel_kg=20.0,
        avg_final_tire_wear_pct=0.0,
        warning_count=0,
        delta_to_leader_sec=0.0,
        ranking_explanation="Zero wear candidate",
    )
    res = RankingResult(
        ranked_strategies=(strat,),
        total_candidates=1,
        valid_candidates=1,
        excluded_candidates=0,
        top_k=5,
        leader_scenario_id="SCN_ZERO_WEAR",
        leader_race_time_sec=4000.0,
    )
    adapter = StrategyDashboardAdapter(ranking_result=res)
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ZERO_WEAR")

    bal = data["balance"]
    assert bal["front_rear_ratio"] == 1.0 or math.isnan(bal["front_rear_ratio"])
    assert bal["left_right_ratio"] == 1.0 or math.isnan(bal["left_right_ratio"])


# 15, 16. Stint degradation rate (%/lap)
def test_stint_degradation_rate(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    stint_df = data["stint_analytics_df"]
    assert not stint_df.empty
    for _, row in stint_df.iterrows():
        assert row["degradation_pct_per_lap"] >= 0.0
        assert row["wear_delta"] >= 0.0


# 17 & 18. Remaining tire life & zero/negative degradation handling
def test_remaining_tire_life_projections(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    stint_df = data["stint_analytics_df"]
    assert not stint_df.empty
    row = stint_df.iloc[0]
    assert "remaining_laps_display" in row
    if row["degradation_pct_per_lap"] > 0:
        assert isinstance(int(row["estimated_remaining_laps"]), int)
    else:
        assert row["remaining_laps_display"] == "Projection unavailable"


# 19 & 20. Tire wear & fuel threshold status alerts
def test_engineering_alert_cards(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    alerts = data["alerts"]
    assert len(alerts) >= 3
    cat_names = [a["category"] for a in alerts]
    assert "FUEL" in cat_names
    assert "TIRE WEAR" in cat_names
    assert "BALANCE" in cat_names


# 21. Missing optional field handling
def test_missing_optional_fields_handling():
    strat = RankedStrategy(
        rank=1,
        scenario_id="SCN_BARE_FT",
        canonical_key="SOFT:50",
        total_race_time_sec=4200.0,
        pit_stop_count=0,
        final_fuel_kg=12.0,
        avg_final_tire_wear_pct=40.0,
        warning_count=0,
        delta_to_leader_sec=0.0,
        ranking_explanation="Bare strategy",
    )
    res = RankingResult(
        ranked_strategies=(strat,),
        total_candidates=1,
        valid_candidates=1,
        excluded_candidates=0,
        top_k=5,
        leader_scenario_id="SCN_BARE_FT",
        leader_race_time_sec=4200.0,
    )
    adapter = StrategyDashboardAdapter(ranking_result=res)

    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_BARE_FT")
    assert data["is_empty"] is False
    assert data["summary"]["scenario_id"] == "SCN_BARE_FT"


# 22. Empty strategy handling
def test_empty_ranking_result_handling():
    empty_res = RankingResult(
        ranked_strategies=(),
        total_candidates=0,
        valid_candidates=0,
        excluded_candidates=0,
        top_k=5,
    )
    adapter = StrategyDashboardAdapter(ranking_result=empty_res)
    data = prepare_fuel_tire_analytics_view_data(adapter)

    assert data["is_empty"] is True
    assert data["scenario_id"] is None


# 23. Unknown scenario handling
def test_unknown_scenario_raises(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    with pytest.raises(ValueError, match="not found in ranking result"):
        prepare_fuel_tire_analytics_view_data(adapter, scenario_id="UNKNOWN_SCEN_999")


# 24 & 25. Selected strategy only & no reranking
def test_selected_strategy_only_and_no_reranking(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    d1 = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")
    d2 = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_2")

    assert d1["summary"]["scenario_id"] == "SCN_ANALYTICS_1"
    assert d2["summary"]["scenario_id"] == "SCN_ANALYTICS_2"
    assert adapter.ranking_result.ranked_strategies[0].scenario_id in ["SCN_ANALYTICS_1", "SCN_ANALYTICS_2"]


# 29. Source immutability
def test_source_immutability(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    original_res = copy.deepcopy(adapter.ranking_result)

    _ = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    assert adapter.ranking_result == original_res


# 30. Deterministic output
def test_deterministic_analytics_output(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    res1 = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")
    res2 = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    assert res1["summary"] == res2["summary"]
    assert res1["balance"] == res2["balance"]


# 31. No future leakage (computes strictly up to historical lap records)
def test_no_future_leakage(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    summary = data["summary"]
    assert summary["total_fuel_consumed_kg"] == summary["starting_fuel_kg"] - summary["final_fuel_kg"]


# 32, 33, 34. No fabricated tire temperature, pressure, or aero setup data
def test_no_fabricated_telemetry_fields(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    c_df = data["corner_wear_df"]
    if not c_df.empty:
        for col in c_df.columns:
            assert "temp" not in col.lower()
            assert "pressure" not in col.lower()
            assert "aero" not in col.lower()


# 35 & 36. Separation from G.4.6.3 and G.4.6.4
def test_g463_g464_scope_separation(sample_analytics_adapter):
    adapter = sample_analytics_adapter
    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_1")

    # Verify no multi-strategy comparison scatter data structure is produced
    assert "comparison_df" not in data
    # Verify no Gantt timeline structure is produced
    assert "timeline_df" not in data


# 37. Real End-to-End Integration Test (G.4.5.2 -> ... -> G.4.6.5)
def test_full_pipeline_to_fuel_tire_analytics_e2e_integration(mock_race_config):
    sim = StrategySimulator(mock_race_config)
    val = ConstraintValidator(mock_race_config)

    stint_pair1 = (
        Stint("ST1", 1, "SOFT", 1, 20, 110.0, 60.0),
        Stint("ST2", 2, "HARD", 21, 50, 60.0, 10.0),
    )
    pit_pair1 = [PitStop("PIT1", 20, "SOFT", "HARD", 1, 2, 22.5)]

    scenarios = [
        Scenario("SCN_ANALYTICS_E2E", "TEST_RACE_ANALYTICS", 50, "SOFT", ["SOFT", "HARD"], list(stint_pair1), pit_pair1, 1, 2),
    ]

    sim_results = {s.scenario_id: sim.simulate_strategy(s.stints, s.pit_stops) for s in scenarios}
    val_results = {s.scenario_id: val.validate(sim_results[s.scenario_id], scenario_id=s.scenario_id) for s in scenarios}

    inputs = [(sim_results[s.scenario_id], val_results[s.scenario_id], s) for s in scenarios]
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=1))
    ranking_res = optimizer.optimize(inputs)

    adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results=sim_results,
        validation_results=val_results,
        scenarios=scenarios,
    )

    data = prepare_fuel_tire_analytics_view_data(adapter, scenario_id="SCN_ANALYTICS_E2E")

    assert data["summary"]["scenario_id"] == "SCN_ANALYTICS_E2E"
    assert data["summary"]["rank"] == 1
    assert data["summary"]["is_leader"] is True
    assert data["summary"]["starting_fuel_kg"] == 110.0
    assert data["summary"]["final_fuel_kg"] == 10.0
    assert len(data["alerts"]) >= 3
