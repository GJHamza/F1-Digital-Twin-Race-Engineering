# PHASE G.3.2 REPORT — DATA LAKE (MINIO + S3A + PYSPARK / PYARROW)

**Project:** F1 Digital Twin — Race Engineering Platform  
**Date:** September 22, 2026  
**Status:** **GREEN (VALIDATED)**  
**Target Storage Backend:** MinIO Object Storage (`s3a://f1-data-lake/`)  
**Pipeline Integration:** Dual Backend Support (`ETL_STORAGE_BACKEND=local|minio`)

---

## 1. Objective

Phase G.3.2 introduces a enterprise-grade **Object Storage Data Lake** using **MinIO**, **S3A protocol**, and **PySpark / PyArrow S3FileSystem connectors**.

This phase establishes:
- MinIO Object Storage infrastructure deployed via Docker Compose with volume persistence.
- S3 Bucket `f1-data-lake` storing partitioned **Bronze**, cleansed **Silver**, analytical **Gold**, and **Quarantine** datasets.
- Dual storage abstraction supporting both local filesystem and cloud object storage transparently.
- Real empirical benchmarking comparing Local Filesystem vs MinIO S3A performance across **SMALL** (1,500 events), **MEDIUM** (60,000 events), and **LARGE** (600,000 events) scale datasets.
- Persistence and non-regression validation (71/71 tests passing).

---

## 2. Existing Infrastructure

Prior to Phase G.3.2, the validated architecture comprised:
- **G.1**: Data Specification V1
- **G.2.1**: Schema V1 Implementation & Validation
- **G.2.2**: Synthetic Telemetry Generator V2
- **G.2.3**: Dataset Quality & Statistical Audit
- **G.2.4**: MongoDB Telemetry Data Architecture (Operational OLTP Store)
- **G.3.1**: Data Engineering ETL Foundation (Local Parquet Filesystem)

Phase G.3.2 extends G.3.1 by introducing object storage capabilities without modifying operational MongoDB Atlas data or adding Machine Learning models.

---

## 3. MinIO Configuration

MinIO is deployed as a dedicated Docker container service in `docker-compose.yml`:

```yaml
services:
  minio:
    image: quay.io/minio/minio:latest
    container_name: f1-minio
    restart: always
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    command: server /data --console-address ":9001"
    volumes:
      - minio-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  minio-data:
    driver: local
```

- **API Endpoint:** `http://localhost:9000`
- **Web Console:** `http://localhost:9001`
- **Credentials:** Configured in `.env` (`MINIO_ROOT_USER=minioadmin`, `MINIO_ROOT_PASSWORD=minioadmin`)
- **Persistence:** Docker named volume `minio-data` mapping to `/data`.

---

## 4. Bucket Architecture

Bucket `f1-data-lake` logical structure:

```
s3a://f1-data-lake/
│
├── bronze/
│   └── telemetry/
│       ├── session_id=SES-RACE-001/date=2026-09-22/part-0.parquet
│       └── ...
│
├── silver/
│   └── telemetry/
│       ├── session_id=SES-RACE-001/date=2026-09-22/part-0.parquet
│       └── ...
│
├── gold/
│   ├── lap_performance/lap_performance.parquet
│   ├── tire_performance/tire_performance.parquet
│   ├── fuel_performance/fuel_performance.parquet
│   ├── aero_performance/aero_performance.parquet
│   └── anomaly_summary/anomaly_summary.parquet
│
└── quarantine/
    └── telemetry/part-0.parquet
```

---

## 5. S3A Configuration & PyArrow Integration

The storage abstraction module `code/datalake/s3_client.py` uses PyArrow's C++ native `pyarrow.fs.S3FileSystem`:

```python
s3_fs = pafs.S3FileSystem(
    access_key="minioadmin",
    secret_key="minioadmin",
    endpoint_override="localhost:9000",
    scheme="http",
    allow_bucket_creation=True,
    allow_bucket_deletion=True
)
```

S3 URIs (`s3a://f1-data-lake/...`) are parsed and routed to MinIO S3FileSystem directly, providing high-speed Parquet write and read operations.

---

## 6. Spark / Hadoop Compatibility

- **PyArrow Version:** `24.0.0`
- **PySpark Support:** Compatible with PySpark `3.5.x` S3A Hadoop configuration:
  - `fs.s3a.endpoint`: `http://localhost:9000`
  - `fs.s3a.access.key`: `minioadmin`
  - `fs.s3a.secret.key`: `minioadmin`
  - `fs.s3a.path.style.access`: `true`
  - `fs.s3a.connection.ssl.enabled`: `false`
  - `fs.s3a.impl`: `org.apache.hadoop.fs.s3a.S3AFileSystem`

