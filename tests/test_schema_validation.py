# -*- coding: utf-8 -*-
import sys
import os
import pytest

# Ensure code directory is on import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from schema.schema_validator import validate_telemetry

def get_minimal_valid_payload():
    return {
        "schema_version": "1.0",
        "session_id": "SES-TEST-001",
        "event_id": "EVT-TEST-001",
        "car_id": "SIM-CAR-01",
        "timestamp": "2026-09-21T23:55:00.000Z",
        "telemetry": {
            "speed": 310.0,
            "g_force": 1.01,
            "torque": 873.31,
            "pos_x": -62.64,
            "pos_z": -52.15
        },
        "aerodynamics": {
            "wind_speed": 50.0,
            "drag_coefficient": 0.362,
            "downforce": 5525.76
        },
        "tires": {
            "tire_temp": [118.7, 118.7, 118.7, 118.7],
            "tire_wear": [3.33, 3.33, 3.33, 3.33]
        }
    }

def get_full_valid_payload():
    payload = get_minimal_valid_payload()
    payload.update({
        "car_name": "AERO PHANTOM",
        "team": "WILLIAMS",
        "driver_id": "SIM-DRV-01",
        "driver_name": "Alex Albon (Sim)",
        "lap_number": 5,
        "throttle": 100.0,
        "brake": 0.0,
        "steering_angle": 0.0,
        "fuel_level": 85.4
    })
    payload["telemetry"]["rpm"] = 11500.0
    payload["telemetry"]["gear"] = 7
    return payload

def test_minimal_valid_payload_passes():
    payload = get_minimal_valid_payload()
    res = validate_telemetry(payload)
    assert res["valid"] is True
    assert len(res["errors"]) == 0

def test_full_valid_payload_passes():
    payload = get_full_valid_payload()
    res = validate_telemetry(payload)
    assert res["valid"] is True
    assert len(res["errors"]) == 0

def test_missing_session_id_fails():
    payload = get_minimal_valid_payload()
    del payload["session_id"]
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("session_id" in err for err in res["errors"])

def test_missing_event_id_fails():
    payload = get_minimal_valid_payload()
    del payload["event_id"]
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("event_id" in err for err in res["errors"])

def test_invalid_speed_fails():
    payload = get_minimal_valid_payload()
    payload["telemetry"]["speed"] = -50.0  # Negative speed below min 0.0
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("speed" in err for err in res["errors"])

def test_invalid_tire_array_length_fails():
    payload = get_minimal_valid_payload()
    payload["tires"]["tire_temp"] = [118.7, 118.7, 118.7]  # 3 elements instead of 4
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("tire_temp" in err for err in res["errors"])

def test_invalid_tire_wear_range_fails():
    payload = get_minimal_valid_payload()
    payload["tires"]["tire_wear"] = [3.33, 3.33, 3.33, 150.0]  # Exceeds max 100.0%
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("tire_wear" in err for err in res["errors"])

def test_invalid_throttle_fails():
    payload = get_full_valid_payload()
    payload["throttle"] = 125.0  # Exceeds max 100.0%
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("throttle" in err for err in res["errors"])

def test_invalid_schema_version_fails():
    payload = get_minimal_valid_payload()
    payload["schema_version"] = "2.0"  # Invalid schema version
    res = validate_telemetry(payload)
    assert res["valid"] is False
    assert any("schema_version" in err for err in res["errors"])

def test_non_dict_payload_fails():
    res = validate_telemetry("not a json dict")
    assert res["valid"] is False
    assert len(res["errors"]) == 1
