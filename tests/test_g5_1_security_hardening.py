import json
import sys
import os
import pytest

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from partie1.app import app
from config import AppConfig, config


@pytest.fixture
def client():
    """Provides a Flask test client configured for testing."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    """Verify /health returns 200 OK with liveness info."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "UP"
    assert "timestamp" in data


def test_readiness_endpoint(client):
    """Verify /readiness returns dependency status."""
    response = client.get('/readiness')
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
    assert "dependencies" in data
    assert "mongodb" in data["dependencies"]
    assert "kafka" in data["dependencies"]


def test_telemetry_invalid_content_type(client):
    """Verify POST /telemetry with non-JSON content-type returns 400."""
    response = client.post('/telemetry', data="speed=200", content_type='text/plain')
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "Content-Type" in data["message"]


def test_telemetry_malformed_json(client):
    """Verify POST /telemetry with malformed JSON payload returns 400."""
    response = client.post('/telemetry', data="{invalid_json:", content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"


def test_telemetry_schema_validation_failure(client):
    """Verify POST /telemetry with invalid fields fails schema V1 validation."""
    invalid_payload = {
        "timestamp": "2026-09-26T20:00:00Z",
        "speed": -50.0, # Negative speed invalid
        "lap": 1
    }
    response = client.post('/telemetry', json=invalid_payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "Schema validation failed" in data["message"]


def test_setup_range_validation_downforce(client):
    """Verify POST /setup rejects out-of-bounds downforce values."""
    invalid_setup = {"downforce": 150, "engine_mix": 5}
    response = client.post('/setup', json=invalid_setup)
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "downforce must be between 0 and 100" in data["message"]


def test_setup_range_validation_engine_mix(client):
    """Verify POST /setup rejects out-of-bounds engine_mix values."""
    invalid_setup = {"downforce": 50, "engine_mix": 12}
    response = client.post('/setup', json=invalid_setup)
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "engine_mix must be between 1 and 10" in data["message"]


def test_setup_invalid_type(client):
    """Verify POST /setup rejects non-integer strings or malformed inputs."""
    invalid_setup = {"downforce": "invalid_string", "engine_mix": 5}
    response = client.post('/setup', json=invalid_setup)
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"


def test_not_found_endpoint(client):
    """Verify 404 handler returns clean JSON error response without traceback leakage."""
    response = client.get('/non_existent_route')
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert data["message"] == "Resource Not Found"


def test_cors_headers(client):
    """Verify CORS headers are set appropriately."""
    response = client.get('/health', headers={"Origin": "http://localhost:5000"})
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" in response.headers


def test_secret_masking_in_config():
    """Verify AppConfig masks MongoDB credentials when logging or serializing."""
    cfg = AppConfig()
    masked = cfg.mask_secret("mongodb://admin_user:secret_password@localhost:27017/F1_Simulation")
    assert "secret_password" not in masked
    assert "admin_user" not in masked
    assert "mongodb://***:***@localhost:27017/F1_Simulation" in masked


def test_config_serializes_without_leaking_secrets():
    """Verify config.to_dict() masks secrets by default."""
    cfg = AppConfig()
    cfg.MONGO_URI = "mongodb://myuser:mypassword@localhost:27017"
    serialized = cfg.to_dict(mask_secrets=True)
    assert "mypassword" not in serialized["MONGO_URI"]
    assert "***:***" in serialized["MONGO_URI"]


def test_max_content_length_configuration(client):
    """Verify application limits max payload content length."""
    assert app.config['MAX_CONTENT_LENGTH'] > 0
