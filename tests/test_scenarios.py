# -*- coding: utf-8 -*-
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from data_generator.scenarios import get_scenario, list_scenarios, SCENARIO_REGISTRY

def test_scenario_registry_contains_15_scenarios():
    scenarios = list_scenarios()
    assert len(scenarios) == 15
    expected_list = [
        "AERO_ANOMALY", "BRAKE_STRESS", "COLD_TRACK", "DRY_TO_WET",
        "ENGINE_OVERHEAT", "HEAVY_RAIN", "HIGH_FUEL", "HOT_TRACK",
        "LIGHT_RAIN", "LONG_STINT", "LOW_FUEL", "QUALIFYING_DRY",
        "RACE_DRY", "TIRE_OVERHEAT", "WET_TO_DRY"
    ]
    assert sorted(scenarios) == sorted(expected_list)

def test_get_scenario_retrieval():
    sc = get_scenario("RACE_DRY")
    assert sc.name == "RACE_DRY"
    assert sc.session_type == "RACE"
    assert sc.compound == "MEDIUM"

def test_unknown_scenario_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        get_scenario("INVALID_SCENARIO")
    assert "Unknown scenario" in str(excinfo.value)

def test_dynamic_modifiers_dry_to_wet():
    sc = get_scenario("DRY_TO_WET")
    mod_start = sc.get_dynamic_modifiers(0.1)
    assert mod_start["weather_state"] == "DRY"
    
    mod_mid = sc.get_dynamic_modifiers(0.8)
    assert mod_mid["weather_state"] in ["LIGHT_RAIN", "HEAVY_RAIN"]
    assert mod_mid["grip_factor"] < 1.0

def test_all_scenarios_have_valid_initial_fuel():
    for name, sc in SCENARIO_REGISTRY.items():
        assert 5.0 <= sc.initial_fuel_kg <= 120.0
