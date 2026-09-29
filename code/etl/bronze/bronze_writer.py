# -*- coding: utf-8 -*-
"""
Bronze Layer Writer for F1 Telemetry Pipeline
Reads raw JSONL files / records / S3 sources, attaches technical metadata,
and writes immutable partitioned Parquet data to Local or MinIO S3A storage.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Ensure etl and datalake packages are on path
ETL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODE_DIR = os.path.abspath(os.path.join(ETL_DIR, ".."))
for p in [ETL_DIR, CODE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from etl.config import (
    ETL_BRONZE_PATH,
    S3_BRONZE_PATH,
    ETL_STORAGE_BACKEND,
    PIPELINE_VERSION,
    DEFAULT_SOURCE
)
from datalake.s3_client import (
    get_s3_filesystem,
    ensure_bucket_exists,
    parse_s3_uri
)


def write_bronze(input_source, output_dir=None, source_name=DEFAULT_SOURCE):
    """
    Ingests raw JSONL file, folder of JSONL files, S3 URI, or list of dict events,
    attaches technical ingestion metadata, and writes partitioned Parquet data to Bronze layer (Local or S3A MinIO).

    Args:
        input_source (str or list): Path to JSONL file/dir, S3 URI, or list of event dicts.
        output_dir (str, optional): Target directory or s3a:// URI for Bronze Parquet outputs.
        source_name (str): Identifier for telemetry source.

    Returns:
        dict: Summary metrics (total_records, files_written, output_dir, duration_sec).
    """
    t0 = time.time()

    if output_dir is None:
        if ETL_STORAGE_BACKEND == "minio":
            output_dir = S3_BRONZE_PATH
        else:
            output_dir = ETL_BRONZE_PATH

    is_s3_output = output_dir.startswith("s3a://") or output_dir.startswith("s3://")

    # Clean target directory for idempotent writes
    s3_fs = None
    if is_s3_output:
        bucket, subpath = parse_s3_uri(output_dir)
        s3_fs = get_s3_filesystem()
        ensure_bucket_exists(bucket, s3_fs)
        target_path = f"{bucket}/{subpath}".rstrip("/")
        try:
            file_info = s3_fs.get_file_info(target_path)
            if file_info.type != pa.fs.FileType.NotFound:
                s3_fs.delete_dir(target_path)
        except Exception:
            pass
    else:
        if os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
        os.makedirs(output_dir, exist_ok=True)

    records = []
    if isinstance(input_source, list):
        records = [dict(r) for r in input_source]
    elif isinstance(input_source, str):
        if input_source.startswith("s3a://") or input_source.startswith("s3://"):
            in_bucket, in_subpath = parse_s3_uri(input_source)
            if s3_fs is None:
                s3_fs = get_s3_filesystem()
            in_target = f"{in_bucket}/{in_subpath}".rstrip("/")
            selector = pa.fs.FileSelector(in_target, recursive=True)
            files = [f.path for f in s3_fs.get_file_info(selector) if f.type == pa.fs.FileType.File]
            for fpath in files:
                with s3_fs.open_input_stream(fpath) as f:
                    content = f.read().decode('utf-8')
                    for line in content.splitlines():
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
        elif os.path.isfile(input_source):
            files = [input_source]
            for fpath in files:
                with open(fpath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
        elif os.path.isdir(input_source):
            files = [os.path.join(input_source, f) for f in os.listdir(input_source) if f.endswith('.jsonl')]
            for fpath in files:
                with open(fpath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
        else:
            raise FileNotFoundError(f"Input path not found: {input_source}")
    else:
        raise ValueError("input_source must be a file path, directory path, S3 URI, or list of dicts")

    if not records:
        t1 = time.time()
        return {
            "total_records": 0,
            "files_written": 0,
            "output_dir": output_dir,
            "duration_sec": round(t1 - t0, 3)
        }

    # Technical metadata insertion
    now_iso = datetime.now(timezone.utc).isoformat()

    processed_rows = []
    for r in records:
        row = dict(r)
        row["ingestion_timestamp"] = now_iso
        row["source"] = source_name
        row["pipeline_version"] = PIPELINE_VERSION

        # Extract date partition from timestamp
        ts_str = row.get("timestamp", now_iso)
        try:
            date_part = ts_str[:10]  # YYYY-MM-DD
        except Exception:
            date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row["date"] = date_part

        # Serialize nested dicts/lists to JSON strings for Parquet storage stability
        if isinstance(row.get("telemetry"), dict):
            row["telemetry_json"] = json.dumps(row["telemetry"])
        if isinstance(row.get("aerodynamics"), dict):
            row["aerodynamics_json"] = json.dumps(row["aerodynamics"])
        if isinstance(row.get("tires"), dict):
            row["tires_json"] = json.dumps(row["tires"])
        if isinstance(row.get("active_anomalies"), list):
            row["active_anomalies_json"] = json.dumps(row["active_anomalies"])

        processed_rows.append(row)

    df = pd.DataFrame(processed_rows)
    table = pa.Table.from_pandas(df)

    # Write partitioned Parquet dataset to Local or S3
    if is_s3_output:
        bucket, subpath = parse_s3_uri(output_dir)
        target_root = f"{bucket}/{subpath}".rstrip("/")
        pq.write_to_dataset(
            table,
            root_path=target_root,
            filesystem=s3_fs,
            partition_cols=["session_id", "date"],
            use_dictionary=True,
            compression="SNAPPY"
        )
    else:
        pq.write_to_dataset(
            table,
            root_path=output_dir,
            partition_cols=["session_id", "date"],
            use_dictionary=True,
            compression="SNAPPY"
        )

    t1 = time.time()
    return {
        "total_records": len(records),
        "files_written": len(df["session_id"].unique()) if "session_id" in df.columns else 1,
        "output_dir": output_dir,
        "duration_sec": round(t1 - t0, 3)
    }
