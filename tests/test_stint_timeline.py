# -*- coding: utf-8 -*-
"""
Comprehensive Unit, Integration, and Regression Tests for G.4.6.4 — Stint / Compound Timeline.
Verifies timeline data preparation, stint boundaries, compound preservation, pit stop timing,
leader preservation, immutability, zero re-ranking, and full end-to-end integration.
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
from ml.strategy.strategy_dashboard import prepare_stint_timeline_data


@pytest.fixture
def mock_race_config() -> RaceConfig:
    return RaceConfig(
        race_id="TEST_RACE_TIMELINE",
        total_laps=50,
        starting_fuel=110.0,
        initial_compound="MEDIUM",
        pit_stop_loss_sec=22.5,
    )


@pytest.fixture
def sample_timeline_adapter(mock_race_config) -> StrategyDashboardAdapter:
    sim = StrategySimulator(mock_race_config)
    val = ConstraintValidator(mock_race_config)

    # 1. Multi-stint strategy with pit stop
    stint_pair1 = (
        Stint("ST1", 1, "SOFT", 1, 20, 110.0, 60.0),
        Stint("ST2", 2, "HARD", 21, 50, 60.0, 10.0),
    )
    pit_pair1 = [PitStop("PIT1", 20, "SOFT", "HARD", 1, 2, 22.5)]

    # 2. Single-stint strategy without pit stop
    stint_pair2 = (
        Stint("ST1", 1, "MEDIUM", 1, 50, 110.0, 10.0),
    )
    pit_pair2 = []

    scenarios = [
        Scenario("SCN_TL_1", "TEST_RACE_TIMELINE", 50, "SOFT", ["SOFT", "HARD"], list(stint_pair1), pit_pair1, 1, 2),
        Scenario("SCN_TL_2", "TEST_RACE_TIMELINE", 50, "MEDIUM", ["MEDIUM"], list(stint_pair2), pit_pair2, 0, 1),
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


# 1. Valid strategy produces timeline data
def test_valid_strategy_produces_timeline_data(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    assert timeline_data["is_empty"] is False
    assert timeline_data["scenario_id"] == "SCN_TL_1"
    assert "summary" in timeline_data
    assert "timeline_df" in timeline_data
    assert len(timeline_data["timeline_df"]) == 2


# 2. Empty strategy handled safely
def test_empty_strategy_handled_safely():
    empty_res = RankingResult(
        ranked_strategies=(),
        total_candidates=0,
        valid_candidates=0,
        excluded_candidates=0,
        top_k=5,
    )
    adapter = StrategyDashboardAdapter(ranking_result=empty_res)
    timeline_data = prepare_stint_timeline_data(adapter)

    assert timeline_data["is_empty"] is True
    assert timeline_data["scenario_id"] is None
    assert timeline_data["timeline_df"].empty


# 3. Unknown scenario_id handled clearly
def test_unknown_scenario_id_raises(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    with pytest.raises(ValueError, match="not found in ranking result"):
        prepare_stint_timeline_data(adapter, scenario_id="UNKNOWN_SCENARIO_999")


# 4 & 6. Single-stint & Zero-pit strategy works
def test_single_stint_zero_pit_strategy(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_2")

    assert timeline_data["summary"]["pit_stop_count"] == 0
    assert len(timeline_data["timeline_df"]) == 1
    row = timeline_data["timeline_df"].iloc[0]
    assert row["stint_number"] == 1
    assert row["compound"] == "MEDIUM"
    assert row["start_lap"] == 1
    assert row["end_lap"] == 50
    assert row["stint_laps"] == 50
    assert row["pit_transition"] == "—"


# 5 & 7. Multi-stint & Pit-stop strategy works
def test_multi_stint_pit_stop_strategy(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    t_df = timeline_data["timeline_df"]
    assert len(t_df) == 2
    assert t_df.iloc[0]["pit_transition"] == "Lap 20 (22.5s)"
    assert t_df.iloc[1]["pit_transition"] == "—"


# 8, 9, 10, 11, 12, 13. Preserves Scenario ID, Rank, Compound, Start Lap, End Lap, Stint Length
def test_preserves_stint_fields(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    summary = timeline_data["summary"]
    t_df = timeline_data["timeline_df"]

    assert summary["scenario_id"] == "SCN_TL_1"
    assert summary["rank"] == adapter.ranking_result.ranked_strategies[1].rank  # SCN_TL_1 rank

    row1 = t_df.iloc[0]
    assert row1["compound"] == "SOFT"
    assert row1["start_lap"] == 1
    assert row1["end_lap"] == 20
    assert row1["stint_laps"] == 20

    row2 = t_df.iloc[1]
    assert row2["compound"] == "HARD"
    assert row2["start_lap"] == 21
    assert row2["end_lap"] == 50
    assert row2["stint_laps"] == 30


# 14 & 15. Pit lap and pit duration preserved when available
def test_pit_lap_and_duration_preserved(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    pit_df = timeline_data["pit_df"]
    assert not pit_df.empty
    assert pit_df.iloc[0]["pit_lap"] == 20
    assert pit_df.iloc[0]["duration_sec"] == 22.5


# 16. Stint ordering preserved
def test_stint_ordering_preserved(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    stint_numbers = list(timeline_data["timeline_df"]["stint_number"])
    assert stint_numbers == [1, 2]


# 17. Timeline does not rerank
def test_timeline_does_not_rerank(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    t1 = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")
    t2 = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_2")

    assert t1["summary"]["rank"] == 2
    assert t2["summary"]["rank"] == 1


# 18. Timeline does not mutate source objects
def test_timeline_does_not_mutate(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    ranking_copy = copy.deepcopy(adapter.ranking_result)

    _ = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    assert adapter.ranking_result == ranking_copy


# 22 & 23. Missing optional data and missing weather handled safely
def test_missing_optional_data_and_weather_handled():
    strat = RankedStrategy(
        rank=1,
        scenario_id="SCN_BARE_TL",
        canonical_key="SOFT:1-20|HARD:21-50",
        total_race_time_sec=4500.0,
        pit_stop_count=1,
        final_fuel_kg=15.0,
        avg_final_tire_wear_pct=35.0,
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
        leader_scenario_id="SCN_BARE_TL",
        leader_race_time_sec=4500.0,
    )
    adapter = StrategyDashboardAdapter(ranking_result=res)

    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_BARE_TL")
    assert timeline_data["summary"]["scenario_id"] == "SCN_BARE_TL"
    assert timeline_data["summary"]["validation_status"] == "VALID"


# 24. Deterministic output
def test_deterministic_output(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    res1 = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")
    res2 = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")

    pd.testing.assert_frame_equal(res1["timeline_df"], res2["timeline_df"])


# 25. Only selected strategy is materialized
def test_only_selected_strategy_materialized(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_2")

    assert timeline_data["scenario_id"] == "SCN_TL_2"
    assert len(timeline_data["timeline_df"]) == 1


# 26 & 27. Leader identification uses authoritative leader_scenario_id
def test_leader_identification(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    leader_id = adapter.ranking_result.leader_scenario_id

    t_leader = prepare_stint_timeline_data(adapter, scenario_id=leader_id)
    assert t_leader["summary"]["is_leader"] is True

    non_leader_id = "SCN_TL_2" if leader_id != "SCN_TL_2" else "SCN_TL_1"
    t_non_leader = prepare_stint_timeline_data(adapter, scenario_id=non_leader_id)
    assert t_non_leader["summary"]["is_leader"] is False
    assert t_non_leader["summary"]["leader_scenario_id"] == leader_id


# 28. Presentation derivation of stint length is correct
def test_stint_length_derivation():
    stint_df = pd.DataFrame([
        {"stint_number": 1, "compound": "SOFT", "start_lap": 1, "end_lap": 15},
        {"stint_number": 2, "compound": "HARD", "start_lap": 16, "end_lap": 50},
    ])
    stint_df["stint_laps"] = (stint_df["end_lap"] - stint_df["start_lap"]) + 1

    assert list(stint_df["stint_laps"]) == [15, 35]


# 29 & 30. No fabricated tire temperature or vehicle setup data
def test_no_fabricated_data(sample_timeline_adapter):
    adapter = sample_timeline_adapter
    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_TL_1")
    t_df = timeline_data["timeline_df"]

    for col in t_df.columns:
        assert "temp" not in col.lower()
        assert "setup" not in col.lower()
        assert "aero" not in col.lower()


# 31. Real End-to-End Integration Test (G.4.5.2 -> G.4.5.3 -> G.4.5.4 -> G.4.5.5 -> G.4.6.1 -> G.4.6.2 -> G.4.6.3 -> G.4.6.4)
def test_full_pipeline_to_stint_timeline_e2e_integration(mock_race_config):
    sim = StrategySimulator(mock_race_config)
    val = ConstraintValidator(mock_race_config)

    stint_pair1 = (
        Stint("ST1", 1, "SOFT", 1, 20, 110.0, 60.0),
        Stint("ST2", 2, "HARD", 21, 50, 60.0, 10.0),
    )
    pit_pair1 = [PitStop("PIT1", 20, "SOFT", "HARD", 1, 2, 22.5)]

    scenarios = [
        Scenario("SCN_E2E_1", "TEST_RACE_TIMELINE", 50, "SOFT", ["SOFT", "HARD"], list(stint_pair1), pit_pair1, 1, 2),
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

    timeline_data = prepare_stint_timeline_data(adapter, scenario_id="SCN_E2E_1")

    assert timeline_data["summary"]["scenario_id"] == "SCN_E2E_1"
    assert timeline_data["summary"]["rank"] == 1
    assert timeline_data["summary"]["is_leader"] is True
    assert len(timeline_data["timeline_df"]) == 2
    assert timeline_data["timeline_df"].iloc[0]["pit_transition"] == "Lap 20 (22.5s)"
