# F1 Digital Twin — Synthetic Data Generator V2

> **Important Disclaimer**: This generator produces synthetic engineering telemetry for development, analytics and machine learning experimentation. It is not official Formula 1 telemetry.

---

## 🏗️ Architecture & Package Layout

```
code/data_generator/
├── __init__.py           # Package version & init
├── config.json           # Vehicle profiles & track geometry config
├── scenarios.py          # Scenario registry & definitions (15 scenarios)
├── physics_model.py      # Deterministic synthetic physics functions
├── anomaly_model.py      # Controlled anomaly trigger model
├── generator_v2.py       # Generator engine & CLI interface
└── README.md             # Technical documentation
```

---

## 🏎️ Scenario Engine

The generator provides 15 deterministic scenarios:

1. **`QUALIFYING_DRY`**: High speed qualifying run with low fuel (15kg) and SOFT compound.
2. **`RACE_DRY`**: Standard dry race stint with MEDIUM compound.
3. **`LONG_STINT`**: Extended race stint on HARD compound with fuel consumption and wear escalation.
4. **`LOW_FUEL`**: Ultra-light vehicle mass stint (8kg fuel) near stint end.
5. **`HIGH_FUEL`**: Full fuel tank race start simulation (110kg fuel).
6. **`HOT_TRACK`**: Extreme thermal track environment (38°C air, 52°C track).
7. **`COLD_TRACK`**: Low temperature track conditions (12°C air, 16°C track).
8. **`LIGHT_RAIN`**: Light rain stint on INTERMEDIATE tires (35% rain intensity).
9. **`HEAVY_RAIN`**: Heavy rain stint on WET tires (85% rain intensity).
10. **`DRY_TO_WET`**: Dynamic weather transition from dry track to heavy rain mid-session.
11. **`WET_TO_DRY`**: Dynamic weather transition from wet track to drying line mid-session.
12. **`TIRE_OVERHEAT`**: Controlled tire thermal overload anomaly test.
13. **`ENGINE_OVERHEAT`**: Controlled engine coolant overheating anomaly test.
14. **`BRAKE_STRESS`**: Controlled brake stress & deceleration test.
15. **`AERO_ANOMALY`**: Controlled aerodynamic drag anomaly test.

---

## ⚙️ Physics & Engineering Model

- **Vehicle Mass**: $M_{total} = M_{base} + M_{fuel}$ (mass decreases as fuel is consumed).
- **Powertrain**: Gear (0 to 8) and RPM (1000 to 15,000 RPM) derived deterministically from vehicle speed and throttle input.
- **Aerodynamics**: Drag $C_d$ and Downforce $F_{downforce}$ scale quadratically ($v^2$) with relative airspeed.
- **Tire Dynamics**: 4 wheel array `[FL, FR, RL, RR]` with compound-specific wear rates, thermal convergence, and temperature-pressure scaling.
- **Fuel Consumption**: Monotonically decreasing fuel level and monotonically increasing fuel used.

---

## 🚨 Anomaly Model

Supported controlled anomalies:
- **`TIRE_OVERHEAT`**: Front tire temperatures exceed 110°C, accelerating wear.
- **`ENGINE_OVERHEAT`**: Engine coolant temperature exceeds 120°C.
- **`BRAKE_STRESS`**: Emergency deceleration load exceeds 4.5G.
- **`AERO_ANOMALY`**: Unintended drag coefficient spike ($+0.12 C_d$).

Every anomaly sets `anomaly_flag: true` and populates `active_anomalies` with structured metadata.

---

## 💻 CLI Usage

### List All Available Scenarios
```bash
python code/data_generator/generator_v2.py --list-scenarios
```

### Generate a Dataset
```bash
python code/data_generator/generator_v2.py \
    --scenario RACE_DRY \
    --sessions 2 \
    --laps 5 \
    --seed 42 \
    --output data/generated/race_dry.jsonl
```

---

## 🔒 Schema V1 Validation

Every generated event is validated against `code/schema/schema_v1.json` via `validate_telemetry()`. Invalid events are rejected immediately to guarantee 100% data contract compliance.
