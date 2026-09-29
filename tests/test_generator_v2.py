# -*- coding: utf-8 -*-
import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from data_generator.generator_v2 import SyntheticGeneratorV2
from schema.schema_validator import validate_telemetry

def test_deterministic_generation_reproducibility():
    gen1 = SyntheticGeneratorV2(seed=42)
    events1 = gen1.generate_session("RACE_DRY", laps_count=1)

    gen2 = SyntheticGeneratorV2(seed=42)
    events2 = gen2.generate_session("RACE_DRY", laps_count=1)

    assert len(events1) == len(events2)
    # Compare key fields across all events
    for e1, e2 in zip(events1, events2):
        assert e1["event_id"] == e2["event_id"]
        assert e1["session_id"] == e2["session_id"]
        assert e1["telemetry"]["speed"] == e2["telemetry"]["speed"]
        assert e1["telemetry"]["torque"] == e2["telemetry"]["torque"]

def test_stable_session_id_and_unique_event_ids():
    gen = SyntheticGeneratorV2(seed=123)
    events = gen.generate_session("RACE_DRY", laps_count=2)
    
    session_ids = set(e["session_id"] for e in events)
    assert len(session_ids) == 1  # Exactly 1 stable session_id per session
    
    event_ids = [e["event_id"] for e in events]
    assert len(event_ids) == len(set(event_ids))  # All event_ids are unique

def test_timestamp_monotonicity():
    gen = SyntheticGeneratorV2(seed=99)
    events = gen.generate_session("RACE_DRY", laps_count=2)
    
    timestamps = [e["timestamp"] for e in events]
    for i in range(1, len(timestamps)):
        assert timestamps[i] > timestamps[i-1]

def test_all_events_satisfy_schema_v1():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_session("RACE_DRY", laps_count=2)
    
    for evt in events:
        res = validate_telemetry(evt)
        assert res["valid"] is True, f"Event {evt['event_id']} failed schema: {res['errors']}"

def test_tire_arrays_valid_length_four():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_session("RACE_DRY", laps_count=1)
    
    for evt in events:
        assert len(evt["tires"]["tire_temp"]) == 4
        assert len(evt["tires"]["tire_wear"]) == 4
        assert len(evt["tires"]["tire_pressure"]) == 4

def test_fuel_monotonicity():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_session("RACE_DRY", laps_count=3)
    
    fuels = [e["fuel_level"] for e in events]
    for i in range(1, len(fuels)):
        assert fuels[i] <= fuels[i-1]
        assert fuels[i] >= 0.0

def test_tire_wear_progression():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_session("LONG_STINT", laps_count=3)
    
    wear_fl_start = events[0]["tires"]["tire_wear"][0]
    wear_fl_end = events[-1]["tires"]["tire_wear"][0]
    assert wear_fl_end > wear_fl_start

def test_bounded_percentages():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_session("RACE_DRY", laps_count=2)
    
    for evt in events:
        assert 0.0 <= evt["throttle"] <= 100.0
        assert 0.0 <= evt["brake"] <= 100.0
        for w in evt["tires"]["tire_wear"]:
            assert 0.0 <= w <= 100.0

def test_anomaly_generation():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_session("TIRE_OVERHEAT", laps_count=1)
    
    anomalous_events = [e for e in events if e["anomaly_flag"]]
    assert len(anomalous_events) > 0
    assert any(a["type"] == "TIRE_OVERHEAT" for e in anomalous_events for a in e["active_anomalies"])

def test_scenario_differences():
    gen1 = SyntheticGeneratorV2(seed=42)
    events_dry = gen1.generate_session("QUALIFYING_DRY", laps_count=1)
    
    gen2 = SyntheticGeneratorV2(seed=42)
    events_wet = gen2.generate_session("HEAVY_RAIN", laps_count=1)
    
    avg_speed_dry = sum(e["telemetry"]["speed"] for e in events_dry) / len(events_dry)
    avg_speed_wet = sum(e["telemetry"]["speed"] for e in events_wet) / len(events_wet)
    
    assert avg_speed_dry > avg_speed_wet

def test_jsonl_dataset_output_file(tmp_path):
    out_file = tmp_path / "test_output.jsonl"
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_dataset("RACE_DRY", sessions_count=1, laps_per_session=2, output_file=str(out_file))
    
    assert os.path.exists(out_file)
    with open(out_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    assert len(lines) == len(events)
    first_doc = json.loads(lines[0])
    assert first_doc["schema_version"] == "1.0"
