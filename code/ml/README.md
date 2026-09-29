# F1 Digital Twin — Feature Engineering & ML Package (`code/ml/`)

## Overview

The `code/ml/` package provides a production-grade, reproducible machine learning pipeline for the F1 Digital Twin platform:
1. **Feature Engineering & ML Dataset Foundation (`code/ml/`)**: Transforms cleansed Silver telemetry Parquet data into validated Machine Learning datasets, cleanly partitioned by time into **Train**, **Validation**, and **Test** sets.
2. **Telemetry Anomaly Detection (`code/ml/anomaly/`)**: Implements statistical Z-Score baseline detection, Scikit-learn Isolation Forest unsupervised anomaly modeling, severity calibration (`NORMAL`, `LOW`, `MEDIUM`, `HIGH`), and top signal contribution explainability.

---

## Directory Structure

```
code/ml/
├── __init__.py          # Package initialization
├── config.py            # Centralized ML configuration & schema definitions
├── schema.py            # Physical feature bounds & quality tolerance specifications
├── features/            # Feature extraction modules
│   ├── __init__.py
│   ├── performance.py   # Speed, acceleration estimates, G-force
│   ├── tyres.py         # Tire temperature, wear, stress index, wear rate
│   ├── aerodynamics.py  # Downforce, drag, aero efficiency, downforce/speed
│   ├── powertrain.py    # RPM, torque, torque/rpm, estimated power (kW), fuel
│   └── temporal.py      # Elapsed time, lag-safe 5-step rolling statistics
├── dataset/             # Dataset generation & validation
│   ├── __init__.py
│   ├── builder.py       # End-to-end dataset builder orchestrator
│   ├── validation.py    # Quality auditor (bounds, nulls, duplicates, monotonicity)
│   └── split.py         # Temporal split engine (70% Train / 15% Val / 15% Test)
├── anomaly/             # Telemetry Anomaly Detection Engine (G.4.2)
│   ├── __init__.py
│   ├── config.py        # Anomaly detection configuration & severity quantiles
│   ├── preprocessing.py # StandardScaler fit strictly on Train
│   ├── baseline.py      # Z-score statistical baseline detector
│   ├── isolation_forest.py # Sklearn IsolationForest model wrapper
│   ├── scoring.py       # Normalized [0, 1] scoring & severity mapping (NORMAL, LOW, MEDIUM, HIGH)
│   ├── explain.py       # Top contributing signal deviation calculator
│   └── detector.py      # End-to-end anomaly detection orchestrator
└── README.md            # Technical documentation
```

---

## Feature Taxonomy & Formulas

