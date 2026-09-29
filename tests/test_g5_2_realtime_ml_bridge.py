# -*- coding: utf-8 -*-
"""
G.5.2 Real-Time Stream & ML Bridge Test Suite
Validates Schema V1 processing, SessionStateStore deque windowing, online ML evaluators 
(G.4.2 Anomaly, G.4.3 Lap Time, G.4.4 Tire Degradation), causal boundary protection, 
deterministic replay, signal schemas, and offline Kafka fallback behavior.
"""

import os
import sys
import json
import pytest

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from streaming.ml_bridge_consumer import (
    SessionStateStore,
    OnlineAnomalyEvaluator,
    OnlineLapTimeEvaluator,
    OnlineTireDegradationEvaluator,
    MLBridgeConsumer
)


def get_valid_telemetry_payload(session_id="SES-MONZA-100", lap_number=1, speed=280.0, tire_temp=95.0, tire_wear=10.0):
    """Utility fixture generating Schema V1 compliant telemetry event."""
    return {
        "schema_version": "1.0",
        "session_id": session_id,
        "event_id": f"EVT-TEST-{int(speed * 10)}",
        "car_id": "CAR-01",
        "driver_id": "VER-1",
        "timestamp": "2026-09-26T20:55:00.000Z",
        "lap_number": lap_number,
        "telemetry": {
            "speed": speed,
            "g_force": 2.5,
            "torque": 750.0,
            "pos_x": 10.0,
            "pos_z": -20.0
        },
        "aerodynamics": {
            "wind_speed": 15.0,
            "drag_coefficient": 0.32,
            "downforce": 1600.0
        },
        "tires": {
            "tire_temp": [tire_temp, tire_temp, tire_temp + 5.0, tire_temp + 2.0],
            "tire_wear": [tire_wear, tire_wear, tire_wear + 1.0, tire_wear + 0.5]
        },
        "powertrain": {
            "fuel_remaining_pct": 85.0
        }
    }


def test_schema_v1_acceptance():
    """Verify valid Schema V1 telemetry payload processes cleanly."""
    bridge = MLBridgeConsumer()
    event = get_valid_telemetry_payload()
    signals = bridge.process_event(event)
    assert len(signals) >= 2  # Anomaly + Tire Degradation per tick
    assert signals[0]["signal_type"] == "ANOMALY"
    assert signals[1]["signal_type"] == "TIRE_DEGRADATION"


def test_schema_v1_rejection():
    """Verify malformed telemetry payload is rejected cleanly without raising unhandled exceptions."""
    bridge = MLBridgeConsumer()
    invalid_event = {"schema_version": "1.0", "session_id": "SES-BAD"} # Missing telemetry/tires
    signals = bridge.process_event(invalid_event)
    assert signals == []


def test_session_state_store_init():
    """Verify SessionStateStore initializes with default empty state."""
    store = SessionStateStore(window_size=5)
    assert store.current_lap_number == 1
    assert store.stint_lap_count == 1
    assert len(store.rolling_events) == 0


def test_rolling_deque_maxlen():
    """Verify SessionStateStore rolling deque strictly enforces maxlen=5."""
    store = SessionStateStore(window_size=5)
    for i in range(10):
        ev = get_valid_telemetry_payload(speed=200.0 + i * 10)
        store.update(ev)
    assert len(store.rolling_events) == 5


def test_session_reset():
    """Verify SessionStateStore resets accumulators when a new session_id is received."""
    store = SessionStateStore()
    store.update(get_valid_telemetry_payload(session_id="SES-01", lap_number=3))
    assert store.current_lap_number == 3

    # Switch session ID
    store.update(get_valid_telemetry_payload(session_id="SES-02", lap_number=1))
    assert store.session_id == "SES-02"
    assert store.current_lap_number == 1


def test_lap_transition():
    """Verify lap transition is triggered when lap_number increments."""
    store = SessionStateStore()
    res1 = store.update(get_valid_telemetry_payload(lap_number=1))
    assert res1["lap_transition"] is False

    res2 = store.update(get_valid_telemetry_payload(lap_number=2))
    assert res2["lap_transition"] is True
    assert store.current_lap_number == 2
    assert store.last_completed_lap_summary is not None


def test_compound_change_reset():
    """Verify pit stop and compound change resets stint lap count."""
    store = SessionStateStore()
    store.update(get_valid_telemetry_payload(lap_number=5))
    assert store.stint_lap_count == 1

    pit_event = get_valid_telemetry_payload(lap_number=5)
    pit_event["is_in_pit"] = True
    pit_event["tire_compound"] = "HARD"

    res = store.update(pit_event)
    assert store.stint_lap_count == 0
    assert store.current_compound == "HARD"


def test_anomaly_evaluator_scoring():
    """Verify OnlineAnomalyEvaluator returns valid score between 0 and 1."""
    evaluator = OnlineAnomalyEvaluator()
    event = get_valid_telemetry_payload(speed=280.0, tire_temp=95.0)
    res = evaluator.evaluate(event)
    assert 0.0 <= res["anomaly_score"] <= 1.0
    assert "severity" in res
    assert "contributing_signals" in res


def test_anomaly_severity_mapping():
    """Verify anomaly scores map cleanly to severity tiers."""
    evaluator = OnlineAnomalyEvaluator()
    
    # Overheated tires trigger critical anomaly score
    critical_event = get_valid_telemetry_payload(tire_temp=140.0)
    res = evaluator.evaluate(critical_event)
    assert res["severity"] == "CRITICAL"
    assert res["is_anomaly"] is True
    assert "tire_temp_peak" in res["contributing_signals"]