---

## 7. Bronze Integration

Updated `code/etl/bronze/bronze_writer.py`:
- Ingests raw JSONL files, lists of events, or S3 URIs.
- Attaches technical ingestion metadata (`ingestion_timestamp`, `source`, `pipeline_version`, `date`).
- Serializes nested JSON objects (`telemetry_json`, `aerodynamics_json`, `tires_json`, `active_anomalies_json`).
- Writes partitioned Parquet files by `session_id` and `date` to `s3a://f1-data-lake/bronze/telemetry/`.

---

## 8. Silver Integration

Updated `code/etl/silver/silver_transformer.py`:
- Reads raw Bronze Parquet data from `s3a://f1-data-lake/bronze/telemetry/`.
- Executes G.3.1 quality validation rules and routes invalid records to `s3a://f1-data-lake/quarantine/telemetry/`.
- Performs `event_id` deduplication.
- Computes derived race engineering metrics (`speed_ms`, `tire_temp_avg`, `tire_wear_avg`, `aero_efficiency`, `tire_stress_index`, `acceleration_estimate`).
- Writes partitioned Silver Parquet data to `s3a://f1-data-lake/silver/telemetry/`.

---

## 9. Gold Integration

Updated `code/etl/gold/gold_builder.py`:
- Reads Silver Parquet data from `s3a://f1-data-lake/silver/telemetry/`.
- Computes 5 analytical datasets:
  1. `lap_performance`: Lap duration, avg/max speed, G-force, fuel consumed, anomaly counts.
  2. `tire_performance`: Compound, thermal max/avg, wear delta, tire stress index.
  3. `fuel_performance`: Fuel consumption per session & lap.
  4. `aero_performance`: Downforce vs drag efficiency at speed.
  5. `anomaly_summary`: High-level anomaly type and severity aggregations.
- Writes 5 Parquet datasets under `s3a://f1-data-lake/gold/`.

---

## 10. Partitioning Strategy

- **Bronze & Silver:** Partitioned by `session_id` and `date` (`session_id=.../date=.../`).
- **Gold:** Partitioned logically by dataset subfolder (`gold/<dataset_name>/`).
- **Rationale:** Avoids high-cardinality over-partitioning by `event_id`, which would generate excessive small files. Maintains balanced 1MB-10MB Parquet block sizes.

---

## 11. Data Integrity Verification

Executed record count integrity comparison between local execution and MinIO S3A execution:

- **Local Bronze Count:** `60,000` records $\leftrightarrow$ **MinIO Bronze Count:** `60,000` records (**100% Match**)
- **Local Silver Count:** `60,000` records $\leftrightarrow$ **MinIO Silver Count:** `60,000` records (**100% Match**)
- **Local Gold Lap Count:** `1,000` records $\leftrightarrow$ **MinIO Gold Lap Count:** `1,000` records (**100% Match**)
- **Local Gold Fuel Count:** `50` records $\leftrightarrow$ **MinIO Gold Fuel Count:** `50` records (**100% Match**)

---

## 12. Persistence Verification

1. Container started (`docker compose up -d`).
2. Executed full pipeline on 60,000 events (`s3a://f1-data-lake/`).
3. Stopped and removed container (`docker compose down`).
4. Re-launched container (`docker compose up -d`).
5. Queried MinIO S3 bucket: **60,000 records successfully read back from volume `minio-data`**.

---

## 13. Local vs MinIO S3A Benchmark Results

Empirical benchmark execution comparing **Local Filesystem** vs **MinIO S3A Object Storage**:

| Backend | Dataset | Events | Bronze (s) | Silver (s) | Gold (s) | Total (s) | Throughput (evt/s) |
|---|---|---|---|---|---|---|---|
| **LOCAL** | SMALL | 1,500 | 0.157s | 0.427s | 0.223s | 0.807s | **1,858.74** |
| **MINIO S3A** | SMALL | 1,500 | 0.440s | 0.717s | 0.736s | 1.893s | **792.39** |
| **LOCAL** | MEDIUM | 60,000 | 4.156s | 12.085s | 5.442s | 21.683s | **2,767.14** |
| **MINIO S3A** | MEDIUM | 60,000 | 5.494s | 11.898s | 4.491s | 21.883s | **2,741.85** |
| **LOCAL** | LARGE | 600,000 | 51.381s | 137.056s | 47.129s | 235.566s | **2,547.06** |
| **MINIO S3A** | LARGE | 600,000 | 62.802s | 142.828s | 46.037s | 251.667s | **2,384.10** |

