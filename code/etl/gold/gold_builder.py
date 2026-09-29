# -*- coding: utf-8 -*-
"""
Gold Layer Builder for F1 Race Engineering Platform
Constructs 5 aggregated analytical datasets from Silver data:
1. lap_performance
2. tire_performance
3. fuel_performance
4. aero_performance
5. anomaly_summary

Supports Local Filesystem and MinIO S3A Object Storage backends.
"""

import os
import sys
import json
import time
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

from etl.config import ETL_GOLD_PATH, S3_GOLD_PATH, ETL_STORAGE_BACKEND
from datalake.s3_client import (
    get_s3_filesystem,
    ensure_bucket_exists,
    parse_s3_uri
)


def build_gold(silver_source, output_dir=None):
    """
    Constructs Gold analytical datasets from Silver telemetry data.

    Args:
        silver_source (str or DataFrame): Path/S3 URI to Silver Parquet dataset or pandas DataFrame.
        output_dir (str, optional): Target root directory or S3 URI for Gold Parquet datasets.

    Returns:
        dict: Summary of generated Gold datasets and record counts.
    """
    t0 = time.time()
    if output_dir is None:
        if ETL_STORAGE_BACKEND == "minio":
            output_dir = S3_GOLD_PATH
        else:
            output_dir = ETL_GOLD_PATH

    is_s3_output = output_dir.startswith("s3a://") or output_dir.startswith("s3://")

    s3_fs = None
    if is_s3_output or (isinstance(silver_source, str) and (silver_source.startswith("s3a://") or silver_source.startswith("s3://"))):
        s3_fs = get_s3_filesystem()

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

    # 1. Read Silver Dataset
    if isinstance(silver_source, pd.DataFrame):
        df_silver = silver_source.copy()
    elif isinstance(silver_source, list):
        df_silver = pd.DataFrame(silver_source)
    elif isinstance(silver_source, str):
        if silver_source.startswith("s3a://") or silver_source.startswith("s3://"):
            in_bucket, in_subpath = parse_s3_uri(silver_source)
            target_path = f"{in_bucket}/{in_subpath}".rstrip("/")
            try:
                dataset = pq.ParquetDataset(target_path, filesystem=s3_fs)
                df_silver = dataset.read().to_pandas()
            except Exception:
                df_silver = pd.DataFrame()
        elif os.path.isfile(silver_source) and silver_source.endswith('.jsonl'):
            records = []
            with open(silver_source, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            df_silver = pd.DataFrame(records)
        elif os.path.isdir(silver_source) or os.path.isfile(silver_source):
            try:
                dataset = pq.ParquetDataset(silver_source)
                df_silver = dataset.read().to_pandas()
            except Exception:
                files = []
                if os.path.isfile(silver_source):
                    files = [silver_source]
                else:
                    for root, _, filenames in os.walk(silver_source):
                        for fn in filenames:
                            if fn.endswith('.parquet'):
                                files.append(os.path.join(root, fn))
                if not files:
                    df_silver = pd.DataFrame()
                else:
                    df_silver = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        else:
            raise FileNotFoundError(f"Silver path not found: {silver_source}")
    else:
        raise ValueError("Invalid silver_source parameter type")

    if df_silver.empty:
        t1 = time.time()
        return {
            "gold_datasets_created": 0,
            "counts": {},
            "duration_sec": round(t1 - t0, 3)
        }

    counts = {}

    for col in ["session_id", "car_id", "lap_number", "speed_kmh", "g_force", "tire_temp_avg", "tire_temp_max", "tire_wear_avg", "tire_wear_max", "fuel_level", "downforce", "drag_coefficient", "wind_speed", "aero_efficiency", "tire_stress_index"]:
        if col not in df_silver.columns:
            df_silver[col] = 0.0

    df_silver["lap_number"] = pd.to_numeric(df_silver["lap_number"], errors="coerce").fillna(1).astype(int)

    # 1. LAP PERFORMANCE
    lap_rows = []
    for (sid, car, lap), group in df_silver.groupby(["session_id", "car_id", "lap_number"]):
        speed_avg = float(group["speed_kmh"].mean())
        speed_max = float(group["speed_kmh"].max())
        g_avg = float(group["g_force"].mean())
        t_temp_avg = float(group["tire_temp_avg"].mean())
        t_wear_avg = float(group["tire_wear_avg"].mean())
        
        fuel_start = float(group["fuel_level"].iloc[0])
        fuel_end = float(group["fuel_level"].iloc[-1])
        fuel_consumed = max(0.0, fuel_start - fuel_end)

        anom_count = int(group["anomaly_flag"].sum()) if "anomaly_flag" in group.columns else 0
        lap_time_ms = len(group) * 1000

        lap_rows.append({
            "session_id": sid,
            "car_id": car,
            "lap_number": lap,
            "lap_time_ms": lap_time_ms,
            "average_speed": round(speed_avg, 2),
            "max_speed": round(speed_max, 2),
            "average_g_force": round(g_avg, 3),
            "tire_temp_avg": round(t_temp_avg, 2),
            "tire_wear_avg": round(t_wear_avg, 2),
            "fuel_consumed": round(fuel_consumed, 3),
            "anomaly_count": anom_count
        })
    df_lap = pd.DataFrame(lap_rows)

    # 2. TIRE PERFORMANCE
    tire_rows = []
    for (sid, car, lap), group in df_silver.groupby(["session_id", "car_id", "lap_number"]):
        compound = str(group["tire_compound"].iloc[0]) if "tire_compound" in group.columns else "SOFT"
        avg_temp = float(group["tire_temp_avg"].mean())
        max_temp = float(group["tire_temp_max"].max())
        wear_start = float(group["tire_wear_avg"].iloc[0])
        wear_end = float(group["tire_wear_avg"].iloc[-1])
        wear_delta = max(0.0, wear_end - wear_start)
        tire_stress = float(group["tire_stress_index"].mean())

        tire_rows.append({
            "session_id": sid,
            "car_id": car,
            "lap_number": lap,
            "compound": compound,
            "avg_tire_temp": round(avg_temp, 2),
            "max_tire_temp": round(max_temp, 2),
            "tire_wear_delta": round(wear_delta, 3),
            "tire_stress": round(tire_stress, 3)
        })
    df_tire = pd.DataFrame(tire_rows)

    # 3. FUEL PERFORMANCE
    fuel_rows = []
    for (sid, car), group in df_silver.groupby(["session_id", "car_id"]):
        group_sorted = group.sort_values(by="timestamp")
        start_fuel = float(group_sorted["fuel_level"].iloc[0])
        end_fuel = float(group_sorted["fuel_level"].iloc[-1])
        total_consumed = max(0.0, start_fuel - end_fuel)
        total_laps = group["lap_number"].nunique()
        avg_per_lap = (total_consumed / total_laps) if total_laps > 0 else 0.0

        fuel_rows.append({
            "session_id": sid,
            "car_id": car,
            "starting_fuel": round(start_fuel, 2),
            "ending_fuel": round(end_fuel, 2),
            "fuel_consumed": round(total_consumed, 3),
            "avg_consumption_per_lap": round(avg_per_lap, 3)
        })
    df_fuel = pd.DataFrame(fuel_rows)

    # 4. AERO PERFORMANCE
    aero_rows = []
    for (sid, car, lap), group in df_silver.groupby(["session_id", "car_id", "lap_number"]):
        avg_sp = float(group["speed_kmh"].mean())
        avg_df = float(group["downforce"].mean())
        drag_c = float(group["drag_coefficient"].mean())
        eff = float(group["aero_efficiency"].mean())
        wind = float(group["wind_speed"].mean())

        aero_rows.append({
            "session_id": sid,
            "car_id": car,
            "lap_number": lap,
            "average_speed": round(avg_sp, 2),
            "average_downforce": round(avg_df, 2),
            "drag_coefficient": round(drag_c, 4),
            "aero_efficiency": round(eff, 4),
            "wind_speed": round(wind, 2)
        })
    df_aero = pd.DataFrame(aero_rows)

    # 5. ANOMALY SUMMARY
    anomaly_rows = []
    for idx, row in df_silver.iterrows():
        anoms = row.get("active_anomalies")
        if (anoms is None or (isinstance(anoms, float) and np.isnan(anoms))) and "active_anomalies_json" in row:
            anoms = row.get("active_anomalies_json")

        if isinstance(anoms, str):
            try:
                anoms = json.loads(anoms)
            except Exception:
                anoms = []

        if isinstance(anoms, (list, np.ndarray)):
            for a in anoms:
                if isinstance(a, str):
                    try:
                        a = json.loads(a)
                    except Exception:
                        pass
                if isinstance(a, dict):
                    anomaly_rows.append({
                        "session_id": row["session_id"],
                        "car_id": row["car_id"],
                        "lap_number": row["lap_number"],
                        "anomaly_type": a.get("type", "UNKNOWN"),
                        "severity": a.get("severity", "HIGH"),
                        "timestamp": row["timestamp"]
                    })

    if anomaly_rows:
        df_anom_raw = pd.DataFrame(anomaly_rows)
        anom_summary_rows = []
        for (sid, car, lap, atype, sev), group in df_anom_raw.groupby(["session_id", "car_id", "lap_number", "anomaly_type", "severity"]):
            timestamps = group["timestamp"].sort_values().values
            anom_summary_rows.append({
                "session_id": sid,
                "car_id": car,
                "lap_number": lap,
                "anomaly_type": atype,
                "severity": sev,
                "anomaly_count": len(group),
                "first_occurrence": str(timestamps[0]),
                "last_occurrence": str(timestamps[-1])
            })
        df_anom = pd.DataFrame(anom_summary_rows)
    else:
        df_anom = pd.DataFrame(columns=["session_id", "car_id", "lap_number", "anomaly_type", "severity", "anomaly_count", "first_occurrence", "last_occurrence"])

    gold_tables = {
        "lap_performance": df_lap,
        "tire_performance": df_tire,
        "fuel_performance": df_fuel,
        "aero_performance": df_aero,
        "anomaly_summary": df_anom
    }

    # Write each Gold dataset
    if is_s3_output:
        out_bucket, out_subpath = parse_s3_uri(output_dir)
        for name, df_dataset in gold_tables.items():
            tbl_path = f"{out_bucket}/{out_subpath}/{name}/{name}.parquet".replace("//", "/")
            pq.write_table(pa.Table.from_pandas(df_dataset), tbl_path, filesystem=s3_fs)
            counts[name] = len(df_dataset)
    else:
        for name, df_dataset in gold_tables.items():
            path_ds = os.path.join(output_dir, name)
            os.makedirs(path_ds, exist_ok=True)
            pq.write_table(pa.Table.from_pandas(df_dataset), os.path.join(path_ds, f"{name}.parquet"))
            counts[name] = len(df_dataset)

    t1 = time.time()
    return {
        "gold_datasets_created": len(gold_tables),
        "counts": counts,
        "output_dir": output_dir,
        "duration_sec": round(t1 - t0, 3)
    }
