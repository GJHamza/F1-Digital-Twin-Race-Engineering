# -*- coding: utf-8 -*-
"""
Unit Tests for Streaming Pipeline Configuration
"""

import os
import sys
import pytest

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from streaming.config import StreamingConfig


def test_streaming_config_defaults():
    """Verify default values for StreamingConfig."""
    cfg = StreamingConfig()
    assert cfg.kafka_bootstrap_servers is not None
    assert cfg.kafka_topic == "f1_telemetry"
    assert cfg.minio_bucket == "f1-data-lake"
    assert cfg.bronze_path.startswith("s3a://")
    assert cfg.checkpoint_path.startswith("s3a://")


def test_streaming_config_custom_overrides():
    """Verify explicit override values for StreamingConfig."""
    cfg = StreamingConfig(
        kafka_bootstrap_servers="custom-kafka:9092",
        kafka_topic="custom_topic",
        minio_bucket="my-bucket"
    )
    assert cfg.kafka_bootstrap_servers == "custom-kafka:9092"
    assert cfg.kafka_topic == "custom_topic"
    assert cfg.minio_bucket == "my-bucket"
    assert cfg.bronze_path == "s3a://my-bucket/bronze/telemetry"
    assert cfg.checkpoint_path == "s3a://my-bucket/checkpoints/telemetry"