### Benchmark Analysis
- On **SMALL** workloads, network protocol overhead makes MinIO ~2.3x slower than direct local SSD IO.
- On **MEDIUM** (60k) and **LARGE** (600k) workloads, S3A object storage throughput scales efficiently, achieving **2,384 – 2,742 events/sec**, within **~6.8%** overhead of raw local filesystem IO.

---

## 14. SMALL Dataset Results (1,500 events)
- **Ingestion Time:** 0.440s
- **Transformation Time:** 0.717s
- **Gold Build Time:** 0.736s
- **Total:** 1.893s (**PASS**)

---

## 15. MEDIUM Dataset Results (60,000 events)
- **Ingestion Time:** 5.494s
- **Transformation Time:** 11.898s
- **Gold Build Time:** 4.491s
- **Total:** 21.883s (**PASS**)

---

## 16. LARGE Dataset Results (600,000 events)
- **Ingestion Time:** 62.802s
- **Transformation Time:** 142.828s
- **Gold Build Time:** 46.037s
- **Total:** 251.667s (~4.1 min) (**PASS**)

---

## 17. Tests Suite Integration

New integration test files created:
- `tests/test_minio.py`: MinIO service health, bucket verification, S3FileSystem instantiation.
- `tests/test_s3a.py`: Minimal S3A Write, Read, Count, Schema validation.
- `tests/test_datalake.py`: End-to-end Data Lake pipeline test, Local vs MinIO parity.

---

## 18. Non-Regression Verification

Ran full test suite via `pytest`:

```
======================= 71 passed, 8 warnings in 14.56s =======================
```

- **Previous Test Suite:** 65/65 PASS
- **New G.3.2 Integration Tests:** 6/6 PASS
- **Total Test Suite:** **71/71 PASS (100%)**

---

## 19. Problems Encountered & Resolutions

1. **Docker Hub Rate Limit on `minio/minio:latest`:**
   - *Resolution:* Switched to officialquay registry image `quay.io/minio/minio:latest` in `docker-compose.yml`.
2. **Windows Backslash Path Formatting in S3 URIs:**
   - *Resolution:* Enhanced `parse_s3_uri()` and `pipeline.py` to normalize backslashes (`\`) to forward slashes (`/`) for all S3 URIs.
3. **Windows `cp1252` Console Emoji Encoding Error:**
   - *Resolution:* Replaced unicode emoji in `pipeline.py` stdout output with standard ASCII `[SUCCESS]`.

---

## 20. Limitations

- **Streaming Ingestion:** MinIO currently operates on micro-batch JSONL/Parquet files. Real-time sub-second streaming from Kafka to MinIO is reserved for Phase G.3.3+.
- **Spark Distributed Cluster Mode:** Current setup uses PyArrow/PySpark local worker mode.

---

## 21. Future Architecture Alignment (Phase G.3.3+)

- Integration with **Kafka Connect S3 Sink / PySpark Streaming** for streaming ingestion into Bronze MinIO.
- Feature Store integration for Machine Learning model training in Phase G.4.

---

## 22. Summary Validation Table

| Validation Criteria | Result | Notes |
|---|---|---|
| MinIO | **PASS** | Container running on ports 9000/9001 (healthy) |
| Bucket | **PASS** | `f1-data-lake` bucket verified & created |
| S3A WRITE | **PASS** | PyArrow S3FileSystem writes Parquet directly to S3A |
| S3A READ | **PASS** | PyArrow ParquetDataset reads from S3A |
| Bronze | **PASS** | Ingests raw JSONL to `s3a://f1-data-lake/bronze/` |
| Silver | **PASS** | Cleanses & enriches to `s3a://f1-data-lake/silver/` |
| Gold | **PASS** | Builds 5 analytical datasets under `s3a://f1-data-lake/gold/` |
| Partitioning | **PASS** | Partitioned by `session_id` and `date` |
| Data Integrity | **PASS** | 100% record count match between Local and MinIO |
| Persistence | **PASS** | Data persists across `docker compose down` / `up` |
| SMALL | **PASS** | 1,500 events processed in 1.89s |
| MEDIUM | **PASS** | 60,000 events processed in 21.88s |
| LARGE | **PASS** | 600,000 events processed in 251.67s |
| Local vs MinIO | **PASS** | MinIO within 6.8% of local IO at 600k scale |
| Regression | **PASS** | 71/71 tests passing (65 original + 6 new) |
| End-to-End | **PASS** | Complete Bronze $\rightarrow$ Silver $\rightarrow$ Gold pipeline validated |

---

## Final Status: **GREEN**
