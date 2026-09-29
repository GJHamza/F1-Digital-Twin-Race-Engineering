# -*- coding: utf-8 -*-
import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

# Ensure code directory is on import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))

from partie1.app import app
from schema.schema_validator import validate_telemetry

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def get_valid_payload():
    return {
        "schema_version": "1.0",
        "session_id": "SES-TEST-100",
        "event_id": "EVT-TEST-100",
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

def test_ping_payload_passes(client):
    res = client.post('/telemetry', json={"ping": True})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data.get("ping") is True

@patch('partie1.app.producer')
def test_valid_payload_calls_kafka(mock_producer, client):
    mock_producer.send = MagicMock()
    mock_producer.flush = MagicMock()
    
    payload = get_valid_payload()
    res = client.post('/telemetry', json=payload)
    
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    mock_producer.send.assert_called_once_with('f1_telemetry', value=payload)

@patch('partie1.app.producer')
@patch('partie1.app.mongo_client')
def test_invalid_payload_rejected_with_400_no_kafka_or_mongo(mock_mongo, mock_producer, client):
    mock_producer.send = MagicMock()
    mock_mongo.db = MagicMock()
    
    invalid_payload = get_valid_payload()
    del invalid_payload["session_id"]  # Missing required field
    
    res = client.post('/telemetry', json=invalid_payload)
    
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "Schema validation failed" in data["message"]
    assert len(data["errors"]) > 0
    
    # Assert neither Kafka nor MongoDB fallback was invoked
    mock_producer.send.assert_not_called()
    mock_mongo.db.insert_one.assert_not_called()
