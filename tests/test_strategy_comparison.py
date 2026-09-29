# -*- coding: utf-8 -*-
"""
Comprehensive Unit, Integration, and Regression Tests for G.4.6.3 — Strategy Comparison / Trade-off Analysis.
Verifies data extraction, UI preparation, leader preservation, max selection bounds, no re-ranking, and immutability.
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
from ml.strategy.strategy_dashboard import (
    prepare_comparison_view_data,
    MAX_DEFAULT_COMPARISON_COUNT,
)


@pytest.fixture
def mock_race_config() -> RaceConfig:
    return RaceConfig(
        race_id="TEST_RACE_COMP",
        total_laps=10,
        starting_fuel=100.0,
        initial_compound="MEDIUM",
        pit_stop_loss_sec=20.0,
    )


@pytest.fixture
def sample_ranking_and_adapter(mock_race_config) -> StrategyDashboardAdapter:
    """Constructs 5 sample ranked strategies and adapter."""
    sim = StrategySimulator(mock_race_config)
    val = ConstraintValidator(mock_race_config)

    stint_pair1 = (Stint("ST1", 1, "SOFT", 1, 5, 100.0, 50.0), Stint("ST2", 2, "HARD", 6, 10, 50.0, 10.0))
    pit_pair1 = [PitStop("PIT1", 5, "SOFT", "HARD", 1, 2, 20.0)]

    stint_pair2 = (Stint("ST1", 1, "MEDIUM", 1, 5, 100.0, 50.0), Stint("ST2", 2, "HARD", 6, 10, 50.0, 10.0))
    pit_pair2 = [PitStop("PIT1", 5, "MEDIUM", "HARD", 1, 2, 20.0)]

    stint_pair3 = (Stint("ST1", 1, "HARD", 1, 5, 100.0, 50.0), Stint("ST2", 2, "SOFT", 6, 10, 50.0, 10.0))
    pit_pair3 = [PitStop("PIT1", 5, "HARD", "SOFT", 1, 2, 20.0)]

    stint_pair4 = (Stint("ST1", 1, "SOFT", 1, 4, 100.0, 60.0), Stint("ST2", 2, "MEDIUM", 5, 10, 60.0, 10.0))
    pit_pair4 = [PitStop("PIT1", 4, "SOFT", "MEDIUM", 1, 2, 20.0)]

    stint_pair5 = (Stint("ST1", 1, "MEDIUM", 1, 4, 100.0, 60.0), Stint("ST2", 2, "SOFT", 5, 10, 60.0, 10.0))
    pit_pair5 = [PitStop("PIT1", 4, "MEDIUM", "SOFT", 1, 2, 20.0)]

    scenarios = [
        Scenario("SCN_COMP_1", "TEST_RACE_COMP", 10, "SOFT", ["SOFT", "HARD"], list(stint_pair1), pit_pair1, 1, 2),
        Scenario("SCN_COMP_2", "TEST_RACE_COMP", 10, "MEDIUM", ["MEDIUM", "HARD"], list(stint_pair2), pit_pair2, 1, 2),
        Scenario("SCN_COMP_3", "TEST_RACE_COMP", 10, "HARD", ["HARD", "SOFT"], list(stint_pair3), pit_pair3, 1, 2),
        Scenario("SCN_COMP_4", "TEST_RACE_COMP", 10, "SOFT", ["SOFT", "MEDIUM"], list(stint_pair4), pit_pair4, 1, 2),
        Scenario("SCN_COMP_5", "TEST_RACE_COMP", 10, "MEDIUM", ["MEDIUM", "SOFT"], list(stint_pair5), pit_pair5, 1, 2),
    ]

    sim_results = {scen.scenario_id: sim.simulate_strategy(scen.stints, scen.pit_stops) for scen in scenarios}
    val_results = {scen.scenario_id: val.validate(sim_results[scen.scenario_id], scenario_id=scen.scenario_id) for scen in scenarios}

    inputs = [(sim_results[s.scenario_id], val_results[s.scenario_id], s) for s in scenarios]
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=5))
    ranking_res = optimizer.optimize(inputs)

    return StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results=sim_results,
        validation_results=val_results,
        scenarios=scenarios,
    )


# 1. Comparison accepts valid scenario IDs
def test_comparison_accepts_valid_scenario_ids(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    selected = ["SCN_COMP_1", "SCN_COMP_2"]
    comp_data = prepare_comparison_view_data(adapter, scenario_ids=selected)

    assert comp_data["selected_scenario_ids"] == selected
    df = comp_data["comparison_df"]
    assert len(df) == 2
    assert list(df["scenario_id"]) == selected


# 2. Unknown scenario ID handled clearly
def test_unknown_scenario_id_raises(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    with pytest.raises(ValueError, match="not found in ranking result"):
        prepare_comparison_view_data(adapter, scenario_ids=["INVALID_SCN_999"])


# 3. Leader is preserved
def test_leader_preserved_in_comparison(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    leader_id = adapter.ranking_result.leader_scenario_id
    comp_data = prepare_comparison_view_data(adapter, scenario_ids=[leader_id])

    assert comp_data["leader_scenario_id"] == leader_id
    assert comp_data["leader_included"] is True


# 4 - 10. Metric fields preservation (rank, race time, delta, pit stops, fuel, tire wear, warnings)
def test_metric_fields_preservation(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    comp_data = prepare_comparison_view_data(adapter)
    df = comp_data["comparison_df"]

    expected_ranked = adapter.ranking_result.ranked_strategies[:MAX_DEFAULT_COMPARISON_COUNT]
    for idx, strat in enumerate(expected_ranked):
        row = df.iloc[idx]
        assert row["rank"] == strat.rank
        assert row["scenario_id"] == strat.scenario_id
        assert abs(row["total_race_time_sec"] - strat.total_race_time_sec) < 1e-3
        assert abs(row["delta_to_leader_sec"] - strat.delta_to_leader_sec) < 1e-3
        assert row["pit_stop_count"] == strat.pit_stop_count
        assert abs(row["final_fuel_kg"] - strat.final_fuel_kg) < 1e-3
        assert abs(row["avg_final_tire_wear_pct"] - strat.avg_final_tire_wear_pct) < 1e-2
        assert row["warning_count"] == strat.warning_count


# 11 & 12. Comparison does not rerank or calculate new score
def test_no_reranking_or_new_scoring(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    comp_data = prepare_comparison_view_data(adapter)
    df = comp_data["comparison_df"]

    # Check rank column is strictly ascending
    ranks = list(df["rank"])
    assert ranks == sorted(ranks)


# 13 & 14. Immutability tests
def test_comparison_does_not_mutate_upstream(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    ranking_copy = copy.deepcopy(adapter.ranking_result)

    _ = prepare_comparison_view_data(adapter, scenario_ids=["SCN_COMP_1", "SCN_COMP_2"])

    assert adapter.ranking_result == ranking_copy
    for original_strat, copied_strat in zip(adapter.ranking_result.ranked_strategies, ranking_copy.ranked_strategies):
        assert original_strat == copied_strat


# 15. Maximum comparison count enforced (capped at 4)
def test_max_comparison_count_enforced(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    all_5_ids = [s.scenario_id for s in adapter.ranking_result.ranked_strategies]

    comp_data = prepare_comparison_view_data(adapter, scenario_ids=all_5_ids, max_compare=4)

    assert len(comp_data["selected_scenario_ids"]) == 4
    assert len(comp_data["comparison_df"]) == 4


# 16. Duplicate scenario IDs handled safely
def test_duplicate_scenario_ids_deduplicated(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    dups = ["SCN_COMP_1", "SCN_COMP_1", "SCN_COMP_2", "SCN_COMP_1"]

    comp_data = prepare_comparison_view_data(adapter, scenario_ids=dups)

    assert comp_data["selected_scenario_ids"] == ["SCN_COMP_1", "SCN_COMP_2"]
    assert len(comp_data["comparison_df"]) == 2


# 17. Empty comparison handled
def test_empty_ranking_result_comparison():
    empty_res = RankingResult(
        ranked_strategies=(),
        top_k=5,
        total_candidates=0,
        valid_candidates=0,
        excluded_candidates=0,
    )
    adapter = StrategyDashboardAdapter(ranking_result=empty_res)

    comp_data = prepare_comparison_view_data(adapter)
    assert comp_data["comparison_df"].empty
    assert comp_data["stint_df_map"] == {}
    assert comp_data["leader_scenario_id"] is None
    assert comp_data["leader_included"] is False


# 18. Single-strategy comparison handled
def test_single_strategy_comparison(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    comp_data = prepare_comparison_view_data(adapter, scenario_ids=["SCN_COMP_1"])

    assert len(comp_data["comparison_df"]) == 1
    assert comp_data["selected_scenario_ids"] == ["SCN_COMP_1"]


# 19 & 20. Missing optional stint and lap telemetry handled safely
def test_missing_optional_telemetry_handled():
    strat = RankedStrategy(
        rank=1,
        scenario_id="SCN_BARE",
        canonical_key="HARD:10",
        total_race_time_sec=1000.0,
        pit_stop_count=0,
        final_fuel_kg=20.0,
        avg_final_tire_wear_pct=30.0,
        warning_count=0,
        delta_to_leader_sec=0.0,
        ranking_explanation="Bare strategy",
    )
    res = RankingResult(
        ranked_strategies=(strat,),
        top_k=5,
        total_candidates=1,
        valid_candidates=1,
        excluded_candidates=0,
        leader_scenario_id="SCN_BARE",
        leader_race_time_sec=1000.0,
    )
    adapter = StrategyDashboardAdapter(ranking_result=res)

    comp_data = prepare_comparison_view_data(adapter, scenario_ids=["SCN_BARE"])
    assert len(comp_data["comparison_df"]) == 1
    assert comp_data["stint_df_map"]["SCN_BARE"].empty
    assert comp_data["lap_df_map"]["SCN_BARE"].empty


# 21, 22, 23. Real lap & stint data present without fabricated tire temperatures
def test_lap_telemetry_fields_and_no_temperature(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    comp_data = prepare_comparison_view_data(adapter, scenario_ids=["SCN_COMP_1"])

    lap_df = comp_data["lap_df_map"]["SCN_COMP_1"]
    assert not lap_df.empty
    assert "lap_number" in lap_df.columns
    assert "fuel_kg" in lap_df.columns
    assert "avg_tire_wear" in lap_df.columns

    # Explicit audit check: No fabricated tire temperatures
    for col in lap_df.columns:
        assert "temp" not in col.lower()


# 24. Deterministic comparison output
def test_deterministic_comparison_output(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    res1 = prepare_comparison_view_data(adapter, scenario_ids=["SCN_COMP_1", "SCN_COMP_2"])
    res2 = prepare_comparison_view_data(adapter, scenario_ids=["SCN_COMP_1", "SCN_COMP_2"])

    pd.testing.assert_frame_equal(res1["comparison_df"], res2["comparison_df"])


# 26. Leader exclusion does not create a new leader
def test_leader_exclusion_preserves_authoritative_leader(sample_ranking_and_adapter):
    adapter = sample_ranking_and_adapter
    leader_id = adapter.ranking_result.leader_scenario_id
    non_leaders = [s.scenario_id for s in adapter.ranking_result.ranked_strategies if s.scenario_id != leader_id]

    comp_data = prepare_comparison_view_data(adapter, scenario_ids=non_leaders[:2])

    assert comp_data["leader_scenario_id"] == leader_id
    assert comp_data["leader_included"] is False
    # Verify non-leader selected is rank > 1
    assert comp_data["comparison_df"].iloc[0]["rank"] > 1


# 29. Mandatory No-Reranking Test
def test_mandatory_no_reranking():
    """Verify that custom non-trivial ranked strategies retain exact original ranks in comparison view."""
    strat_a = RankedStrategy(
        rank=1,
        scenario_id="SCN_A",
        canonical_key="SOFT:10",
        total_race_time_sec=1000.0,
        pit_stop_count=1,
        final_fuel_kg=5.0,  # Lower fuel, but rank 1
        avg_final_tire_wear_pct=40.0,
        warning_count=0,
        delta_to_leader_sec=0.0,
        ranking_explanation="Rank 1",
    )
    strat_b = RankedStrategy(
        rank=2,
        scenario_id="SCN_B",
        canonical_key="HARD:10",
        total_race_time_sec=1010.0,
        pit_stop_count=0,
        final_fuel_kg=25.0,  # Higher fuel, but rank 2
        avg_final_tire_wear_pct=15.0,
        warning_count=0,
        delta_to_leader_sec=10.0,
        ranking_explanation="Rank 2",
    )
    res = RankingResult(
        ranked_strategies=(strat_a, strat_b),
        top_k=2,
        total_candidates=2,
        valid_candidates=2,
        excluded_candidates=0,
        leader_scenario_id="SCN_A",
        leader_race_time_sec=1000.0,
    )
    adapter = StrategyDashboardAdapter(ranking_result=res)

    comp_data = prepare_comparison_view_data(adapter, scenario_ids=["SCN_A", "SCN_B"])
    df = comp_data["comparison_df"]

    assert df.iloc[0]["scenario_id"] == "SCN_A"
    assert df.iloc[0]["rank"] == 1
    assert df.iloc[1]["scenario_id"] == "SCN_B"
    assert df.iloc[1]["rank"] == 2


# 30. Mandatory No-Mutation Test
def test_mandatory_no_mutation():
    """Verify that deep-copied RankingResult remains identical after comparison operations."""
    strat = RankedStrategy(
        rank=1,
        scenario_id="SCN_MUTATE_TEST",
        canonical_key="SOFT:10",
        total_race_time_sec=950.0,
        pit_stop_count=0,
        final_fuel_kg=12.0,
        avg_final_tire_wear_pct=22.0,
        warning_count=0,
        delta_to_leader_sec=0.0,
        ranking_explanation="Mutation check",
    )
    res = RankingResult(
        ranked_strategies=(strat,),
        top_k=1,
        total_candidates=1,
        valid_candidates=1,
        excluded_candidates=0,
        leader_scenario_id="SCN_MUTATE_TEST",
        leader_race_time_sec=950.0,
    )
    original_res = copy.deepcopy(res)
    adapter = StrategyDashboardAdapter(ranking_result=res)

    _ = prepare_comparison_view_data(adapter, scenario_ids=["SCN_MUTATE_TEST"])

    assert adapter.ranking_result == original_res


# 31. Full Pipeline Integration Test (G.4.5.2 -> G.4.5.3 -> G.4.5.4 -> G.4.5.5 -> G.4.6.1 -> G.4.6.2 -> G.4.6.3)
def test_full_pipeline_to_comparison_integration(mock_race_config):
    sim = StrategySimulator(mock_race_config)
    val = ConstraintValidator(mock_race_config)

    stint_pair1 = (Stint("ST1", 1, "SOFT", 1, 5, 100.0, 50.0), Stint("ST2", 2, "HARD", 6, 10, 50.0, 10.0))
    pit_pair1 = [PitStop("PIT1", 5, "SOFT", "HARD", 1, 2, 20.0)]
    stint_pair2 = (Stint("ST1", 1, "MEDIUM", 1, 5, 100.0, 50.0), Stint("ST2", 2, "HARD", 6, 10, 50.0, 10.0))
    pit_pair2 = [PitStop("PIT1", 5, "MEDIUM", "HARD", 1, 2, 20.0)]

    scenarios = [
        Scenario("SCN_INT_1", "TEST_RACE_COMP", 10, "SOFT", ["SOFT", "HARD"], list(stint_pair1), pit_pair1, 1, 2),
        Scenario("SCN_INT_2", "TEST_RACE_COMP", 10, "MEDIUM", ["MEDIUM", "HARD"], list(stint_pair2), pit_pair2, 1, 2),
    ]

    sim_results = {s.scenario_id: sim.simulate_strategy(s.stints, s.pit_stops) for s in scenarios}
    val_results = {s.scenario_id: val.validate(sim_results[s.scenario_id], scenario_id=s.scenario_id) for s in scenarios}

    inputs = [(sim_results[s.scenario_id], val_results[s.scenario_id], s) for s in scenarios]
    optimizer = StrategyOptimizer(OptimizationConfig(top_k=2))
    ranking_res = optimizer.optimize(inputs)

    adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results=sim_results,
        validation_results=val_results,
        scenarios=scenarios,
    )

    comp_data = prepare_comparison_view_data(adapter)
    df = comp_data["comparison_df"]

    assert len(df) == 2
    assert comp_data["leader_scenario_id"] == ranking_res.leader_scenario_id
    assert comp_data["leader_included"] is True
    assert not comp_data["lap_df_map"][ranking_res.leader_scenario_id].empty
    assert not comp_data["stint_df_map"][ranking_res.leader_scenario_id].empty
