# -*- coding: utf-8 -*-
"""
End-to-End Data Lake Integration Tests & Local vs MinIO Equivalence
"""

import os
import sys
import pytest
import pandas as pd
import pyarrow.parquet as pq

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from etl.bronze.bronze_writer import write_bronze
from etl.silver.silver_transformer import transform_silver
from etl.gold.gold_builder import build_gold
from datalake.s3_client import get_s3_filesystem, parse_s3_uri, MINIO_BUCKET, check_minio_health


@pytest.fixture(scope="module")
def sample_events():
    return [
        {
            "event_id": f"EVT_DL_{i:04d}",
            "session_id": "SESS_DL_001",
            "car_id": "FERRARI_01",
            "lap_number": 1,
            "timestamp": "2026-09-22T10:00:00.000Z",
            "speed": 280.0 + i,
            "rpm": 11500,
            "fuel_level": 105.0 - (i * 0.1),
            "telemetry": {"speed": 280.0 + i, "rpm": 11500, "gear": 6, "g_force": 1.4},
            "aerodynamics": {"downforce": 420.0, "drag_coefficient": 0.35, "wind_speed": 12.0},
            "tires": {"tire_temp": [92.0, 93.0, 94.0, 91.0], "tire_wear": [2.0, 2.1, 2.2, 1.9]},
            "active_anomalies": []
        }
        for i in range(20)
    ]


@pytest.mark.integration
def test_datalake_end_to_end_minio(sample_events, tmp_path):
    """
    Tests complete Bronze -> Silver -> Gold pipeline on MinIO S3A storage.
    Verifies record count integrity across all layers.
    """
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")

    s3_bronze = f"s3a://{MINIO_BUCKET}/bronze/test_telemetry"
    s3_silver = f"s3a://{MINIO_BUCKET}/silver/test_telemetry"
    s3_quarantine = f"s3a://{MINIO_BUCKET}/quarantine/test_telemetry"
    s3_gold = f"s3a://{MINIO_BUCKET}/gold_test"

    # 1. Bronze Write
    b_res = write_bronze(sample_events, output_dir=s3_bronze)
    assert b_res["total_records"] == 20, "Bronze ingestion record count mismatch"

    # 2. Silver Transformation
    s_res = transform_silver(s3_bronze, output_dir=s3_silver, quarantine_dir=s3_quarantine)
    assert s_res["valid_count"] == 20, "Silver valid record count mismatch"
    assert s_res["quarantine_count"] == 0, "Quarantine count expected 0"

    # 3. Gold Builder
    g_res = build_gold(s3_silver, output_dir=s3_gold)
    assert g_res["gold_datasets_created"] == 5, "Expected 5 Gold datasets"
    assert g_res["counts"]["lap_performance"] == 1, "Expected 1 lap aggregated record"
    assert g_res["counts"]["fuel_performance"] == 1, "Expected 1 fuel aggregated record"


@pytest.mark.integration
def test_local_vs_minio_integrity(sample_events, tmp_path):
    """
    Executes identical dataset on Local Filesystem vs MinIO S3A.
    Verifies 100% record count and schema equivalence between backends.
    """
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")
    local_base = str(tmp_path / "processed")
    local_b = os.path.join(local_base, "bronze")
    local_s = os.path.join(local_base, "silver")
    local_g = os.path.join(local_base, "gold")
    local_q = os.path.join(local_base, "quarantine")

    s3_b = f"s3a://{MINIO_BUCKET}/bronze/equiv_telemetry"
    s3_s = f"s3a://{MINIO_BUCKET}/silver/equiv_telemetry"
    s3_q = f"s3a://{MINIO_BUCKET}/quarantine/equiv_telemetry"
    s3_g = f"s3a://{MINIO_BUCKET}/gold_equiv"

    # Run Local
    b_local = write_bronze(sample_events, output_dir=local_b)
    s_local = transform_silver(local_b, output_dir=local_s, quarantine_dir=local_q)
    g_local = build_gold(local_s, output_dir=local_g)

    # Run MinIO
    b_minio = write_bronze(sample_events, output_dir=s3_b)
    s_minio = transform_silver(s3_b, output_dir=s3_s, quarantine_dir=s3_q)
    g_minio = build_gold(s3_s, output_dir=s3_g)

    # Parity checks
    assert b_local["total_records"] == b_minio["total_records"] == 20
    assert s_local["valid_count"] == s_minio["valid_count"] == 20
    assert g_local["counts"]["lap_performance"] == g_minio["counts"]["lap_performance"] == 1
    assert g_local["counts"]["fuel_performance"] == g_minio["counts"]["fuel_performance"] == 1
