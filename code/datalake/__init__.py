# -*- coding: utf-8 -*-
"""
Data Lake Infrastructure Module for F1 Digital Twin
Provides S3A / MinIO object storage connection, health checking, bucket creation, and PyArrow/Spark filesystem integration.
"""

from .s3_client import (
    get_s3_filesystem,
    ensure_bucket_exists,
    check_minio_health,
    get_s3_uri,
    parse_s3_uri
)

__all__ = [
    "get_s3_filesystem",
    "ensure_bucket_exists",
    "check_minio_health",
    "get_s3_uri",
    "parse_s3_uri"
]