def test_pre_lap_prediction_causal_boundary():
    """Verify LapTimeEvaluator relies strictly on pre-lap summary without current-lap leakage."""
    evaluator = OnlineLapTimeEvaluator()
    pre_lap_summary = {
        "average_speed_before_lap": 260.0,
        "tire_temp_avg_before_lap": 92.0,
        "tire_wear_avg_before_lap": 15.0,
        "fuel_remaining_pct_before_lap": 80.0
    }
    res = evaluator.evaluate(pre_lap_summary)
    assert res["causal_boundary_validated"] is True
    assert 70.0 <= res["predicted_lap_time_sec"] <= 140.0


def test_no_current_lap_leakage():
    """Verify lap time prediction signal is generated ONLY on lap transitions."""
    bridge = MLBridgeConsumer()
    
    # Tick 1 on Lap 1 -> No lap time prediction signal
    signals_t1 = bridge.process_event(get_valid_telemetry_payload(lap_number=1))
    signal_types_t1 = [s["signal_type"] for s in signals_t1]
    assert "LAP_TIME_PREDICTION" not in signal_types_t1

    # Tick on Lap 2 transition -> LAP_TIME_PREDICTION signal emitted
    signals_t2 = bridge.process_event(get_valid_telemetry_payload(lap_number=2))
    signal_types_t2 = [s["signal_type"] for s in signals_t2]
    assert "LAP_TIME_PREDICTION" in signal_types_t2


def test_tire_degradation_horizon():
    """Verify TireDegradationEvaluator calculates remaining life and 10-lap wear projections."""
    evaluator = OnlineTireDegradationEvaluator()
    event = get_valid_telemetry_payload(tire_wear=20.0)
    res = evaluator.evaluate(event, stint_lap=5)
    assert "current_wear_4corner" in res
    assert "projected_wear_10_laps" in res
    assert res["remaining_life_laps"] > 0
    assert "fl" in res["projected_wear_10_laps"]


def test_four_corner_tire_handling():
    """Verify 4-corner wheel wear positions (fl, fr, rl, rr) are formatted explicitly."""
    evaluator = OnlineTireDegradationEvaluator()
    event = get_valid_telemetry_payload(tire_wear=15.0)
    res = evaluator.evaluate(event, stint_lap=3)
    corners = res["current_wear_4corner"]
    assert set(corners.keys()) == {"fl", "fr", "rl", "rr"}


def test_kafka_offline_fallback():
    """Verify MLBridgeConsumer handles offline Kafka cluster gracefully without throwing exceptions."""
    bridge = MLBridgeConsumer()
    connected = bridge.init_kafka()
    assert connected in (True, False) # Does not raise uncaught error


def test_deterministic_replay():
    """Verify replaying the identical telemetry sequence 5 times yields identical ML signals."""
    results = []
    events = [
        get_valid_telemetry_payload(lap_number=1, speed=250.0 + i * 5) for i in range(5)
    ]

    for run in range(5):
        bridge = MLBridgeConsumer()
        run_signals = []
        for ev in events:
            sigs = bridge.process_event(ev)
            # Remove timestamp for deterministic comparison
            sigs_cleaned = []
            for s in sigs:
                s_copy = s.copy()
                s_copy.pop("timestamp", None)
                sigs_cleaned.append(s_copy)
            run_signals.append(sigs_cleaned)
        results.append(run_signals)

    # Compare runs 1..4 with run 0
    base_json = json.dumps(results[0], sort_keys=True)
    for k in range(1, 5):
        run_json = json.dumps(results[k], sort_keys=True)
        assert run_json == base_json



def test_duplicate_event_handling():
    """Verify processing duplicate telemetry events does not break state store."""
    bridge = MLBridgeConsumer()
    event = get_valid_telemetry_payload(speed=300.0)
    sigs1 = bridge.process_event(event)
    sigs2 = bridge.process_event(event)
    assert len(sigs1) >= 2
    assert len(sigs2) >= 2


def test_out_of_order_event_handling():
    """Verify state store handles events with missing optional fields or unordered speeds."""
    bridge = MLBridgeConsumer()
    event1 = get_valid_telemetry_payload(speed=320.0)
    event2 = get_valid_telemetry_payload(speed=150.0)
    del event2["powertrain"]  # Missing optional section
    
    sigs1 = bridge.process_event(event1)
    sigs2 = bridge.process_event(event2)
    assert len(sigs1) >= 2
    assert len(sigs2) >= 2


def test_ml_signal_schema():
    """Verify emitted ML signals adhere to standardized JSON schema structure."""
    bridge = MLBridgeConsumer()
    signals = bridge.process_event(get_valid_telemetry_payload(lap_number=2))
    
    for sig in signals:
        assert "schema_version" in sig
        assert "signal_type" in sig
        assert "session_id" in sig
        assert "event_id" in sig
        assert "timestamp" in sig
        assert "model_version" in sig


def test_signal_serialization():
    """Verify ML signals serialize to JSON cleanly without type errors."""
    bridge = MLBridgeConsumer()
    signals = bridge.process_event(get_valid_telemetry_payload())
    for sig in signals:
        serialized = json.dumps(sig)
        assert isinstance(serialized, str)
        assert len(serialized) > 0


def test_ml_bridge_performance_benchmark():
    """Measures empirical per-event processing latency over 1,000 telemetry events."""
    import time
    bridge = MLBridgeConsumer()
    payload = get_valid_telemetry_payload()

    t0 = time.perf_counter()
    iterations = 1000
    for _ in range(iterations):
        bridge.process_event(payload)
    t1 = time.perf_counter()

    total_time_ms = (t1 - t0) * 1000.0
    avg_latency_ms = total_time_ms / iterations

    # Assert avg latency per event is well below target threshold of 15 ms (< 2.0 ms typical)
    assert avg_latency_ms < 15.0

