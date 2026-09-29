# F1 Data Engineering ETL Foundation

**Package:** `code/etl`  
**Version:** `1.0.0`  

---

## 1. Overview & Architecture

The `code/etl` module implements the complete 3-tier Data Engineering Lakehouse architecture for the F1 Digital Twin:
```
[RAW JSONL Telemetry / Generator V2]
               │
               ▼
      ┌─────────────────┐
      │   BRONZE LAYER  │  Immutable Parquet raw events + technical metadata
      └────────┬────────┘  (partitioned by session_id & date)
               │
               ▼
      ┌─────────────────┐
      │   SILVER LAYER  │  Cleansed, typed, deduplicated, enriched telemetry
      └────────┬────────┘  + quarantine routing for invalid records
               │
               ▼
      ┌─────────────────┐
      │    GOLD LAYER   │  Aggregated Race Engineering analytical datasets
      └─────────────────┘  (lap, tire, fuel, aero, anomaly performance)
```

---

## 2. Layer Specifications

### A. Bronze Layer (`data/bronze/telemetry/`)
- **Format:** Parquet (Snappy compression).
- **Partitioning:** `session_id=.../date=YYYY-MM-DD/part-....parquet`.
- **Fields:** Preserves 100% of raw Schema V1 event fields without modifying physical telemetry values.
- **Added Technical Metadata:**
  - `ingestion_timestamp`: ISO-8601 UTC timestamp of ingestion.
  - `source`: Source component identifier (`synthetic_generator_v2`).
  - `pipeline_version`: Current ETL pipeline version (`1.0.0`).

### B. Silver Layer (`data/silver/telemetry/`)
- **Format:** Parquet.
- **Quality Filtering (`quality_rules.py`):** Rejects invalid payloads missing mandatory keys (`event_id`, `session_id`, `car_id`, `timestamp`), out-of-bound numerical variables (speed, rpm, throttle, brake, fuel), or invalid tire arrays (must contain exactly 4 values).
- **Quarantine Routing (`data/quarantine/telemetry/`):** Rejected records are stored with explicit `rejection_reason` and `rejected_at` fields.
- **Event Deduplication:** Deduplicates records by `event_id`.
- **Derived Engineering Metrics:**
  - `speed_ms`: `speed_kmh / 3.6`
  - `acceleration_estimate`: Numerical derivative $\Delta speed\_ms / \Delta t$ per session timeline.
  - `tire_temp_avg` / `tire_temp_max`: Average & maximum tire temperature across all 4 wheels.
  - `tire_wear_avg` / `tire_wear_max`: Average & maximum tire wear percentage across all 4 wheels.
  - `fuel_remaining_pct`: `(fuel_level / 110.0) * 100.0`
  - `aero_efficiency`: `downforce / ((speed_ms^2) * drag_coefficient + 1e-5)`
  - `tire_stress_index`: `(tire_temp_avg / 100) * (1 + tire_wear_avg / 100) * speed_ms`

### C. Gold Layer (`data/gold/`)
Analytical Parquet datasets optimized for Race Engineering & Future ML:
1. `data/gold/lap_performance`: Aggregated per `(session_id, car_id, lap_number)` -> `lap_time_ms`, `average_speed`, `max_speed`, `average_g_force`, `tire_temp_avg`, `tire_wear_avg`, `fuel_consumed`, `anomaly_count`.
2. `data/gold/tire_performance`: Aggregated per `(session_id, car_id, lap_number, compound)` -> `avg_tire_temp`, `max_tire_temp`, `tire_wear_delta`, `tire_stress`.
3. `data/gold/fuel_performance`: Aggregated per `(session_id, car_id)` -> `starting_fuel`, `ending_fuel`, `fuel_consumed`, `avg_consumption_per_lap`.
4. `data/gold/aero_performance`: Aggregated per `(session_id, car_id, lap_number)` -> `average_speed`, `average_downforce`, `drag_coefficient`, `aero_efficiency`, `wind_speed`.
5. `data/gold/anomaly_summary`: Aggregated per `(session_id, car_id, lap_number, anomaly_type, severity)` -> `anomaly_count`, `first_occurrence`, `last_occurrence`.

---

## 3. Command Line Interface (CLI)

Run the full pipeline end-to-end:
```bash
python -m code.etl.pipeline --input data/generated/medium.jsonl --output data/processed --all
```

Run specific layers:
```bash
# Execute Bronze layer only
python -m code.etl.pipeline --input data/generated/medium.jsonl --layer bronze

# Execute Silver layer only
python -m code.etl.pipeline --layer silver

# Execute Gold layer only
python -m code.etl.pipeline --layer gold
```

---

## 4. Idempotency & Quality Assurance
- **Deterministic Transformations:** Running the pipeline multiple times over identical input data produces identical Parquet datasets and partition structures.
- **Deduplication:** Unique `event_id` constraints prevent double-counting of telemetry records across executions.

---

## 5. Future Extensibility Roadmap
- **MinIO / S3 Storage Migration:** Local paths (`data/bronze/`) are abstraction-wrapped so changing to object storage endpoints (`s3a://f1-telemetry/bronze/`) requires zero code changes.
- **Kafka Streaming Integration:** Micro-batch streaming writes can feed directly into Bronze Parquet writer.
- **Feature Store for ML:** Gold datasets (`lap_performance`, `tire_performance`) provide ready-to-train feature tables for tire degradation, pit strategy, and anomaly detection ML models.
