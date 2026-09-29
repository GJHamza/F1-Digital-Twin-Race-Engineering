# -*- coding: utf-8 -*-
"""
Bronze Parquet Sink for PySpark Structured Streaming
Writes streaming telemetry DataFrame to MinIO S3A Object Storage with durable checkpointing.
"""


def write_bronze_stream(df, config, trigger_time="5 seconds", available_now=False):
    """
    Configures and starts PySpark writeStream targeting MinIO S3A Bronze Parquet storage.

    Args:
        df (DataFrame): Streaming DataFrame from kafka_source.
        config (StreamingConfig): Streaming pipeline configuration.
        trigger_time (str): Trigger interval (e.g., '5 seconds').
        available_now (bool): If True, uses trigger(availableNow=True) to process available records and exit.

    Returns:
        StreamingQuery: Active PySpark StreamingQuery instance.
    """
    writer = (
        df.writeStream
        .format("parquet")
        .outputMode("append")
        .option("path", config.bronze_path)
        .option("checkpointLocation", config.checkpoint_path)
        .partitionBy("session_id", "date")
    )

    if available_now:
        writer = writer.trigger(availableNow=True)
    elif trigger_time:
        writer = writer.trigger(processingTime=trigger_time)

    query = writer.start()
    return query
