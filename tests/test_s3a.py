# -*- coding: utf-8 -*-
"""
Minimal S3A Write, Read, Count, and Schema Validation Test
Demonstrates: WRITE PASS, READ PASS, COUNT PASS, SCHEMA PASS on s3a://f1-data-lake/test/
"""

import os
import sys
import pytest
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from datalake.s3_client import (
    get_s3_filesystem,
    ensure_bucket_exists,
    check_minio_health,
    MINIO_BUCKET
)


@pytest.mark.integration
def test_s3a_minimal_read_write_count_schema():
    """
    Minimal S3A verification test:
    1. Writes dummy telemetry DataFrame to s3a://f1-data-lake/test/
    2. Reads dummy Parquet dataset back from S3A
    3. Asserts COUNT match (COUNT PASS)
    4. Asserts SCHEMA match (SCHEMA PASS)
    """
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")
    s3_fs = get_s3_filesystem()
    ensure_bucket_exists(MINIO_BUCKET, s3_fs)

    test_s3_dir = f"{MINIO_BUCKET}/test/minimal_telemetry"
    try:
        file_info = s3_fs.get_file_info(test_s3_dir)
        if file_info.type != pa.fs.FileType.NotFound:
            s3_fs.delete_dir(test_s3_dir)
    except Exception:
        pass

    sample_data = [
        {"session_id": "SESS_TEST_01", "car_id": "FERRARI_01", "speed": 312.5, "lap_number": 1},
        {"session_id": "SESS_TEST_01", "car_id": "FERRARI_01", "speed": 315.0, "lap_number": 1},
        {"session_id": "SESS_TEST_01", "car_id": "RED_BULL_01", "speed": 320.2, "lap_number": 1}
    ]
    df_expected = pd.DataFrame(sample_data)
    expected_count = len(df_expected)
    expected_columns = set(df_expected.columns)

    # 1. WRITE PASS
    table_write = pa.Table.from_pandas(df_expected)
    pq.write_to_dataset(
        table_write,
        root_path=test_s3_dir,
        filesystem=s3_fs,
        partition_cols=["session_id"],
        use_dictionary=True,
        compression="SNAPPY"
    )

    # 2. READ PASS
    dataset_read = pq.ParquetDataset(test_s3_dir, filesystem=s3_fs)
    df_read = dataset_read.read().to_pandas()

    assert not df_read.empty, "READ FAIL: Read dataset from S3A is empty"

    # 3. COUNT PASS
    actual_count = len(df_read)
    assert actual_count == expected_count, f"COUNT FAIL: Expected {expected_count} records, got {actual_count}"

    # 4. SCHEMA PASS
    actual_columns = set(df_read.columns)
    # partition cols may be added or present
    assert expected_columns.issubset(actual_columns), f"SCHEMA FAIL: Expected columns {expected_columns} missing from {actual_columns}"
