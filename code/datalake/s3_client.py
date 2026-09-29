# -*- coding: utf-8 -*-
"""
S3 Client & PyArrow S3FileSystem Integration for MinIO Object Storage
Handles S3 connection, bucket management, health checks, and path parsing.
"""

import os
import urllib.request
import pyarrow.fs as pafs
from dotenv import load_dotenv

# Load environment variables if available
load_dotenv()

MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")


def parse_s3_uri(s3_uri):
    """
    Parses an s3a:// or s3:// URI into bucket and relative path.
    Example: 's3a://f1-data-lake/bronze/telemetry' -> ('f1-data-lake', 'bronze/telemetry')
    """
    s3_uri = s3_uri.replace("\\", "/")
    if not (s3_uri.startswith("s3a://") or s3_uri.startswith("s3://")):
        raise ValueError(f"Invalid S3 URI: '{s3_uri}'. Must start with s3a:// or s3://")

    # Strip scheme
    clean_path = s3_uri.replace("s3a://", "").replace("s3://", "")
    parts = clean_path.split("/", 1)
    bucket = parts[0]
    subpath = parts[1] if len(parts) > 1 else ""
    return bucket, subpath



def get_s3_uri(bucket=MINIO_BUCKET, path=""):
    """
    Constructs a standard s3a:// URI for a given bucket and path.
    """
    clean_path = path.lstrip("/")
    if clean_path:
        return f"s3a://{bucket}/{clean_path}"
    return f"s3a://{bucket}"


def check_minio_health(endpoint=None):
    """
    Checks if MinIO server is alive and reachable via HTTP health endpoint.
    Returns:
        bool: True if reachable and healthy, False otherwise.
    """
    if endpoint is None:
        endpoint = MINIO_ENDPOINT

    health_url = f"{endpoint.rstrip('/')}/minio/health/live"
    try:
        req = urllib.request.Request(health_url, headers={"User-Agent": "F1-DataLake-Client"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_s3_filesystem(access_key=None, secret_key=None, endpoint=None):
    """
    Returns a PyArrow S3FileSystem configured for MinIO.

    Args:
        access_key (str, optional): MinIO access key / root user.
        secret_key (str, optional): MinIO secret key / root password.
        endpoint (str, optional): MinIO API endpoint (e.g., 'http://localhost:9000').

    Returns:
        pafs.S3FileSystem: Configured PyArrow S3 filesystem instance.
    """
    if access_key is None:
        access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    if secret_key is None:
        secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    if endpoint is None:
        endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")

    # Clean endpoint for PyArrow endpoint_override
    endpoint_override = endpoint.replace("http://", "").replace("https://", "")

    s3_fs = pafs.S3FileSystem(
        access_key=access_key,
        secret_key=secret_key,
        endpoint_override=endpoint_override,
        scheme="http",
        allow_bucket_creation=True,
        allow_bucket_deletion=True
    )
    return s3_fs


def ensure_bucket_exists(bucket_name=MINIO_BUCKET, s3_fs=None):
    """
    Ensures that target S3 bucket exists in MinIO. Creates it if it doesn't exist.

    Args:
        bucket_name (str): Name of bucket to create/verify.
        s3_fs (S3FileSystem, optional): PyArrow S3 filesystem instance.

    Returns:
        bool: True if bucket exists or was created successfully.
    """
    if s3_fs is None:
        s3_fs = get_s3_filesystem()

    try:
        file_info = s3_fs.get_file_info(bucket_name)
        if file_info.type == pafs.FileType.NotFound:
            s3_fs.create_dir(bucket_name)
            return True
        return True
    except Exception as e:
        # Try creating dir directly
        try:
            s3_fs.create_dir(bucket_name)
            return True
        except Exception:
            raise RuntimeError(f"Failed to verify/create bucket '{bucket_name}': {e}")
