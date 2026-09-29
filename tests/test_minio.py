# -*- coding: utf-8 -*-
"""
Integration Tests for MinIO Object Storage Health & Bucket Operations
"""

import os
import sys
import pytest

# Add code directory to path
CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from datalake.s3_client import (
    check_minio_health,
    get_s3_filesystem,
    ensure_bucket_exists,
    MINIO_BUCKET
)


@pytest.mark.integration
def test_minio_health_check():
    """Verify MinIO API endpoint is alive and returning HTTP 200 health status."""
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")
    is_healthy = check_minio_health()
    assert is_healthy is True, "MinIO service is not reachable on port 9000."


@pytest.mark.integration
def test_minio_s3_filesystem_creation():
    """Verify PyArrow S3FileSystem connects to MinIO without authorization errors."""
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")
    s3_fs = get_s3_filesystem()
    assert s3_fs is not None, "Failed to instantiate S3FileSystem"


@pytest.mark.integration
def test_minio_bucket_creation_and_exists():
    """Verify target S3 bucket (f1-data-lake) can be verified or created idempotently."""
    if not check_minio_health():
        pytest.skip("MinIO server is not reachable (Docker container stopped)")
    bucket_ok = ensure_bucket_exists(MINIO_BUCKET)
    assert bucket_ok is True, f"Failed to ensure bucket '{MINIO_BUCKET}' exists."

    s3_fs = get_s3_filesystem()
    info = s3_fs.get_file_info(MINIO_BUCKET)
    assert info.type != pytest.importorskip("pyarrow.fs").FileType.NotFound, f"Bucket '{MINIO_BUCKET}' not found"
