# -*- coding: utf-8 -*-
"""
Centralized Configuration for F1 Data Engineering ETL Pipeline
Supports Local Filesystem and MinIO S3A Data Lake backends.
"""

import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Default Local Data Paths
DEFAULT_INPUT_PATH = os.path.join(PROJECT_ROOT, "data", "generated", "medium.jsonl")
DEFAULT_OUTPUT_BASE = os.path.join(PROJECT_ROOT, "data", "processed")

ETL_BRONZE_PATH = os.path.join(DEFAULT_OUTPUT_BASE, "bronze", "telemetry")
ETL_SILVER_PATH = os.path.join(DEFAULT_OUTPUT_BASE, "silver", "telemetry")
ETL_QUARANTINE_PATH = os.path.join(DEFAULT_OUTPUT_BASE, "quarantine", "telemetry")
ETL_GOLD_PATH = os.path.join(DEFAULT_OUTPUT_BASE, "gold")

# S3A / MinIO Data Lake Paths
S3_BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")
S3_BRONZE_PATH = f"s3a://{S3_BUCKET}/bronze/telemetry"
S3_SILVER_PATH = f"s3a://{S3_BUCKET}/silver/telemetry"
S3_QUARANTINE_PATH = f"s3a://{S3_BUCKET}/quarantine/telemetry"
S3_GOLD_PATH = f"s3a://{S3_BUCKET}/gold"

ETL_STORAGE_BACKEND = os.getenv("ETL_STORAGE_BACKEND", "local").lower()

# Pipeline Configuration
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
PIPELINE_VERSION = "1.0.0"
DEFAULT_SOURCE = "synthetic_generator_v2"
