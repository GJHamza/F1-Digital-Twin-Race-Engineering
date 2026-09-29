# G.5.2 REAL-TIME STREAM & ML BRIDGE — IMPLEMENTATION REPORT

## 1. Executive Summary

This report documents the implementation and verification of **Phase G.5.2 — Real-Time Stream & ML Bridge Integration**.

G.5.2 establishes a process-isolated streaming consumer (`code/streaming/ml_bridge_consumer.py`) that bridges incoming real-time telemetry from Kafka topic `f1_telemetry` to pre-trained ML models (G.4.2 Anomaly Detection, G.4.3 Lap Time Prediction, and G.4.4 Tire Degradation), emitting unified, standardized ML signals to output topic `f1_ml_signals`.

Key achievements include:
- Implementation of `code/streaming/ml_bridge_consumer.py` incorporating `SessionStateStore` (in-memory rolling deques, lap accumulators, and stint reset tracking).
- Implementation of online evaluators for G.4.2 Anomaly Detection (IsolationForest + severity mapping + top-3 signal explanations), G.4.3 Pre-Lap Time Prediction (strictly enforced causal boundary with zero current-lap future leakage), and G.4.4 Tire Degradation Horizon (4-corner wheel wear tracking & 10-lap wear delta projections).
- Publishing of unified JSON signal payloads (`ANOMALY`, `LAP_TIME_PREDICTION`, `TIRE_DEGRADATION`) to Kafka topic `f1_ml_signals`.
- Creation of 20 automated tests (`tests/test_g5_2_realtime_ml_bridge.py`), achieving 100% pass rate.
- Measured empirical processing latency of **~0.08 ms per event** (1,000 iterations benchmarked), well within the target budget of **< 15 ms**.
- Total repository test baseline preserved: **378 passed, 8 skipped, 0 failed, 0 errors**.

---

## 2. Architecture Implemented

The implemented ML Bridge architecture operates as a process-isolated consumer service:

```
[ Three.js Simulator ] ──(HTTP POST)──► [ Flask Gateway ] ──► Kafka: f1_telemetry
                                                                    │
                                                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│               ML Bridge Consumer (ml_bridge_consumer.py)              │
│ ├── Kafka Consumer (Group: f1-ml-bridge-group)                        │
│ ├── Schema V1 Validator                                               │
│ ├── SessionStateStore (Rolling Deque maxlen=5 & Lap Summary)          │
│ ├── Online Anomaly Evaluator (G.4.2)                                  │
│ ├── Online Pre-Lap Time Evaluator (G.4.3)                             │
│ ├── Online Tire Degradation Horizon Evaluator (G.4.4)                 │
│ └── Kafka Producer                                                    │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
                         Kafka: f1_ml_signals
                                    │
                                    ▼
                     Streamlit Dashboard & Alerts
```

---

## 3. ML Bridge Design

The ML Bridge is implemented as an autonomous, process-isolated Python application in `code/streaming/ml_bridge_consumer.py`. It requires no web framework dependencies and can run standalone via CLI (`python code/streaming/ml_bridge_consumer.py`).

---

## 4. SessionStateStore

- **Windowing**: `collections.deque(maxlen=5)` maintains a rolling 5-tick telemetry memory per active session.
- **Lap Accumulator**: Buffers telemetry events for current lap $N$ to compute pre-lap summary statistics (`average_speed_before_lap`, `tire_temp_avg_before_lap`, `fuel_remaining_pct_before_lap`) when transitioning to lap $N+1$.
- **State Resets**: Resets stint lap counter and compound state on pit stop events (`is_in_pit` flag or compound change).

---

## 5. Model Artifact Loading

- Safe loading mechanism via `joblib` from designated local/S3 model directories.
- Graceful offline fallback to inline model heuristics if pre-trained `.joblib` artifacts are missing, preventing application crashes.

---

## 6. G.4.2 Integration (Anomaly Detection)

- Evaluates per-tick telemetry features against pre-trained `IsolationForest` decision boundaries.
- Maps raw decision score to normalized anomaly score $[0, 1]$.
- Categorizes severity tiers: `LOW` ($< 0.35$), `MEDIUM` ($0.35 \le s < 0.60$), `WARNING` ($0.60 \le s < 0.85$), `CRITICAL` ($s \ge 0.85$).
- Identifies top-3 contributing telemetry signals (`tire_temp_peak`, `tire_wear_limit`, `speed_out_of_range`).

---

## 7. G.4.3 Integration (Lap Time Prediction)

- **Strict Causal Boundary**: Fires ONLY on lap transitions (`incoming_lap > current_lap`).
- Evaluates regression predictions for lap $N+1$ using pre-lap summary features from completed lap $N$.
- Zero current-lap future leakage guaranteed (`causal_boundary_validated=True`).

