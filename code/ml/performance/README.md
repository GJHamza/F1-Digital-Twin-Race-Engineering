# ML Performance Prediction — Phase G.4.3

## Overview

The `code/ml/performance/` package implements **Phase G.4.3: Lap Time / Performance Prediction** for the F1 Digital Twin — Race Engineering Platform.

It provides a supervised machine learning regression pipeline designed to predict lap times (`lap_time_sec`) from pre-lap telemetry aggregations and rolling historical performance metrics.

---

## Package Structure

```
code/ml/performance/
├── __init__.py          # Entry point and package exports
├── config.py            # PerformanceConfig paths, splits, and feature definitions
├── target.py            # construct_lap_target_dataset() lap-level aggregation
├── features.py          # compute_pre_lap_features() pre-lap telemetry & temporal features
├── preprocessing.py     # Chronological 70/15/15 split & Train-only StandardScaler
├── baseline.py          # MeanBaselineModel & PreviousLapBaselineModel
├── models.py            # PerformanceRegressionModel (RandomForest & GradientBoosting)
├── evaluation.py        # calculate_metrics() and evaluate_regression_models()
├── predictor.py         # run_performance_prediction_pipeline() orchestrator
└── README.md            # Module documentation
```

---

## Key Methodology

### 1. Target Construction (`target.py`)
Groups Silver telemetry ticks by `(session_id, car_id, lap_number)` and calculates exact lap duration:
$$\text{lap\_time\_sec} = t_{\text{end}} - t_{\text{start}} > 0$$

### 2. Feature Engineering & Zero Leakage (`features.py`)
Features are computed strictly using telemetry from preceding completed laps ($1, \dots, L-1$) or initial lap conditions ($L=1$).
- **Performance**: `average_speed_before_lap`, `max_speed_before_lap`, `average_acceleration_before_lap`, `average_g_force_before_lap`
- **Tyres**: `tire_temp_avg_before_lap`, `tire_temp_max_before_lap`, `tire_wear_avg_before_lap`, `tire_wear_max_before_lap`, `tire_stress_index_before_lap`, `tire_wear_rate_before_lap`
- **Aerodynamics**: `average_downforce_before_lap`, `average_drag_coefficient_before_lap`, `average_wind_speed_before_lap`, `average_aero_efficiency_before_lap`
- **Powertrain**: `average_rpm_before_lap`, `average_torque_before_lap`, `estimated_power_kw_before_lap`, `fuel_remaining_pct_before_lap`
- **Temporal / Historic**: `previous_lap_time_sec`, `rolling_lap_time_mean`, `rolling_lap_time_std`, `elapsed_session_time_sec`

### 3. Chronological Temporal Splitting (`preprocessing.py`)
- **Train**: First 70% of chronological laps
- **Validation**: Next 15% of chronological laps
- **Test**: Final 15% of chronological laps
- `StandardScaler` fitted **strictly on TRAIN**.

### 4. Regression Models & Selection (`models.py`, `evaluation.py`)
- **Baselines**: Mean Baseline & Previous-Lap Baseline
- **ML Regressors**: `RandomForestRegressor(n_estimators=100, random_state=42)` & `GradientBoostingRegressor(n_estimators=100, random_state=42)`
- Model selection performed strictly on **Validation MAE/RMSE**.

---

## Quick Start

```python
from ml.performance.predictor import run_performance_prediction_pipeline

# Execute end-to-end pipeline
report = run_performance_prediction_pipeline()

print(f"Best Model: {report['best_model_name']}")
print(report["comparison_table"])
```
