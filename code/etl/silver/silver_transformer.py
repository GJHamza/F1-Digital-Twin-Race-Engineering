# -*- coding: utf-8 -*-
"""
Silver Layer Transformer for F1 Telemetry Pipeline
Cleanses, validates, deduplicates, and enriches telemetry events
with deterministic derived engineering metrics. Supports Local and S3A MinIO backends.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# Ensure etl and datalake packages are on path
ETL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODE_DIR = os.path.abspath(os.path.join(ETL_DIR, ".."))
for p in [ETL_DIR, CODE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from etl.config import (
    ETL_SILVER_PATH,
    ETL_QUARANTINE_PATH,
    S3_SILVER_PATH,
    S3_QUARANTINE_PATH,
    ETL_STORAGE_BACKEND
)
from etl.silver.quality_rules import validate_silver_record
from datalake.s3_client import (
    get_s3_filesystem,
    ensure_bucket_exists,
    parse_s3_uri
)


def transform_silver(bronze_source, output_dir=None, quarantine_dir=None):
    """
    Transforms Bronze Parquet telemetry data into clean, enriched Silver Parquet data.
    Routes invalid records to quarantine and calculates derived race engineering metrics.

    Args:
        bronze_source (str or DataFrame or list): Path to Bronze Parquet directory/file, S3 URI, DataFrame, or list of dicts.
        output_dir (str, optional): Target directory or S3 URI for Silver Parquet outputs.
        quarantine_dir (str, optional): Target directory or S3 URI for Quarantine outputs.

    Returns:
        dict: Transformation metrics (total_processed, valid_count, quarantine_count, duplicate_count, duration_sec).
    """
    t0 = time.time()

    if output_dir is None:
        if ETL_STORAGE_BACKEND == "minio":
            output_dir = S3_SILVER_PATH
        else:
            output_dir = ETL_SILVER_PATH

    if quarantine_dir is None:
        if ETL_STORAGE_BACKEND == "minio":
            quarantine_dir = S3_QUARANTINE_PATH
        else:
            quarantine_dir = ETL_QUARANTINE_PATH

    is_s3_output = output_dir.startswith("s3a://") or output_dir.startswith("s3://")
    is_s3_quarantine = quarantine_dir.startswith("s3a://") or quarantine_dir.startswith("s3://")

    s3_fs = None
    if is_s3_output or is_s3_quarantine or (isinstance(bronze_source, str) and (bronze_source.startswith("s3a://") or bronze_source.startswith("s3://"))):
        s3_fs = get_s3_filesystem()

    # Prepare Silver output directory / bucket
    if is_s3_output:
        out_bucket, out_subpath = parse_s3_uri(output_dir)
        ensure_bucket_exists(out_bucket, s3_fs)
        target_path = f"{out_bucket}/{out_subpath}".rstrip("/")
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

    # Prepare Quarantine output directory / bucket
    if is_s3_quarantine:
        q_bucket, _ = parse_s3_uri(quarantine_dir)
        ensure_bucket_exists(q_bucket, s3_fs)
    else:
        os.makedirs(quarantine_dir, exist_ok=True)

    # 1. Read input dataset
    if isinstance(bronze_source, pd.DataFrame):
        df_raw = bronze_source.copy()
    elif isinstance(bronze_source, list):
        df_raw = pd.DataFrame(bronze_source)
    elif isinstance(bronze_source, str):
        if bronze_source.startswith("s3a://") or bronze_source.startswith("s3://"):
            in_bucket, in_subpath = parse_s3_uri(bronze_source)
            target_path = f"{in_bucket}/{in_subpath}".rstrip("/")
            try:
                dataset = pq.ParquetDataset(target_path, filesystem=s3_fs)
                df_raw = dataset.read().to_pandas()
            except Exception:
                df_raw = pd.DataFrame()
        elif os.path.isfile(bronze_source) and bronze_source.endswith('.jsonl'):
            records = []
            with open(bronze_source, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            df_raw = pd.DataFrame(records)
        elif os.path.isdir(bronze_source) or os.path.isfile(bronze_source):
            try:
                dataset = pq.ParquetDataset(bronze_source)
                df_raw = dataset.read().to_pandas()
            except Exception:
                files = []
                if os.path.isfile(bronze_source):
                    files = [bronze_source]
                else:
                    for root, _, filenames in os.walk(bronze_source):
                        for fn in filenames:
                            if fn.endswith('.parquet'):
                                files.append(os.path.join(root, fn))
                if not files:
                    df_raw = pd.DataFrame()
                else:
                    df_raw = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        else:
            raise FileNotFoundError(f"Bronze path not found: {bronze_source}")
    else:
        raise ValueError("Invalid bronze_source parameter type")

    if df_raw.empty:
        t1 = time.time()
        return {
            "total_processed": 0,
            "valid_count": 0,
            "quarantine_count": 0,
            "duplicate_count": 0,
            "silver_written_count": 0,
            "duration_sec": round(t1 - t0, 3)
        }

    records = df_raw.to_dict(orient="records")
    total_processed = len(records)

    valid_records = []
    quarantine_records = []
    seen_event_ids = set()
    duplicate_count = 0

    now_iso = datetime.now(timezone.utc).isoformat()

    # 2. Quality Validation & Quarantine Routing & Event ID Deduplication
    for r in records:
        for json_key in ["telemetry_json", "aerodynamics_json", "tires_json", "active_anomalies_json"]:
            if json_key in r and isinstance(r[json_key], str):
                base_key = json_key.replace("_json", "")
                try:
                    r[base_key] = json.loads(r[json_key])
                except Exception:
                    pass

        is_valid, reason = validate_silver_record(r)
        if not is_valid:
            r_quarantine = dict(r)
            r_quarantine["rejection_reason"] = reason
            r_quarantine["rejected_at"] = now_iso
            quarantine_records.append(r_quarantine)
            continue

        eid = r.get("event_id")
        if eid in seen_event_ids:
            duplicate_count += 1
            r_quarantine = dict(r)
            r_quarantine["rejection_reason"] = f"Duplicate event_id '{eid}'"
            r_quarantine["rejected_at"] = now_iso
            quarantine_records.append(r_quarantine)
            continue

        seen_event_ids.add(eid)
        valid_records.append(r)

    # 3. Write Quarantine records if any
    if quarantine_records:
        df_quarantine = pd.DataFrame(quarantine_records)
        for col in df_quarantine.columns:
            df_quarantine[col] = df_quarantine[col].astype(str)
        
        q_table = pa.Table.from_pandas(df_quarantine)
        if is_s3_quarantine:
            q_bucket, q_subpath = parse_s3_uri(quarantine_dir)
            q_root = f"{q_bucket}/{q_subpath}".rstrip("/")
            pq.write_to_dataset(
                q_table,
                root_path=q_root,
                filesystem=s3_fs,
                use_dictionary=True,
                compression="SNAPPY"
            )
        else:
            pq.write_to_dataset(
                q_table,
                root_path=quarantine_dir,
                use_dictionary=True,
                compression="SNAPPY"
            )

    if not valid_records:
        t1 = time.time()
        return {
            "total_processed": total_processed,
            "valid_count": 0,
            "quarantine_count": len(quarantine_records),
            "duplicate_count": duplicate_count,
            "silver_written_count": 0,
            "duration_sec": round(t1 - t0, 3)
        }

    # 4. Silver Derived Metrics Calculation
    df_silver = pd.DataFrame(valid_records)

    def extract_nested_speed(row):
        tel = row.get("telemetry")
        if isinstance(tel, dict):
            return float(tel.get("speed", 0.0))
        return float(row.get("speed", 0.0))

    def extract_nested_rpm(row):
        tel = row.get("telemetry")
        if isinstance(tel, dict):
            return float(tel.get("rpm", 0.0))
        return float(row.get("rpm", 0.0))

    def extract_nested_torque(row):
        tel = row.get("telemetry")
        if isinstance(tel, dict):
            return float(tel.get("torque", 0.0))
        return float(row.get("torque", 0.0))

    def extract_nested_g_force(row):
        tel = row.get("telemetry")
        if isinstance(tel, dict):
            return float(tel.get("g_force", 1.0))
        return float(row.get("g_force", 1.0))

    def extract_nested_downforce(row):
        aero = row.get("aerodynamics")
        if isinstance(aero, dict):
            return float(aero.get("downforce", 0.0))
        return float(row.get("downforce", 0.0))

    def extract_nested_drag(row):
        aero = row.get("aerodynamics")
        if isinstance(aero, dict):
            return float(aero.get("drag_coefficient", 0.35))
        return float(row.get("drag_coefficient", 0.35))

    def extract_nested_wind(row):
        aero = row.get("aerodynamics")
        if isinstance(aero, dict):
            return float(aero.get("wind_speed", 0.0))
        return float(row.get("wind_speed", 0.0))

    def extract_tire_temps(row):
        tires = row.get("tires")
        if isinstance(tires, dict) and "tire_temp" in tires:
            return [float(x) for x in tires["tire_temp"]]
        return [95.0, 95.0, 95.0, 95.0]

    def extract_tire_wears(row):
        tires = row.get("tires")
        if isinstance(tires, dict) and "tire_wear" in tires:
            return [float(x) for x in tires["tire_wear"]]
        return [0.0, 0.0, 0.0, 0.0]

    df_silver["speed_kmh"] = df_silver.apply(extract_nested_speed, axis=1)
    df_silver["speed_ms"] = df_silver["speed_kmh"] / 3.6
    df_silver["rpm"] = df_silver.apply(extract_nested_rpm, axis=1)
    df_silver["torque"] = df_silver.apply(extract_nested_torque, axis=1)
    df_silver["g_force"] = df_silver.apply(extract_nested_g_force, axis=1)
    df_silver["downforce"] = df_silver.apply(extract_nested_downforce, axis=1)
    df_silver["drag_coefficient"] = df_silver.apply(extract_nested_drag, axis=1)
    df_silver["wind_speed"] = df_silver.apply(extract_nested_wind, axis=1)

    tire_temps_list = df_silver.apply(extract_tire_temps, axis=1)
    df_silver["tire_temp_avg"] = [float(np.mean(tt)) for tt in tire_temps_list]
    df_silver["tire_temp_max"] = [float(np.max(tt)) for tt in tire_temps_list]

    tire_wears_list = df_silver.apply(extract_tire_wears, axis=1)
    df_silver["tire_wear_avg"] = [float(np.mean(tw)) for tw in tire_wears_list]
    df_silver["tire_wear_max"] = [float(np.max(tw)) for tw in tire_wears_list]

    df_silver["fuel_level"] = pd.to_numeric(df_silver["fuel_level"], errors="coerce").fillna(0.0)
    df_silver["fuel_remaining_pct"] = (df_silver["fuel_level"] / 110.0) * 100.0

    df_silver["aero_efficiency"] = df_silver["downforce"] / (
        (df_silver["speed_ms"] ** 2) * df_silver["drag_coefficient"] + 1e-5
    )

    df_silver["tire_stress_index"] = (
        (df_silver["tire_temp_avg"] / 100.0) *
        (1.0 + df_silver["tire_wear_avg"] / 100.0) *
        df_silver["speed_ms"]
    )

    df_silver = df_silver.sort_values(by=["session_id", "timestamp"]).reset_index(drop=True)
    df_silver["acceleration_estimate"] = 0.0

    session_groups = df_silver.groupby("session_id")
    accel_list = []
    for sid, group in session_groups:
        speeds = group["speed_ms"].values
        accels = np.zeros(len(speeds))
        if len(speeds) > 1:
            accels[1:] = np.diff(speeds)
        accel_list.extend(accels)

    df_silver["acceleration_estimate"] = accel_list

    for col in ["telemetry", "aerodynamics", "tires", "active_anomalies"]:
        if col in df_silver.columns:
            df_silver[col + "_json"] = df_silver[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (dict, list)) else str(x)
            )

    table = pa.Table.from_pandas(df_silver)
    if is_s3_output:
        out_bucket, out_subpath = parse_s3_uri(output_dir)
        target_root = f"{out_bucket}/{out_subpath}".rstrip("/")
        pq.write_to_dataset(
            table,
            root_path=target_root,
            filesystem=s3_fs,
            partition_cols=["session_id", "date"] if "date" in df_silver.columns else ["session_id"],
            use_dictionary=True,
            compression="SNAPPY"
        )
    else:
        pq.write_to_dataset(
            table,
            root_path=output_dir,
            partition_cols=["session_id", "date"] if "date" in df_silver.columns else ["session_id"],
            use_dictionary=True,
            compression="SNAPPY"
        )

    t1 = time.time()
    return {
        "total_processed": total_processed,
        "valid_count": len(valid_records),
        "quarantine_count": len(quarantine_records),
        "duplicate_count": duplicate_count,
        "silver_written_count": len(df_silver),
        "duration_sec": round(t1 - t0, 3)
    }
