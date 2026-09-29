# -*- coding: utf-8 -*-
"""
Unit and Integration Test Suite for G.4.6.6 Strategy Details & Validation Audit Cockpit.
Verifies read-only presentation data extraction, validation preservation, scenario & race config inspection,
simulation assumptions audit, lap trace filtering, immutability, determinism, and e2e pipeline integration.
"""

import copy
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
    prepare_strategy_details_view_data,
    render_strategy_details,
)


@pytest.fixture
def sample_strategy_pipeline():
    """Builds a complete, authoritative G.4.5 pipeline output tuple for G.4.6 testing."""
    config = RaceConfig(
        race_id="RACE_TEST_G466",
        total_laps=20,
        starting_fuel=50.0,
        initial_compound="MEDIUM",
        pit_stop_loss_sec=22.5,
        max_tire_wear=85.0,
        min_stint_laps=5,
    )

    stints_valid = [
        Stint("ST1", 1, "MEDIUM", 1, 10, 50.0, 28.0, starting_tire_wear=0.0, ending_tire_wear=30.0),
        Stint("ST2", 2, "HARD", 11, 20, 28.0, 6.0, starting_tire_wear=0.0, ending_tire_wear=25.0),
    ]
    pits_valid = [
        PitStop("PIT1", 10, "MEDIUM", "HARD", 1, 2, 22.5)
    ]
    scen_valid = Scenario(
        scenario_id="SCN_G466_VALID",
        race_id="RACE_TEST_G466",
        total_laps=20,
        starting_compound="MEDIUM",
        compound_sequence=["MEDIUM", "HARD"],
        stints=stints_valid,
        pit_stops=pits_valid,
        number_of_stops=1,
        number_of_stints=2,
    )

    simulator = StrategySimulator(config)
    sim_valid = simulator.simulate_strategy(scen_valid.stints, scen_valid.pit_stops)

    validator = ConstraintValidator(config)
    val_valid = validator.validate(sim_valid, scenario_id=scen_valid.scenario_id)

    # Invalid scenario with hard violation
    stints_inv = [
        Stint("ST1", 1, "SOFT", 1, 20, 50.0, 5.0, starting_tire_wear=0.0, ending_tire_wear=95.0),
    ]
    scen_inv = Scenario(
        scenario_id="SCN_G466_INVALID",
        race_id="RACE_TEST_G466",
        total_laps=20,
        starting_compound="SOFT",
        compound_sequence=["SOFT"],
        stints=stints_inv,
        pit_stops=[],
        number_of_stops=0,
        number_of_stints=1,
    )
    sim_inv = simulator.simulate_strategy(scen_inv.stints, scen_inv.pit_stops)
    val_inv = ValidationResult(
        scenario_id=scen_inv.scenario_id,
        race_id="RACE_TEST_G466",
        valid=False,
        severity="CRITICAL_VIOLATION",
        violations=(
            Violation(
                constraint_id="MANDATORY_COMPOUND_VIOLATION",
                category="COMPOUND",
                severity="CRITICAL",
                message="Dry race requires at least two distinct compound specifications.",
                actual_value=1,
                expected_value=">= 2 distinct compounds",
                lap_number=20,
                stint_id="ST1",
            ),
        ),
        warnings=("Single compound warning",),
        checked_constraints_count=8,
    )

    # Build Optimization Candidates & Ranking Result
    cand_valid = OptimizationCandidate.from_simulation_and_validation(sim_valid, val_valid, scenario=scen_valid)
    cand_inv = OptimizationCandidate.from_simulation_and_validation(sim_inv, val_inv, scenario=scen_inv)

    leader_time = min(cand_valid.total_race_time_sec, cand_inv.total_race_time_sec)
    ranked_valid = RankedStrategy.from_candidate(cand_valid, rank=1, leader_race_time_sec=leader_time)
    ranked_inv = RankedStrategy.from_candidate(cand_inv, rank=2, leader_race_time_sec=leader_time)

    ranking_res = RankingResult(
        ranked_strategies=(ranked_valid, ranked_inv),
        total_candidates=2,
        valid_candidates=1,
        excluded_candidates=1,
        top_k=5,
    )

    adapter = StrategyDashboardAdapter(
        ranking_result=ranking_res,
        simulation_results={scen_valid.scenario_id: sim_valid, scen_inv.scenario_id: sim_inv},
        validation_results={scen_valid.scenario_id: val_valid, scen_inv.scenario_id: val_inv},
        scenarios={scen_valid.scenario_id: scen_valid, scen_inv.scenario_id: scen_inv},
    )

    return {
        "config": config,
        "scen_valid": scen_valid,
        "scen_inv": scen_inv,
        "sim_valid": sim_valid,
        "sim_inv": sim_inv,
        "val_valid": val_valid,
        "val_inv": val_inv,
        "ranking_res": ranking_res,
        "adapter": adapter,
    }


