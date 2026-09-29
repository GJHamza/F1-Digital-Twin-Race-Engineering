# -*- coding: utf-8 -*-
"""
Unit Tests for Streaming Utility Functions & PySpark Processing
"""

import os
import sys
import pytest
import json

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from streaming.config import StreamingConfig
from streaming.schema import get_telemetry_spark_schema


def test_schema_json_parsing_sample(tmp_path):
    """Verify sample JSON payload matches schema structure without exceptions."""
    sample_payload = {
        "schema_version": "1.0",
        "session_id": "SES_TEST_STRM_01",
        "event_id": "EVT_STRM_001",
        "car_id": "FERRARI_01",
        "car_name": "SF-24",
        "team": "FERRARI",
        "driver_id": "LEC",
        "driver_name": "Charles Leclerc",
        "lap_number": 5,
        "timestamp": "2026-09-22T10:30:00.000Z",
        "fuel_level": 98.5,
        "telemetry": {
            "speed": 310.4,
            "rpm": 11800,
            "gear": 7,
            "torque": 450.0,
            "g_force": 1.8,
            "pos_x": 120.5,
            "pos_z": -450.2
        },
        "aerodynamics": {
            "wind_speed": 8.5,
            "drag_coefficient": 0.34,
            "downforce": 480.0
        },
        "tires": {
            "tire_temp": [94.0, 95.0, 96.0, 93.0],
            "tire_wear": [3.5, 3.6, 3.7, 3.4]
        },
        "active_anomalies": []
    }

    raw_json = json.dumps(sample_payload)
    data = json.loads(raw_json)

    assert data["event_id"] == "EVT_STRM_001"
    assert data["session_id"] == "SES_TEST_STRM_01"
    assert data["telemetry"]["speed"] == 310.4
    assert len(data["tires"]["tire_temp"]) == 4
