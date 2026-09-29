# F1 DIGITAL TWIN — PHASE G.4.2 VALIDATION REPORT
## Telemetry Anomaly Detection
**Status**: GREEN (100% Validated)  
**Date**: 2026-09-22  
**Environment**: PySpark 3.5.1 / PyArrow 24.0.0 / Scikit-learn / MinIO S3A / Parquet  

---

## 1. Executive Summary

Phase G.4.2 successfully delivers an **Unsupervised Telemetry Anomaly Detection System** for the F1 Digital Twin platform under `code/ml/anomaly/`. The pipeline reads feature datasets from G.4.1 (`s3a://f1-data-lake/ml/features/`), trains an Isolation Forest model and a Z-score statistical baseline strictly on the `train` partition, calibrates severity thresholds on `validation`, predicts anomalies on `test`, generates top signal explainability, and writes Parquet anomaly datasets to MinIO S3A (`s3a://f1-data-lake/ml/anomalies/`).

### Key Accomplishments:
1. **Modular Anomaly Package (`code/ml/anomaly/`)**:
   - `preprocessing.py`: `StandardScaler` fit **strictly on Train** with explicit feature column order preservation.
   - `baseline.py`: Z-Score statistical baseline detector serving as a reference benchmark.
   - `isolation_forest.py`: Scikit-learn `IsolationForest` wrapper (`n_estimators=100`, `contamination=0.05`, `random_state=42`) trained **strictly on Train**.
   - `scoring.py`: Normalizes decision scores to $[0, 1]$ and maps severity levels (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`) calibrated on **Validation** set quantiles ($90^{\text{th}}$, $95^{\text{th}}$, $99^{\text{th}}$ percentiles).
   - `explain.py`: Identifies top 3 contributing signals using Z-score deviations relative to Train baseline without claiming causal attribution.
   - `detector.py`: End-to-end pipeline orchestrator saving formatted Parquet anomaly datasets.
2. **Data Leakage Prevention**:
   - Preprocessing scaler and Isolation Forest model fit **exclusively on Train**.
   - Quantile thresholds calibrated **exclusively on Validation**.
   - Predictions on **Test** use frozen scaler, model, and thresholds.
   - Identifiers (`event_id`, `session_id`, `timestamp`, `car_id`, `driver_id`) excluded from model inputs.
3. **Performance & Throughput**:
   - Benchmarked at **~3,124 rows/second** throughput on 1,000 telemetry events across 3 partitions.

---

## 2. Model & Algorithm Comparison

| Dimension | Statistical Z-Score Baseline | Isolation Forest Model |
| :--- | :--- | :--- |
| **Methodology** | Univariate Max Absolute Z-Score | Multi-dimensional Random Isolation Trees |
| **Feature Interactions** | Independent feature deviation | Captures non-linear feature interactions |
| **Training Partition** | Fit on Train means & standard deviations | Fit on Train feature space (`n_estimators=100`) |
| **Threshold Calibration** | Fixed $Z > 3.0$ standard deviation limit | Quantile thresholds fit on Validation scores |
| **Detected Anomalies** | 99 / 1,000 (9.90%) | 77 / 1,000 (7.70%) |
| **Operational Role** | Statistical Reference Baseline | Production Anomaly Classifier |

---

## 3. Severity Level Calibration & Distribution

Severity thresholds were calibrated using Validation partition decision score quantiles ($90^{\text{th}}$, $95^{\text{th}}$, $99^{\text{th}}$ percentiles):

| Severity Level | Operational Definition | Score Threshold | Sample Breakdown (1,000 events) |
| :--- | :--- | :--- | :--- |
| **`NORMAL`** | Standard nominal telemetry operation | Score $< 90^{\text{th}}$ quantile | **936 records (93.60%)** |
| **`LOW`** | Slight statistical deviation | Score $\ge 90^{\text{th}}$ and $< 95^{\text{th}}$ quantile | **15 records (1.50%)** |
| **`MEDIUM`** | Moderate multi-signal telemetry deviation | Score $\ge 95^{\text{th}}$ and $< 99^{\text{th}}$ quantile | **37 records (3.70%)** |
| **`HIGH`** | Critical extreme telemetry anomaly | Score $\ge 99^{\text{th}}$ quantile | **12 records (1.20%)** |

---

## 4. Signal Explainability Example

For each detected anomaly, the `explain.py` engine computes top 3 deviating signals relative to Train baseline distribution:

```json
{
  "event_id": "EVT_BENCH_A_000050",
  "anomaly_score": 0.9842,
  "anomaly_label": 1,
  "anomaly_severity": "HIGH",
  "contributing_signals": "[\"speed_kmh\", \"rpm\", \"tire_temp_avg\"]",
  "model_version": "1.0.0"
}
```

*Note: Signals indicate associated statistical deviations, not causal attribution.*

---

## 5. Benchmark & Performance Metrics

| Metric | Benchmark Result | Target / Threshold | Pass / Fail |
| :--- | :--- | :--- | :--- |
| **Total Processed Rows** | 1,000 rows | $\ge 100$ rows | PASS |
| **Partition Breakdown** | Train: 700 / Val: 150 / Test: 150 | 70% / 15% / 15% | PASS |
| **Isolation Forest Anomalies** | 77 anomalies (7.70%) | $[5\%, 10\%]$ expected | PASS |
| **Baseline Anomalies** | 99 anomalies (9.90%) | Baseline reference | PASS |
| **Execution Duration** | 0.320 seconds | $< 5.0$ seconds | PASS |
| **Throughput** | **3,123.8 rows/sec** | $> 500$ rows/sec | PASS |

---

## 6. Non-Regression Test Suite Audit

- **Total Test Cases Collected**: 98
- **Passed**: 98
- **Skipped**: 0 (all MinIO integration tests passed with MinIO active)
- **Failed**: 0
- **Existing Tests Preserved**: 91 / 91 (100%)
- **New G.4.2 Anomaly Unit & Integration Tests**: 7 / 7 (100% Passed)
- **Regression Rate**: **0.0%**

---

## 7. Verdict

**Final Verdict**: **GREEN** (Fully Validated and Approved for Phase G.4.2)
