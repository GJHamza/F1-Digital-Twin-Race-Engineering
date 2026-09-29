# -*- coding: utf-8 -*-
"""
Streaming Pipeline Configuration for F1 Digital Twin
Loads and validates Kafka, MinIO, S3A, and PySpark parameters.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class StreamingConfig:
    def __init__(
        self,
        kafka_bootstrap_servers=None,
        kafka_topic=None,
        minio_endpoint=None,
        minio_access_key=None,
        minio_secret_key=None,
        minio_bucket=None,
        bronze_path=None,
        checkpoint_path=None,
        spark_master=None
    ):
        self.kafka_bootstrap_servers = (
            kafka_bootstrap_servers or os.getenv("KAFKA_BROKER", "localhost:9092")
        )
        self.kafka_topic = (
            kafka_topic or os.getenv("KAFKA_TOPIC", "f1_telemetry")
        )
        self.minio_endpoint = (
            minio_endpoint or os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        )
        self.minio_access_key = (
            minio_access_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
        )
        self.minio_secret_key = (
            minio_secret_key or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        )
        self.minio_bucket = (
            minio_bucket or os.getenv("MINIO_BUCKET", "f1-data-lake")
        )

        bucket_clean = self.minio_bucket.strip("/")
        self.bronze_path = (
            bronze_path or f"s3a://{bucket_clean}/bronze/telemetry"
        )
        
        if checkpoint_path is not None:
            self.checkpoint_path = checkpoint_path
        elif minio_bucket is not None:
            self.checkpoint_path = f"s3a://{bucket_clean}/checkpoints/telemetry"
        else:
            self.checkpoint_path = os.getenv("SPARK_CHECKPOINT_DIR", f"s3a://{bucket_clean}/checkpoints/telemetry")

        self.spark_master = (
            spark_master or os.getenv("SPARK_MASTER", "local[*]")
        )

    def to_dict(self):
        return {
            "kafka_bootstrap_servers": self.kafka_bootstrap_servers,
            "kafka_topic": self.kafka_topic,
            "minio_endpoint": self.minio_endpoint,
            "minio_bucket": self.minio_bucket,
            "bronze_path": self.bronze_path,
            "checkpoint_path": self.checkpoint_path,
            "spark_master": self.spark_master
        }