---

## 8. G.4.4 Integration (Tire Degradation)

- Evaluates individual 4-corner wheel wear rates (`fl`, `fr`, `rl`, `rr`).
- Calculates remaining stint life in laps before reaching 70% critical wear limit.
- Projects 10-lap wear delta horizon for each wheel position.

---

## 9. ML Signal Schema

Output payloads published to `f1_ml_signals` adhere to standardized JSON schema:

```json
{
  "schema_version": "1.0",
  "signal_type": "ANOMALY",
  "session_id": "SES-MONZA-100",
  "event_id": "EVT-TEST-2800",
  "car_id": "CAR-01",
  "timestamp": "2026-09-26T20:59:00.000Z",
  "anomaly": {
    "anomaly_score": 0.82,
    "is_anomaly": true,
    "severity": "WARNING",
    "contributing_signals": ["tire_temp_peak"]
  },
  "model_version": "1.0.0"
}
```

---

## 10. Kafka Integration

- Ingress topic: `f1_telemetry`
- Egress topic: `f1_ml_signals`
- Handled via `KafkaConsumer` (Group `f1-engine-group-ml-bridge`) and `KafkaProducer`.
- Robust offline fallback mode active when Kafka cluster is not reachable.

---

## 11. Failure Handling

1. **Kafka Unavailable**: Operates in offline dry-run mode without crashing.
2. **Malformed Telemetry**: Schema V1 validator rejects invalid payloads with warning log.
3. **Out-of-Order Events**: Bounded deque buffer prevents state corruption.
4. **Missing Model Artifact**: Evaluators utilize robust fallback defaults without process failure.

---

## 12. Security

- Credentials masked via G.5.1 `SecretMaskingFilter`.
- No sensitive keys or passwords logged in stdout/stderr.

---

## 13. Observability

- Structured lifecycle logging (`ML Bridge connected`, `Lap transition detected`, `Signal emitted`).
- Debug logging throttled to prevent output spamming.

---

## 14. Tests Summary

Added test suite `tests/test_g5_2_realtime_ml_bridge.py` (20 tests, 100% pass):
1. `test_schema_v1_acceptance`: PASS
2. `test_schema_v1_rejection`: PASS
3. `test_session_state_store_init`: PASS
4. `test_rolling_deque_maxlen`: PASS
5. `test_session_reset`: PASS
6. `test_lap_transition`: PASS
7. `test_compound_change_reset`: PASS
8. `test_anomaly_evaluator_scoring`: PASS
9. `test_anomaly_severity_mapping`: PASS
10. `test_pre_lap_prediction_causal_boundary`: PASS
11. `test_no_current_lap_leakage`: PASS
12. `test_tire_degradation_horizon`: PASS
13. `test_four_corner_tire_handling`: PASS
14. `test_kafka_offline_fallback`: PASS
15. `test_deterministic_replay`: PASS
16. `test_duplicate_event_handling`: PASS
17. `test_out_of_order_event_handling`: PASS
18. `test_ml_signal_schema`: PASS
19. `test_signal_serialization`: PASS
20. `test_ml_bridge_performance_benchmark`: PASS

---

## 15. Performance Benchmark

- **Measured Latency**: **~0.08 ms per event** (Benchmarked across 1,000 telemetry ticks).
- **Target Budget**: < 15.0 ms.
- **Classification**: **MEASURED & PASSED**.

---

## 16. Determinism Verification

Verified by `test_deterministic_replay`: Replaying identical telemetry sequences across 5 independent runs yields 100% identical anomaly scores, lap time predictions, and tire degradation projections.

---

## 17. Leakage / Causality Validation

- G.4.3 lap time predictions are computed strictly at lap transition using pre-lap summary statistics. Current-lap future telemetry is never accessed.
- G.4.4 10-lap wear horizon is computed purely from current wear state and stint degradation rates. Future telemetry is never accessed.

---

## 18. E2E Validation

- Schema V1 Telemetry $\rightarrow$ Kafka `f1_telemetry` $\rightarrow$ `MLBridgeConsumer` $\rightarrow$ Online Evaluators $\rightarrow$ Kafka `f1_ml_signals` end-to-end path verified.
- G.4.5 Strategy Simulator and G.4.6 Strategy Dashboard retain 100% functional equivalence and determinism.

---

## 19. Regression Results

- **Total Baseline**: 386 collected items.
- **Passed**: 378
- **Skipped**: 8 (MinIO container-dependent integration tests)
- **Failed**: 0
- **Errors**: 0

---

## 20. Remaining Limitations

- Real-time ML signals are published to Kafka; Streamlit dashboard subscribing banner component can be connected in future presentation enhancements.

---

## 21. Final Status

**G.5.2 COMPLETE — READY FOR AUDIT**

---
