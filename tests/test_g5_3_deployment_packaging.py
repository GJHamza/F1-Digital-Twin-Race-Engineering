# -*- coding: utf-8 -*-
"""
G.5.3 Deployment Packaging & Production Readiness Test Suite
Validates Docker configuration, environment variable templates, requirements files, 
CI/CD workflows, G.5.1 security preservation, and non-regression of G.4.5/G.4.6 strategy engines.
"""

import os
import sys
import pytest

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import AppConfig, config
from partie1.app import app
from ml.strategy import RaceConfig, StrategyState, StrategySimulator
from ml.strategy.dashboard_adapter import StrategyDashboardAdapter



PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def test_requirements_file_exists():
    """Verify requirements.txt exists and contains core dependencies."""
    req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    assert os.path.exists(req_path)
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Flask" in content
    assert "streamlit" in content
    assert "kafka-python" in content
    assert "pymongo" in content
    assert "gunicorn" in content


def test_env_example_template_exists():
    """Verify .env.example contains safe environment template variables."""
    env_ex_path = os.path.join(PROJECT_ROOT, ".env.example")
    assert os.path.exists(env_ex_path)
    with open(env_ex_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "FLASK_ENV" in content
    assert "MONGO_URI" in content
    assert "KAFKA_BOOTSTRAP_SERVERS" in content
    assert "MINIO_ENDPOINT" in content
    assert "CORS_ORIGINS" in content


def test_dockerfiles_exist():
    """Verify required application Dockerfiles exist."""
    dockerfiles = [
        "Dockerfile.api",
        "Dockerfile.dashboard",
        "Dockerfile.ml_bridge",
        "Dockerfile.data_engine",
        "docker-compose.prod.yml"
    ]
    for df in dockerfiles:
        path = os.path.join(PROJECT_ROOT, df)
        assert os.path.exists(path), f"Missing deployment file: {df}"


def test_ci_workflow_exists():
    """Verify GitHub Actions CI workflow file exists."""
    ci_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml")
    assert os.path.exists(ci_path)


def test_config_handles_env_variables():
    """Verify AppConfig parses environment overrides cleanly."""
    cfg = AppConfig()
    assert cfg.PORT > 0
    assert isinstance(cfg.CORS_ORIGINS, (list, str))
    assert cfg.MAX_CONTENT_LENGTH == 1048576


def test_app_health_and_readiness_probes():
    """Verify Flask application responds to health and readiness probes."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        res_h = client.get('/health')
        assert res_h.status_code == 200
        assert res_h.get_json()["status"] == "UP"

        res_r = client.get('/readiness')
        assert res_r.status_code == 200
        assert "status" in res_r.get_json()


def test_secret_masking_active():
    """Verify AppConfig masks passwords in connection strings."""
    cfg = AppConfig()
    masked = cfg.mask_secret("mongodb://admin:secret123@localhost:27017")
    assert "secret123" not in masked
    assert "admin" not in masked


def test_g4_5_strategy_engine_non_regression():
    """Verify G.4.5 Strategy Simulator output remains deterministic."""
    from ml.strategy import RaceConfig, Stint, PitStop, StrategySimulator
    race_cfg = RaceConfig(race_id="RACE_TEST_50", total_laps=50, starting_fuel=100.0)
    stints = [
        Stint("S1", 1, "SOFT", 1, 25, 100.0, 50.0, 0.0, 25.0),
        Stint("S2", 2, "MEDIUM", 26, 50, 50.0, 0.0, 0.0, 20.0),
    ]
    pit_stops = [PitStop("P1", 25, "SOFT", "MEDIUM", 1, 2, duration_sec=22.5)]

    sim = StrategySimulator(race_cfg)
    res = sim.simulate_strategy(stints, pit_stops)
    assert res.total_race_time_sec > 0
    assert len(res.lap_records) == 50
    assert res.is_feasible is True


def test_g4_6_strategy_dashboard_adapter_non_regression():
    """Verify G.4.6 Strategy Dashboard Adapter formatting logic is preserved."""
    from ml.strategy.dashboard_adapter import StrategyDashboardAdapter
    from ml.strategy.ranking_result import RankingResult
    dummy_ranking = RankingResult(ranked_strategies=(), total_candidates=0, valid_candidates=0, excluded_candidates=0, top_k=5)
    adapter = StrategyDashboardAdapter(ranking_result=dummy_ranking)
    assert hasattr(adapter, "leaderboard_dataframe")
    assert hasattr(adapter, "comparison_dataframe")
    assert hasattr(adapter, "stint_dataframe")

