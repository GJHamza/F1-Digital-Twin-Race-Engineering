# -*- coding: utf-8 -*-
"""
PySpark Structured Streaming Entrypoint CLI for F1 Digital Twin
Orchestrates Kafka stream consumption, Schema V1 decoding, S3A Hadoop configuration,
and writing partitioned Parquet data into MinIO S3A Bronze storage with durable checkpoints.
"""

import os
import sys
import argparse
import time

# Add parent directories to sys.path
STREAMING_DIR = os.path.abspath(os.path.dirname(__file__))
CODE_DIR = os.path.abspath(os.path.join(STREAMING_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(CODE_DIR, ".."))
for p in [STREAMING_DIR, CODE_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from pyspark.sql import SparkSession
from streaming.config import StreamingConfig
from streaming.kafka_source import create_kafka_stream
from streaming.bronze_sink import write_bronze_stream


def build_spark_session(config):
    """
    Constructs PySpark SparkSession configured with Kafka SQL package and MinIO S3A Hadoop filesystem.
    """
    # Fix Windows Hadoop winutils requirement if running natively on Windows host
    if sys.platform.startswith("win") and "HADOOP_HOME" not in os.environ:
        fake_hadoop = os.path.abspath(os.path.join(PROJECT_ROOT, "scratch", "hadoop"))
        os.makedirs(os.path.join(fake_hadoop, "bin"), exist_ok=True)
        winutils_file = os.path.join(fake_hadoop, "bin", "winutils.exe")
        if not os.path.exists(winutils_file):
            open(winutils_file, "a").close()
        os.environ["HADOOP_HOME"] = fake_hadoop

    buffer_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "scratch", "s3a_buffer"))
    os.makedirs(buffer_dir, exist_ok=True)
    buffer_dir_posix = buffer_dir.replace("\\", "/")

    builder = (
        SparkSession.builder
        .appName("F1-Telemetry-PySpark-Streaming")
        .master(config.spark_master)
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262")
        .config("spark.hadoop.fs.s3a.endpoint", config.minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", config.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", config.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
        .config("spark.hadoop.fs.s3a.fast.upload.buffer", "array")
        .config("spark.hadoop.io.native.lib.available", "false")
        .config("spark.hadoop.fs.s3a.buffer.dir", buffer_dir_posix)
        .config("spark.hadoop.hadoop.tmp.dir", buffer_dir_posix)
        .config("spark.sql.streaming.checkpointLocation", config.checkpoint_path)


    )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark




def run_streaming_pipeline(config=None, once=False, starting_offsets="earliest"):
    """
    Executes the PySpark Structured Streaming pipeline.

    Args:
        config (StreamingConfig, optional): Streaming configuration.
        once (bool): If True, processes available messages and exits.
        starting_offsets (str): Starting offsets strategy ('earliest', 'latest').
    """
    if config is None:
        config = StreamingConfig()

    print(f"\n==================================================", flush=True)
    print(f"STARTING PYSPARK STRUCTURED STREAMING PIPELINE", flush=True)
    print(f"==================================================", flush=True)
    print(f"[CONFIG] Kafka Broker    : {config.kafka_bootstrap_servers}", flush=True)
    print(f"[CONFIG] Kafka Topic     : {config.kafka_topic}", flush=True)
    print(f"[CONFIG] MinIO Endpoint  : {config.minio_endpoint}", flush=True)
    print(f"[CONFIG] Bronze Path     : {config.bronze_path}", flush=True)
    print(f"[CONFIG] Checkpoint Path : {config.checkpoint_path}", flush=True)

    spark = build_spark_session(config)

    print("\n[STREAMING] Connecting to Kafka source...", flush=True)
    stream_df = create_kafka_stream(spark, config, starting_offsets=starting_offsets)

    print("[STREAMING] Starting Bronze Parquet S3A writeStream...", flush=True)
    query = write_bronze_stream(stream_df, config, available_now=once)

    print(f"[STREAMING] Active query ID: {query.id} | Status: RUNNING", flush=True)

    if once:
        query.awaitTermination()
        print("[STREAMING] One-time batch stream processing completed successfully.", flush=True)
    else:
        try:
            query.awaitTermination()
        except KeyboardInterrupt:
            print("\n[STREAMING] Stopping streaming query gracefully...", flush=True)
            query.stop()

    return query


def main():
    parser = argparse.ArgumentParser(description="F1 Telemetry PySpark Structured Streaming Pipeline")
    parser.add_argument("--once", action="store_true", help="Process available Kafka records and exit")
    parser.add_argument("--kafka-broker", type=str, default=None, help="Kafka bootstrap servers")
    parser.add_argument("--topic", type=str, default=None, help="Kafka topic name")
    parser.add_argument("--starting-offsets", type=str, default="earliest", choices=["earliest", "latest"])

    args = parser.parse_args()
    config = StreamingConfig(
        kafka_bootstrap_servers=args.kafka_broker,
        kafka_topic=args.topic
    )
    run_streaming_pipeline(config=config, once=args.once, starting_offsets=args.starting_offsets)


if __name__ == "__main__":
    main()
