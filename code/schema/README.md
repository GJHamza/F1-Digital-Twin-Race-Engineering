# F1 Digital Twin — Schema V1 Specification & Validation

This directory contains the official Data Specification V1 and Schema Validation module for the **F1 Digital Twin** platform.

---

## 📄 Files

- **`schema_v1.json`**: Official JSON Schema Draft-07 definition for telemetry events.
- **`schema_validator.py`**: High-performance Python validation module wrapping `jsonschema.Draft7Validator`.

---

## 🎯 Architecture Data Flow

```
Digital Twin (simulation.js)
  │ (Emits Enriched V1 Telemetry Payload)
  ▼
Flask API (app.py)
  │ (Validates against schema_v1.json via schema_validator.py)
  ├───────────────────────────────┐
  │ [Valid V1 Payload]            │ [Invalid Payload]
  ▼                               ▼
Kafka Broker (f1_telemetry)     HTTP 400 Bad Request
  │                               (Rejected: No Kafka/Mongo writes)
  ▼
Data Engine Consumer (data_engine.py)
  │
  ▼
MongoDB Atlas (F1_Simulation)
```

---

## 🔑 Key Schema Requirements

### 1. Mandatory Top-Level Fields
- `schema_version`: String (`"1.0"`)
- `session_id`: String (e.g. `SES-a8f3-1742`)
- `event_id`: String (e.g. `EVT-17429302-942`)
- `car_id`: String (e.g. `SIM-CAR-01`)
- `timestamp`: String (ISO 8601 UTC)
- `telemetry`: Object containing required `speed`, `g_force`, `torque`, `pos_x`, `pos_z`
- `aerodynamics`: Object containing required `wind_speed`, `drag_coefficient`, `downforce`
- `tires`: Object containing required `tire_temp` (4 floats) and `tire_wear` (4 floats)

### 2. Optional Enriched Analytical Fields
- Identity: `car_name`, `team`, `driver_id`, `driver_name`
- Timing: `lap_number`, `lap_time_ms`, `sector_number`, `sector_time_ms`
- Driver: `throttle`, `brake`, `steering_angle`
- Powertrain: `rpm`, `gear`, `engine_temperature`, `engine_load`
- Aero/Environment: `drs_active`, `air_density`, `weather_state`, `track_condition`

---

## 🛡️ Validation & Error Behavior

1. **Flask Ingestion Guard**: Incoming `POST /telemetry` payloads are validated before any processing.
2. **Invalid Rejection**: Payloads failing schema validation return **HTTP 400 Bad Request** with a structured list of validation errors. Invalid payloads are **never** published to Kafka or inserted into MongoDB.
3. **Ping Fast-Path**: Diagnostic connection pings (`{"ping": true}`) bypass schema validation.

---

## 📌 Schema Versioning Strategy

- `schema_version` is fixed at `"1.0"`.
- **Minor Additions (v1.x)**: Optional fields can be added without breaking existing ingestion.
- **Major Changes (v2.0)**: Renaming or deleting required fields will increment the major version.