| Feature Category | Feature Name | Source Fields | Formula / Description | Unit |
| :--- | :--- | :--- | :--- | :--- |
| **Performance** | `speed_kmh` | `speed` | Vehicle speed in kilometers per hour | km/h |
| **Performance** | `speed_ms` | `speed_kmh` | `speed_kmh / 3.6` | m/s |
| **Performance** | `acceleration_estimate` | `speed_ms` | `Δ(speed_ms)` per time step per session | m/s² |
| **Performance** | `g_force` | `g_force` | Resultant g-force | g |
| **Tyres** | `tire_temp_avg` | `tires.tire_temp` | Average tire temperature across 4 wheels | °C |
| **Tyres** | `tire_temp_max` | `tires.tire_temp` | Maximum tire temperature among 4 wheels | °C |
| **Tyres** | `tire_wear_avg` | `tires.tire_wear` | Average tire wear across 4 wheels | % |
| **Tyres** | `tire_wear_max` | `tires.tire_wear` | Maximum tire wear among 4 wheels | % |
| **Tyres** | `tire_stress_index` | `temp_avg, wear_avg, speed_ms` | `(temp_avg / 100) * (1 + wear_avg / 100) * speed_ms` | — |
| **Tyres** | `tire_wear_rate` | `tire_wear_avg` | `max(0, Δ(tire_wear_avg))` per step | %/step |
| **Aerodynamics** | `downforce` | `aerodynamics.downforce` | Aerodynamic downforce generated | N |
| **Aerodynamics** | `drag_coefficient` | `aerodynamics.drag_coefficient` | Aerodynamic drag coefficient ($C_d$) | — |
| **Aerodynamics** | `wind_speed` | `aerodynamics.wind_speed` | Ambient wind speed | km/h |
| **Aerodynamics** | `aero_efficiency` | `downforce, speed_ms, drag` | `downforce / ((speed_ms²) * drag + 1e-5)` | — |
| **Aerodynamics** | `downforce_per_speed` | `downforce, speed_ms` | `downforce / (speed_ms + 1e-5)` | N/(m/s) |
| **Powertrain** | `rpm` | `telemetry.rpm` | Engine revolutions per minute | RPM |
| **Powertrain** | `torque` | `telemetry.torque` | Engine torque output | Nm |
| **Powertrain** | `torque_per_rpm` | `torque, rpm` | `torque / (rpm + 1.0)` | Nm/RPM |
| **Powertrain** | `estimated_power_kw` | `torque, rpm` | `(torque * rpm) / 9548.8` | kW |
| **Powertrain** | `fuel_level` | `fuel_level` | Fuel mass remaining | kg |
| **Powertrain** | `fuel_remaining_pct` | `fuel_level` | `(fuel_level / 110.0) * 100` | % |
| **Temporal** | `elapsed_time_sec` | `timestamp` | Time elapsed since session start | s |
| **Temporal** | `rolling_speed_mean_5` | `speed_kmh` | Backward-looking 5-step rolling mean speed | km/h |
| **Temporal** | `rolling_speed_std_5` | `speed_kmh` | Backward-looking 5-step rolling std speed | km/h |
| **Temporal** | `rolling_tire_temp_5` | `tire_temp_avg` | Backward-looking 5-step rolling mean tire temp | °C |
| **Temporal** | `rolling_tire_wear_5` | `tire_wear_avg` | Backward-looking 5-step rolling mean tire wear | % |

---

## Anomaly Detection & Severity Mapping

- **Preprocessing & Fit**: `StandardScaler` and `IsolationForest` fit **strictly on Train** partition (`contamination=0.05`, `random_state=42`).
- **Severity Calibration**: Score quantiles ($90^{\text{th}}$, $95^{\text{th}}$, $99^{\text{th}}$ percentiles) calibrated on **Validation** partition.
- **Severity Levels**:
  - `NORMAL`: Anomaly score $< 90^{\text{th}}$ percentile
  - `LOW`: Anomaly score $\ge 90^{\text{th}}$ and $< 95^{\text{th}}$ percentile
  - `MEDIUM`: Anomaly score $\ge 95^{\text{th}}$ and $< 99^{\text{th}}$ percentile
  - `HIGH`: Anomaly score $\ge 99^{\text{th}}$ percentile
- **Explainability**: Top 3 contributing signals identified per anomaly using Z-score deviation relative to Train baseline.

---

## Usage Examples

### 1. Build ML Feature Dataset
```python
from ml.config import MLConfig
from ml.dataset.builder import build_ml_dataset

config = MLConfig(storage_backend="local")
summary = build_ml_dataset(config)

print(f"Total Records: {summary['total_records']}")
print(f"Features: {summary['feature_count']}")
print(f"Train/Val/Test: {summary['train_count']} / {summary['val_count']} / {summary['test_count']}")
```

### 2. Run Telemetry Anomaly Detection
```python
from ml.anomaly.config import AnomalyConfig
from ml.anomaly.detector import detect_telemetry_anomalies

anomaly_config = AnomalyConfig(storage_backend="local")
res = detect_telemetry_anomalies(anomaly_config)

print(f"Total Records: {res['total_records']}")
print(f"Isolation Forest Anomalies: {res['anomaly_count']} ({res['anomaly_rate']:.2%})")
print(f"Severities: {res['severities']}")
```
