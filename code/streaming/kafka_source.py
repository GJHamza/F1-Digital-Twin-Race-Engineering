# -*- coding: utf-8 -*-
"""
Kafka Source Builder for PySpark Structured Streaming
Reads raw messages from Kafka topic, decodes JSON value, and applies Schema V1.
"""

from pyspark.sql.functions import from_json, col, substring, current_date, date_format, coalesce
from .schema import get_telemetry_spark_schema


def create_kafka_stream(spark, config, starting_offsets="earliest"):
    """
    Creates a PySpark Structured Streaming DataFrame connected to Kafka topic.

    Args:
        spark (SparkSession): Active SparkSession instance.
        config (StreamingConfig): Streaming pipeline configuration.
        starting_offsets (str): Starting offset strategy ('earliest', 'latest').

    Returns:
        DataFrame: Transformed streaming DataFrame with parsed JSON telemetry payload and Kafka metadata.
    """
    kafka_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", config.kafka_bootstrap_servers)
        .option("subscribe", config.kafka_topic)
        .option("startingOffsets", starting_offsets)
        .option("failOnDataLoss", "false")
        .load()
    )

    schema = get_telemetry_spark_schema()

    # Decode JSON payload from value byte array
    parsed_df = kafka_df.select(
        col("topic").alias("kafka_topic"),
        col("partition").alias("kafka_partition"),
        col("offset").alias("kafka_offset"),
        col("timestamp").alias("kafka_timestamp"),
        from_json(col("value").cast("string"), schema).alias("data")
    )

    # Flatten data struct and attach ingestion metadata
    telemetry_stream = parsed_df.select(
        col("kafka_topic"),
        col("kafka_partition"),
        col("kafka_offset"),
        col("kafka_timestamp"),
        col("data.*")
    )

    # Filter out records where event_id is null or empty
    filtered_stream = telemetry_stream.filter(
        col("event_id").isNotNull() & (col("event_id") != "")
    )

    # Derive date partition column (YYYY-MM-DD) from timestamp or fallback to current_date()
    date_col = coalesce(
        substring(col("timestamp"), 1, 10),
        date_format(col("kafka_timestamp"), "yyyy-MM-dd"),
        date_format(current_date(), "yyyy-MM-dd")
    )

    return filtered_stream.withColumn("date", date_col)
