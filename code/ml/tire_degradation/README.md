# ML Tire Degradation Modeling — Phase G.4.4

## Overview

The `code/ml/tire_degradation/` package implements **Phase G.4.4: Tire Degradation Modeling** for the F1 Digital Twin — Race Engineering Platform.

It provides a multi-output machine learning regression pipeline designed to predict future tire wear degradation deltas ($\Delta \text{wear}_h(t)$) over a configurable horizon $H = 10$ telemetry observations across all four wheel positions (**FL**, **FR**, **RL**, **RR**).

---

## Package Structure

```
code/ml/tire_degradation/
├── __init__.py          # Package entry point and exports
├── config.py            # Storage paths, DEFAULT_HORIZON_STEPS=10, 4-wheel targets, and feature lists
├── inspection.py        # inspect_tire_telemetry() pre-implementation checks
├── dataset.py           # construct_tire_degradation_dataset() pairing t with t+H
├── features.py          # compute_tire_degradation_features() 4-wheel pre-horizon features
├── preprocessing.py     # Chronological 70/15/15 split & Train-only StandardScaler
├── baseline.py          # ZeroDegradationBaseline & PreviousDegradationBaseline
├── models.py            # TireDegradationModel (RandomForest & GradientBoosting multi-output)
├── evaluation.py        # calculate_tire_metrics() per wheel & validate_physical_bounds()
├── predictor.py         # run_tire_degradation_pipeline() orchestrator
└── README.md            # Package documentation
```

---

## Key Methodology

### 1. Target Formulation ($H = 10$ Steps)
For each telemetry observation $t$ and each wheel position $w \in \{\text{FL}, \text{FR}, \text{RL}, \text{RR}\}$ within session boundaries:
$$\Delta \text{wear}_{h, w}(t) = \text{wear}_w(t + H) - \text{wear}_w(t)$$

Observations in the last $H$ steps of a session without a $t+H$ future match are excluded safely with documented reasons.

### 2. Four-Wheel Granularity & Features
Maintains individual wheel states (**FL**, **FR**, **RL**, **RR**) without premature averaging:
- **Tire State**: `tire_wear_fl`, `tire_wear_fr`, `tire_wear_rl`, `tire_wear_rr`, `tire_temp_fl`, `tire_temp_fr`, `tire_temp_rl`, `tire_temp_rr`, `tire_wear_avg`, `tire_wear_max`, `tire_temp_avg`, `tire_temp_max`, `tire_stress_index`, `tire_wear_rate`
- **Dynamics**: `speed_kmh`, `speed_ms`, `acceleration_estimate`, `g_force`
- **Aerodynamics**: `downforce`, `drag_coefficient`, `wind_speed`, `aero_efficiency`
- **Powertrain**: `rpm`, `torque`, `estimated_power_kw`, `fuel_remaining_pct`
- **Temporal / Historic**: `elapsed_time_sec`, `previous_wear_delta_fl`, `previous_wear_delta_fr`, `previous_wear_delta_rl`, `previous_wear_delta_rr`

### 3. Chronological Temporal Splitting
- **Train (70%)** / **Validation (15%)** / **Test (15%)** strictly chronological (`shuffle=False`).
- `StandardScaler` fitted **strictly on TRAIN**.

### 4. Models & Selection
- **Baselines**: Zero Degradation (`delta = 0`) & Previous Degradation Extrapolation
- **ML Models**: Multi-Output `RandomForestRegressor` & Multi-Output `GradientBoostingRegressor`
- Model selection performed strictly on **Validation MAE Global**.

---

## Quick Start

```python
from ml.tire_degradation.predictor import run_tire_degradation_pipeline

# Run end-to-end pipeline with default H=10
report = run_tire_degradation_pipeline()

print(f"Best Model: {report['best_model_name']}")
print(report["comparison_table"])
```
