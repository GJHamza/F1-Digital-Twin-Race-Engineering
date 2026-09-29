# Storage Module — MongoDB Architecture & Offline Ingestion Pipeline

**Package:** `code/storage`  
**Version:** `1.0.0`  
**Database Name:** `F1_Simulation`  

---

## 1. Overview
The storage module implements the official three-collection MongoDB architecture specified in **Phase G.1**:
1. `sessions` — 1 document per simulation session.
2. `telemetry` — 1 document per Schema V1 telemetry event.
3. `anomalies` — 1 document per active telemetry anomaly event.

It provides a high-performance, idempotent offline bulk ingestion engine (`TelemetryIngestor`) that validates incoming data against Schema V1, derives session and anomaly metadata, and prevents duplicate insertions without modifying historical legacy data.

---

## 2. Collections & Document Models

### A. `sessions` Collection
Stores top-level session metadata.
```json
{
  "session_id": "SES-DRY-2026-0001",
  "car_id": "SIM-CAR-01",
  "team": "Scuderia Ferrari",
  "driver_id": "LEC-16",
  "session_type": "RACE",
  "created_at": "2026-09-21T23:55:00.000Z",
  "started_at": "2026-09-21T23:55:00.000Z",
  "ended_at": "2026-09-21T23:56:00.000Z",
  "laps_completed": 20,
  "scenario": "RACE_DRY",
  "schema_version": "1.0"
}
```

### B. `telemetry` Collection
Stores complete, un-flattened Schema V1 telemetry events.
```json
{
  "schema_version": "1.0",
  "session_id": "SES-DRY-2026-0001",
  "event_id": "EVT-8f92a1bc-341d-48ef-b209-901b238d451a",
  "car_id": "SIM-CAR-01",
  "timestamp": "2026-09-21T23:55:00.000Z",
  "lap_number": 1,
  "sector_number": 1,
  "throttle": 100.0,
  "brake": 0.0,
  "fuel_level": 110.0,
  "telemetry": {
    "speed": 320.5,
    "rpm": 14200,
    "gear": 8,
    "torque": 620.0,
    "engine_temperature": 98.5,
    "engine_load": 95.0
  },
  "aerodynamics": {
    "wind_speed": 12.0,
    "drag_coefficient": 0.35,
    "downforce": 12500.0
  },
  "tires": {
    "tire_temp": [95.0, 95.0, 96.0, 96.0],
    "tire_wear": [2.1, 2.1, 2.2, 2.2],
    "tire_pressure": [1.45, 1.45, 1.45, 1.45]
  }
}
```

### C. `anomalies` Collection
Stores lightweight references to active system anomalies.
```json
{
  "schema_version": "1.0",
  "session_id": "SES-DRY-2026-0001",
  "event_id": "EVT-8f92a1bc-341d-48ef-b209-901b238d451a",
  "car_id": "SIM-CAR-01",
  "timestamp": "2026-09-21T23:55:00.000Z",
  "severity": "HIGH",
  "anomaly_type": "TIRE_OVERHEAT",
  "description": "Tire temperature exceeded safety threshold (+35.0°C)",
  "active": true
}
```

---

## 3. Database Indexes

Required indexes are initialized idempotently via `ensure_indexes(db)`:

| Collection | Index Fields | Unique | Sparse | Purpose |
| :--- | :--- | :---: | :---: | :--- |
| `telemetry` | `{ session_id: 1, timestamp: 1 }` | No | No | Session timeline queries |
| `telemetry` | `{ car_id: 1, timestamp: -1 }` | No | No | Latest telemetry lookup |
| `telemetry` | `{ event_id: 1 }` | **Yes** | **Yes** | Idempotent event deduplication |
| `sessions` | `{ session_id: 1 }` | **Yes** | No | Primary session lookup |
| `sessions` | `{ created_at: -1 }` | No | No | Recent sessions sorting |
| `anomalies` | `{ session_id: 1, severity: 1 }` | No | No | Severity alert filtering |
| `anomalies` | `{ session_id: 1, event_id: 1 }` | **Yes** | **Yes** | Anomaly deduplication |

---

## 4. Ingestion Pipeline & Idempotency

### Workflow
1. **Schema Validation:** Incoming payloads are validated against `Schema V1`. Any invalid payload is immediately **REJECTED** and logged.
2. **Session Derivation:** Groups valid events by `session_id`, derives time bounds (`started_at`, `ended_at`) and `laps_completed`, and upserts into `sessions`.
3. **Anomaly Extraction:** Filters events where `anomaly_flag == True`, extracts anomaly details, and upserts into `anomalies`.
4. **Bulk Idempotent Telemetry Upsert:** Telemetry documents are upserted using `$setOnInsert` on `event_id`. Re-ingesting identical files skips existing documents without error.

---

## 5. Legacy Coexistence & Production Safety

- **Legacy Telemetry:** Historical documents created during Phase A–D (without `event_id` or nested fields) remain untouched in `telemetry`.
- **Collection Safety:** Existing collections (`car_settings`, legacy data) are preserved without dropping or renaming.
- **Production Isolation:** Unit tests run against isolated mock database instances to ensure production Atlas is never mutated during automated test execution.
