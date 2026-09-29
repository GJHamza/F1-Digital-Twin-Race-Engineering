# F1 Digital Twin — Data Lake Infrastructure (MinIO + S3A + PySpark/PyArrow)

## Overview

The `datalake` module implements a cloud-native **Object Storage Data Lake** architecture for the F1 Digital Twin platform using **MinIO**, **S3A protocol**, and high-performance **PyArrow / PySpark S3FileSystem connectors**.

This architecture decouples operational metadata storage (MongoDB Atlas) from high-throughput analytical telemetry persistence (MinIO S3A Object Storage).

---

## Architecture Cible

```
                 F1 DIGITAL TWIN
                       │
                       ▼
                    Kafka
                       │
                       ▼
              ┌─────────────────┐
              │      BRONZE     │
              │     MinIO       │
              │      S3A        │
              └────────┬────────┘
                       │
                       ▼
               PySpark / PyArrow
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
         ┌─────────┐         ┌─────────┐
         │ SILVER  │         │  GOLD   │
         │  MinIO  │         │  MinIO  │
         │  S3A    │         │  S3A    │
         └─────────┘         └─────────┘
                                  │
                                  ▼
                         Race Engineering
                                  │
                                  ▼
                             Future ML
```

---

## Bucket Architecture (`s3a://f1-data-lake/`)

| Data Lake Layer | Path / Prefix | Description | Partitioning Strategy | Storage Format |
|---|---|---|---|---|
| **Bronze** | `s3a://f1-data-lake/bronze/telemetry/` | Raw telemetry ingestion with technical metadata | `session_id`, `date` | Partitioned Parquet |
| **Silver** | `s3a://f1-data-lake/silver/telemetry/` | Cleansed, deduplicated, enriched telemetry with derived metrics | `session_id`, `date` | Partitioned Parquet |
| **Quarantine** | `s3a://f1-data-lake/quarantine/telemetry/` | Rejected invalid telemetry events & duplicates | None | Parquet |
| **Gold** | `s3a://f1-data-lake/gold/lap_performance/` | Aggregated lap performance metrics | `session_id` | Parquet |
| **Gold** | `s3a://f1-data-lake/gold/tire_performance/` | Aggregated tire wear & thermal degradation metrics | `session_id` | Parquet |
| **Gold** | `s3a://f1-data-lake/gold/fuel_performance/` | Fuel consumption per lap analytics | `session_id` | Parquet |
| **Gold** | `s3a://f1-data-lake/gold/aero_performance/` | Downforce vs drag efficiency metrics | `session_id` | Parquet |
| **Gold** | `s3a://f1-data-lake/gold/anomaly_summary/` | High-level anomaly detection summaries | `session_id` | Parquet |

---

## Configuration & Environment Variables

MinIO configuration parameters are loaded from `.env`:

```ini
# MinIO Data Lake Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=http://localhost:9000
MINIO_BUCKET=f1-data-lake
ETL_STORAGE_BACKEND=minio
```

---

## Storage Abstraction & Dual Backend Support

The ETL pipeline (`code/etl/`) supports dynamic backend switching via `ETL_STORAGE_BACKEND`:

- `ETL_STORAGE_BACKEND=local`: Reads and writes to local filesystem (`data/processed/`).
- `ETL_STORAGE_BACKEND=minio`: Reads and writes directly to `s3a://f1-data-lake/` using PyArrow S3FileSystem.

### Python API Usage

```python
from datalake.s3_client import get_s3_filesystem, check_minio_health, ensure_bucket_exists

# Check health
if check_minio_health():
    print("MinIO Object Storage is active")

# Ensure bucket exists
ensure_bucket_exists("f1-data-lake")

# Get PyArrow S3FileSystem
s3_fs = get_s3_filesystem()
```

---

## Docker Commands

```bash
# Start MinIO Object Storage service
docker compose up -d

# Check status & health
docker ps

# View MinIO container logs
docker logs f1-minio

# Stop MinIO service (data persists in volume 'minio-data')
docker compose down

# Stop & remove volumes
docker compose down -v
```

---

## Running Automated Tests & Verification

```bash
# Execute test suite (71 tests passing)
python -m pytest tests/

# Execute Data Lake integration tests only
python -m pytest tests/test_minio.py tests/test_s3a.py tests/test_datalake.py

# Run pipeline benchmark (SMALL, MEDIUM, LARGE)
python scratch/benchmark_g3_2.py
```