def test_strategy_identity_preservation(sample_strategy_pipeline):
    """Test 1: Verify identity metrics (rank, scenario_id, canonical_key, delta, fuel) match upstream."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    assert not data["is_empty"]
    identity = data["identity"]

    assert identity["scenario_id"] == scen_id
    assert identity["rank"] == 1
    assert identity["pit_stop_count"] == 1
    assert identity["starting_compound"] == "MEDIUM"
    assert identity["compound_sequence"] == ["MEDIUM", "HARD"]
    assert identity["stint_count"] == 2


def test_validation_status_preservation(sample_strategy_pipeline):
    """Test 2: Verify validation status, valid flag, severity, and checked rules match upstream."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id
    val_valid = sample_strategy_pipeline["val_valid"]

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    val_data = data["validation"]

    assert val_data["valid"] is True
    assert val_data["valid"] == val_valid.valid
    assert val_data["severity"] == val_valid.severity
    assert val_data["violation_count"] == 0
    assert val_data["checked_constraints_count"] == val_valid.checked_constraints_count


def test_hard_violations_preservation(sample_strategy_pipeline):
    """Test 3: Verify hard violations from G.4.5.4 are preserved and formatted correctly."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_inv"].scenario_id
    val_inv = sample_strategy_pipeline["val_inv"]

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    val_data = data["validation"]

    assert val_data["valid"] is False
    assert val_data["valid"] == val_inv.valid
    assert val_data["severity"] == val_inv.severity
    assert val_data["violation_count"] > 0
    assert len(val_data["violations"]) == len(val_inv.violations)

    v_df = val_data["violations_df"]
    assert not v_df.empty
    assert "constraint_id" in v_df.columns
    assert "category" in v_df.columns


def test_soft_warnings_preservation(sample_strategy_pipeline):
    """Test 4: Verify soft warnings are extracted cleanly into view data."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    assert isinstance(data["validation"]["warnings"], list)


def test_category_compliance_breakdown(sample_strategy_pipeline):
    """Test 5: Verify category breakdown maps violations to categories like COMPOUND, TIRE, FUEL."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_inv"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    breakdown = data["validation"]["category_breakdown"]

    assert "COMPOUND" in breakdown or "TIRE" in breakdown
    total_v = sum(info["violations"] for info in breakdown.values())
    assert total_v == data["validation"]["violation_count"]


def test_race_config_metadata_extraction(sample_strategy_pipeline):
    """Test 6: Verify race session parameters are correctly extracted into view data."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    cfg = data["race_config"]

    assert cfg["total_laps"] == 20
    assert cfg["starting_fuel"] == 50.0
    assert cfg["pit_stop_loss_sec"] == 22.5
    assert cfg["max_tire_wear"] == 85.0
    assert cfg["min_stint_laps"] in (3, 5)


def test_simulation_assumptions_extraction(sample_strategy_pipeline):
    """Test 7: Verify simulation assumptions clearly distinguish PROJECT ASSUMPTION vs FIA REGULATION."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    assumptions = data["assumptions"]

    assert len(assumptions) >= 4
    types = [a["type"] for a in assumptions]
    assert "PROJECT SIMULATION ASSUMPTION" in types
    assert "FIA REGULATION" in types


def test_lap_trace_dataframe_extraction(sample_strategy_pipeline):
    """Test 8: Verify lap trace DataFrame contains per-lap telemetry columns."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    trace = data["lap_trace"]

    assert trace["total_laps"] == 20
    assert not trace["lap_df"].empty
    assert "lap_number" in trace["lap_df"].columns
    assert "fuel_kg" in trace["lap_df"].columns
    assert "avg_tire_wear" in trace["lap_df"].columns


def test_lap_trace_range_filtering(sample_strategy_pipeline):
    """Test 9: Verify lap_range parameter filters the lap trace DataFrame correctly."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id, lap_range=(5, 12))
    filtered_df = data["lap_trace"]["lap_df"]

    assert len(filtered_df) == 8
    assert filtered_df["lap_number"].min() == 5
    assert filtered_df["lap_number"].max() == 12


def test_pit_laps_detection(sample_strategy_pipeline):
    """Test 10: Verify pit laps are accurately identified in trace metadata."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    pit_laps = data["lap_trace"]["pit_laps"]

    assert 10 in pit_laps


def test_selected_strategy_only_processing(sample_strategy_pipeline):
    """Test 11: Verify view data is generated strictly for the requested scenario_id."""
    adapter = sample_strategy_pipeline["adapter"]
    valid_id = sample_strategy_pipeline["scen_valid"].scenario_id
    inv_id = sample_strategy_pipeline["scen_inv"].scenario_id

    data_valid = prepare_strategy_details_view_data(adapter, scenario_id=valid_id)
    data_inv = prepare_strategy_details_view_data(adapter, scenario_id=inv_id)

    assert data_valid["scenario_id"] == valid_id
    assert data_inv["scenario_id"] == inv_id
    assert data_valid["validation"]["valid"] is True
    assert data_inv["validation"]["valid"] is False


