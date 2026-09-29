# -*- coding: utf-8 -*-
"""
Incremental Silver Layer Transformer for F1 Telemetry Pipeline
Reads new / unprocessed Bronze Parquet files from Local or MinIO S3A Object Storage,
cleanses, validates, deduplicates by event_id against a state manifest, routes invalid
records to Quarantine, computes derived race engineering metrics, and appends to Silver Parquet.
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
    ETL_BRONZE_PATH,
    ETL_SILVER_PATH,
    ETL_QUARANTINE_PATH,
    S3_BRONZE_PATH,
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


def load_state_manifest(state_path, s3_fs=None):
    """Loads state manifest JSON containing processed file list and seen event_id set."""
    is_s3 = state_path.startswith("s3a://") or state_path.startswith("s3://")
    default_state = {"processed_files": [], "seen_event_ids": []}

    try:
        if is_s3:
            if s3_fs is None:
                s3_fs = get_s3_filesystem()
            bucket, subpath = parse_s3_uri(state_path)
            target = f"{bucket}/{subpath}".rstrip("/")
            file_info = s3_fs.get_file_info(target)
            if file_info.type != pa.fs.FileType.NotFound:
                with s3_fs.open_input_stream(target) as f:
                    content = f.read().decode('utf-8')
                    return json.loads(content)
        else:
            if os.path.exists(state_path):
                with open(state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except Exception:
        pass
    return default_state


def save_state_manifest(state_data, state_path, s3_fs=None):
    """Saves state manifest JSON to Local or S3A storage."""
    is_s3 = state_path.startswith("s3a://") or state_path.startswith("s3://")
    content = json.dumps(state_data, indent=2)

    if is_s3:
        if s3_fs is None:
            s3_fs = get_s3_filesystem()
        bucket, subpath = parse_s3_uri(state_path)
        ensure_bucket_exists(bucket, s3_fs)
        target = f"{bucket}/{subpath}".rstrip("/")
        with s3_fs.open_output_stream(target) as f:
            f.write(content.encode('utf-8'))
    else:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, 'w', encoding='utf-8') as f:
            f.write(content)


def list_bronze_parquet_files(bronze_source, s3_fs=None):
    """Lists all Parquet file paths under Bronze directory (Local or S3A)."""
    files = []
    is_s3 = isinstance(bronze_source, str) and (bronze_source.startswith("s3a://") or bronze_source.startswith("s3://"))

    if is_s3:
        if s3_fs is None:
            s3_fs = get_s3_filesystem()
        bucket, subpath = parse_s3_uri(bronze_source)
        target = f"{bucket}/{subpath}".rstrip("/")
        try:
            selector = pa.fs.FileSelector(target, recursive=True)
            for info in s3_fs.get_file_info(selector):
                if info.type == pa.fs.FileType.File and info.path.endswith('.parquet'):
                    files.append(info.path)
        except Exception:
            pass
    elif isinstance(bronze_source, str):
        if os.path.isfile(bronze_source) and bronze_source.endswith('.parquet'):
            files.append(bronze_source)
        elif os.path.isdir(bronze_source):
            for root, _, filenames in os.walk(bronze_source):
                for fn in filenames:
                    if fn.endswith('.parquet'):
                        files.append(os.path.join(root, fn))
    return sorted(files)


def transform_silver_incremental(
    bronze_source=None,
    output_dir=None,
    quarantine_dir=None,
    state_path=None
):
    """
    Incrementally transforms unprocessed Bronze Parquet telemetry data into clean Silver Parquet data.
    Maintains an idempotent state manifest of processed files and seen event_id keys.

    Args:
        bronze_source (str, optional): Source Bronze directory or S3 URI.
        output_dir (str, optional): Target Silver directory or S3 URI.
        quarantine_dir (str, optional): Target Quarantine directory or S3 URI.
        state_path (str, optional): Path or S3 URI to state manifest JSON.

    Returns:
        dict: Incremental transformation metrics.
    """
    t0 = time.time()

    if bronze_source is None:
        bronze_source = S3_BRONZE_PATH if ETL_STORAGE_BACKEND == "minio" else ETL_BRONZE_PATH

    if output_dir is None:
        output_dir = S3_SILVER_PATH if ETL_STORAGE_BACKEND == "minio" else ETL_SILVER_PATH

    if quarantine_dir is None:
        quarantine_dir = S3_QUARANTINE_PATH if ETL_STORAGE_BACKEND == "minio" else ETL_QUARANTINE_PATH

    if state_path is None:
        if ETL_STORAGE_BACKEND == "minio":
            state_path = "s3a://f1-data-lake/checkpoints/silver_incremental/state.json"
        else:
            state_path = os.path.join(ETL_DIR, "..", "data", "processed", "checkpoints", "silver_state.json")

    is_s3_output = output_dir.startswith("s3a://") or output_dir.startswith("s3://")
    is_s3_quarantine = quarantine_dir.startswith("s3a://") or quarantine_dir.startswith("s3://")
    is_s3_bronze = isinstance(bronze_source, str) and (bronze_source.startswith("s3a://") or bronze_source.startswith("s3://"))

    s3_fs = None
    if is_s3_output or is_s3_quarantine or is_s3_bronze or state_path.startswith("s3a://") or state_path.startswith("s3://"):
        s3_fs = get_s3_filesystem()

    # Load state manifest
    state = load_state_manifest(state_path, s3_fs)
    processed_files_set = set(state.get("processed_files", []))
    seen_event_ids_set = set(state.get("seen_event_ids", []))

    # List Bronze files and find new unprocessed files
    all_bronze_files = list_bronze_parquet_files(bronze_source, s3_fs)
    new_files = [f for f in all_bronze_files if f not in processed_files_set]

    if not new_files:
        t1 = time.time()
        return {
            "new_files_processed": 0,
            "total_processed": 0,
            "valid_count": 0,
            "quarantine_count": 0,
            "duplicate_count": 0,
            "silver_written_count": 0,
            "duration_sec": round(t1 - t0, 3)
        }

    # Read records from new files
    raw_dfs = []
    for fpath in new_files:
        try:
            if is_s3_bronze:
                tbl = pq.read_table(fpath, filesystem=s3_fs)
            else:
                tbl = pq.read_table(fpath)
            raw_dfs.append(tbl.to_pandas())
        except Exception as e:
            print(f"[WARN] Failed to read Bronze file '{fpath}': {e}", flush=True)

    if not raw_dfs:
        t1 = time.time()
        return {
            "new_files_processed": len(new_files),
            "total_processed": 0,
            "valid_count": 0,
            "quarantine_count": 0,
            "duplicate_count": 0,
            "silver_written_count": 0,
            "duration_sec": round(t1 - t0, 3)
        }

    df_raw = pd.concat(raw_dfs, ignore_index=True)
    records = df_raw.to_dict(orient="records")
    total_processed = len(records)

    valid_records = []
    quarantine_records = []
    duplicate_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    # Quality validation, event_id deduplication against state & current batch
    batch_seen_ids = set()
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
        if eid in seen_event_ids_set or eid in batch_seen_ids:
            duplicate_count += 1
            r_quarantine = dict(r)
            r_quarantine["rejection_reason"] = f"Duplicate event_id '{eid}'"
            r_quarantine["rejected_at"] = now_iso
            quarantine_records.append(r_quarantine)
            continue

        seen_event_ids_set.add(eid)
        batch_seen_ids.add(eid)
        valid_records.append(r)

    # Write Quarantine records if any
    if quarantine_records:
        df_quarantine = pd.DataFrame(quarantine_records)
        for col in df_quarantine.columns:
            df_quarantine[col] = df_quarantine[col].astype(str)
        q_table = pa.Table.from_pandas(df_quarantine)
        if is_s3_quarantine:
            q_bucket, q_subpath = parse_s3_uri(quarantine_dir)
            ensure_bucket_exists(q_bucket, s3_fs)
            q_root = f"{q_bucket}/{q_subpath}".rstrip("/")
            pq.write_to_dataset(
                q_table,
                root_path=q_root,
                filesystem=s3_fs,
                use_dictionary=True,
                compression="SNAPPY"
            )
        else:
            os.makedirs(quarantine_dir, exist_ok=True)
            pq.write_to_dataset(
                q_table,
                root_path=quarantine_dir,
                use_dictionary=True,
                compression="SNAPPY"
            )

    if not valid_records:
        # Update processed files in state even if zero valid records
        processed_files_set.update(new_files)
        state["processed_files"] = sorted(list(processed_files_set))
        state["seen_event_ids"] = sorted(list(seen_event_ids_set))
        save_state_manifest(state, state_path, s3_fs)

        t1 = time.time()
        return {
            "new_files_processed": len(new_files),
            "total_processed": total_processed,
            "valid_count": 0,
            "quarantine_count": len(quarantine_records),
            "duplicate_count": duplicate_count,
            "silver_written_count": 0,
            "duration_sec": round(t1 - t0, 3)
        }

    # Derived Race Engineering Metrics Calculation
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

    for c, default_val in [("fuel_level", 0.0), ("downforce", 0.0), ("drag_coefficient", 0.35), ("wind_speed", 0.0)]:
        if c not in df_silver.columns:
            df_silver[c] = default_val

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
                lambda x: json.dumps(x, default=lambda obj: obj.tolist() if hasattr(obj, 'tolist') else str(obj)) if isinstance(x, (dict, list, np.ndarray)) else str(x)
            )

    # Append to partitioned Silver dataset
    table = pa.Table.from_pandas(df_silver)
    if is_s3_output:
        out_bucket, out_subpath = parse_s3_uri(output_dir)
        ensure_bucket_exists(out_bucket, s3_fs)
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
        os.makedirs(output_dir, exist_ok=True)
        pq.write_to_dataset(
            table,
            root_path=output_dir,
            partition_cols=["session_id", "date"] if "date" in df_silver.columns else ["session_id"],
            use_dictionary=True,
            compression="SNAPPY"
        )

    # Save updated state manifest
    processed_files_set.update(new_files)
    state["processed_files"] = sorted(list(processed_files_set))
    state["seen_event_ids"] = sorted(list(seen_event_ids_set))
    save_state_manifest(state, state_path, s3_fs)

    t1 = time.time()
    return {
        "new_files_processed": len(new_files),
        "total_processed": total_processed,
        "valid_count": len(valid_records),
        "quarantine_count": len(quarantine_records),
        "duplicate_count": duplicate_count,
        "silver_written_count": len(df_silver),
        "duration_sec": round(t1 - t0, 3)
    }
