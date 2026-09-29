# F1 Digital Twin — PySpark Structured Streaming (`Kafka -> PySpark -> MinIO Bronze`)

## Overview

The `streaming` module implements real-time **PySpark Structured Streaming** telemetry ingestion from **Kafka topic `f1_telemetry`** directly into **MinIO S3A Object Storage** (`s3a://f1-data-lake/bronze/telemetry/`) with **durable S3A checkpointing** (`s3a://f1-data-lake/checkpoints/telemetry/`).

---

## Architecture

```
F1 Digital Twin Physics Engine
              │
              ▼ (HTTP POST /telemetry)
    Flask Telemetry Bridge
              │
              ▼ (Kafka Producer)
     Kafka (f1_telemetry)
              │
              ▼ (PySpark readStream format("kafka"))
PySpark Structured Streaming Engine
              │
              ▼ (Hadoop S3A Connector)
    MinIO Object Storage
              │
   ┌──────────┴──────────┐
   ▼                     ▼
Bronze Parquet       S3A Checkpoint
s3a://f1-data-lake/  s3a://f1-data-lake/
bronze/telemetry/    checkpoints/telemetry/
```

---

## Technical Stack & Compatibility

- **Engine:** PySpark `3.5.1` Structured Streaming
- **Source:** Apache Kafka `7.5.0` (`f1_telemetry` topic)
- **Hadoop S3A:** `org.apache.hadoop:hadoop-aws:3.3.4` with `aws-java-sdk-bundle:1.12.262`
- **Kafka SQL Connector:** `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1`
- **Object Storage:** MinIO (`s3a://f1-data-lake/`)
- **Fast Upload Buffer:** `spark.hadoop.fs.s3a.fast.upload.buffer=array`

---

## Configuration & Environment Variables

Key parameters are loaded from `.env` or overridden via CLI arguments:

```ini
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC=f1_telemetry
MINIO_ENDPOINT=http://localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=f1-data-lake
SPARK_CHECKPOINT_DIR=s3a://f1-data-lake/checkpoints/telemetry
```

---

## Execution Commands

### 1. Start Infrastructure Containers

```bash
docker compose up -d
```

### 2. Run PySpark Streaming Job (Continuous)

```bash
python code/streaming/telemetry_stream.py
```

### 3. Run PySpark Streaming Job (Batch Micro-Ingestion / `once=True`)

```bash
python code/streaming/telemetry_stream.py --once
```

### 4. Execute End-to-End Validation & Checkpoint Recovery Test

```bash
python scratch/e2e_streaming_test.py
```

### 5. Run Automated Unit & Integration Test Suite

```bash
python -m pytest tests/
```