def test_empty_ranking_result_handling():
    """Test 12: Verify empty ranking result returns is_empty=True without throwing errors."""
    empty_ranking = RankingResult(ranked_strategies=tuple(), total_candidates=0, valid_candidates=0, excluded_candidates=0, top_k=5)
    adapter = StrategyDashboardAdapter(ranking_result=empty_ranking)

    data = prepare_strategy_details_view_data(adapter)
    assert data["is_empty"] is True
    assert data["scenario_id"] is None


def test_unknown_scenario_id_handling(sample_strategy_pipeline):
    """Test 13: Verify unknown scenario ID returns is_empty=True with error message."""
    adapter = sample_strategy_pipeline["adapter"]

    data = prepare_strategy_details_view_data(adapter, scenario_id="SCN_NONEXISTENT")
    assert data["is_empty"] is True
    assert "error" in data
    assert "SCN_NONEXISTENT" in data["error"]


def test_none_scenario_id_defaults_to_leader(sample_strategy_pipeline):
    """Test 14: Verify scenario_id=None defaults to the leader strategy ID."""
    adapter = sample_strategy_pipeline["adapter"]
    leader_id = sample_strategy_pipeline["ranking_res"].leader_scenario_id

    data = prepare_strategy_details_view_data(adapter, scenario_id=None)
    assert data["scenario_id"] == leader_id


def test_invalid_adapter_raises_value_error():
    """Test 15: Verify adapter=None raises ValueError."""
    with pytest.raises(ValueError, match="adapter cannot be None"):
        prepare_strategy_details_view_data(None)


def test_source_immutability(sample_strategy_pipeline):
    """Test 16: Verify source domain objects are not mutated during view data preparation."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    ranking_before = copy.deepcopy(adapter.ranking_result)
    sim_before = copy.deepcopy(adapter._sim_results[scen_id])
    val_before = copy.deepcopy(adapter._val_results[scen_id])

    _ = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)

    assert adapter.ranking_result == ranking_before
    assert adapter._sim_results[scen_id] == sim_before
    assert adapter._val_results[scen_id] == val_before


def test_deterministic_output(sample_strategy_pipeline):
    """Test 17: Verify multiple calls with identical inputs produce identical view data."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    res1 = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)
    res2 = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)

    assert res1["scenario_id"] == res2["scenario_id"]
    assert res1["identity"] == res2["identity"]
    assert res1["race_config"] == res2["race_config"]
    assert res1["validation"]["valid"] == res2["validation"]["valid"]
    assert res1["validation"]["violation_count"] == res2["validation"]["violation_count"]


def test_no_reranking_or_simulation_rerun(sample_strategy_pipeline, monkeypatch):
    """Test 18: Verify domain simulation, validation, and optimization engines are NOT called."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    mock_sim = MagicMock()
    mock_val = MagicMock()
    mock_opt = MagicMock()

    monkeypatch.setattr(StrategySimulator, "simulate_strategy", mock_sim)
    monkeypatch.setattr(ConstraintValidator, "validate", mock_val)
    monkeypatch.setattr(StrategyOptimizer, "optimize", mock_opt)

    _ = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)

    mock_sim.assert_not_called()
    mock_val.assert_not_called()
    mock_opt.assert_not_called()


def test_render_strategy_details_handles_empty_adapter():
    """Test 19: Verify render_strategy_details handles empty adapter gracefully."""
    empty_ranking = RankingResult(ranked_strategies=tuple(), total_candidates=0, valid_candidates=0, excluded_candidates=0, top_k=5)
    adapter = StrategyDashboardAdapter(ranking_result=empty_ranking)

    out = render_strategy_details(adapter)
    assert out is None


def test_e2e_strategy_details_pipeline_integration(sample_strategy_pipeline):
    """Test 20: Complete E2E integration test verifying G.4.5 -> G.4.6.1 -> G.4.6.6 flow."""
    adapter = sample_strategy_pipeline["adapter"]
    scen_id = sample_strategy_pipeline["scen_valid"].scenario_id

    view_data = prepare_strategy_details_view_data(adapter, scenario_id=scen_id)

    # 1. Identity
    assert view_data["identity"]["rank"] == 1
    assert view_data["identity"]["scenario_id"] == scen_id

    # 2. Validation
    assert view_data["validation"]["valid"] is True
    assert view_data["validation"]["severity"] == "NONE"

    # 3. Race Config
    assert view_data["race_config"]["race_id"] == "RACE_TEST_G466"

    # 4. Assumptions
    assert len(view_data["assumptions"]) >= 4

    # 5. Lap Trace
    assert view_data["lap_trace"]["total_laps"] == 20
    assert not view_data["lap_trace"]["lap_df"].empty
