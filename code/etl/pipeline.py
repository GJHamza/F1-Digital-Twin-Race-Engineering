# -*- coding: utf-8 -*-
"""
End-to-End Data Engineering Pipeline CLI Entrypoint for F1 Digital Twin
Orchestrates Bronze, Silver, and Gold ETL transformation layers.
"""

import os
import sys
import argparse
import time

# Ensure code directory is on import path
PROJECT_CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_CODE_DIR not in sys.path:
    sys.path.insert(0, PROJECT_CODE_DIR)

from etl.config import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_BASE,
    ETL_BRONZE_PATH,
    ETL_SILVER_PATH,
    ETL_QUARANTINE_PATH,
    ETL_GOLD_PATH
)
from etl.bronze.bronze_writer import write_bronze
from etl.silver.silver_transformer import transform_silver
from etl.gold.gold_builder import build_gold


def run_pipeline(input_path=DEFAULT_INPUT_PATH, output_base=DEFAULT_OUTPUT_BASE, layer="all"):
    """
    Executes the F1 Data Engineering Pipeline.

    Args:
        input_path (str): Path to input JSONL file or directory.
        output_base (str): Base output directory for Bronze, Silver, and Gold layers.
        layer (str): Target layer ('bronze', 'silver', 'gold', or 'all').

    Returns:
        dict: Summary execution metrics across layers.
    """
    t_start = time.time()

    if output_base.startswith("s3a://") or output_base.startswith("s3://"):
        base_clean = output_base.rstrip("/")
        bronze_dir = f"{base_clean}/bronze/telemetry"
        silver_dir = f"{base_clean}/silver/telemetry"
        quarantine_dir = f"{base_clean}/quarantine/telemetry"
        gold_dir = f"{base_clean}/gold"
    else:
        bronze_dir = os.path.join(output_base, "bronze", "telemetry")
        silver_dir = os.path.join(output_base, "silver", "telemetry")
        quarantine_dir = os.path.join(output_base, "quarantine", "telemetry")
        gold_dir = os.path.join(output_base, "gold")


    results = {}

    layer = layer.lower()
    run_bronze = layer in ["bronze", "all"]
    run_silver = layer in ["silver", "all"]
    run_gold = layer in ["gold", "all"]

    # --- BRONZE LAYER ---
    if run_bronze:
        print(f"\n[BRONZE] Starting Bronze Layer Ingestion from '{input_path}'...", flush=True)
        bronze_report = write_bronze(input_path, output_dir=bronze_dir)
        results["bronze"] = bronze_report
        print(f"[BRONZE] Records ingested: {bronze_report['total_records']}", flush=True)
        print(f"[BRONZE] Files written to: {bronze_report['output_dir']}", flush=True)
        print(f"[BRONZE] Execution time: {bronze_report['duration_sec']}s", flush=True)

    # --- SILVER LAYER ---
    if run_silver:
        silver_input = bronze_dir if run_bronze else input_path
        print(f"\n[SILVER] Starting Silver Transformation & Quality Checks...", flush=True)
        silver_report = transform_silver(silver_input, output_dir=silver_dir, quarantine_dir=quarantine_dir)
        results["silver"] = silver_report
        print(f"[SILVER] Valid records: {silver_report['valid_count']}", flush=True)
        print(f"[SILVER] Rejected/Quarantine records: {silver_report['quarantine_count']}", flush=True)
        print(f"[SILVER] Duplicate records skipped: {silver_report['duplicate_count']}", flush=True)
        print(f"[SILVER] Execution time: {silver_report['duration_sec']}s", flush=True)

    # --- GOLD LAYER ---
    if run_gold:
        gold_input = silver_dir if run_silver else input_path
        print(f"\n[GOLD] Building Gold Analytical Datasets...", flush=True)
        gold_report = build_gold(gold_input, output_dir=gold_dir)
        results["gold"] = gold_report
        print(f"[GOLD] Lap performance records: {gold_report['counts'].get('lap_performance', 0)}", flush=True)
        print(f"[GOLD] Tire performance records: {gold_report['counts'].get('tire_performance', 0)}", flush=True)
        print(f"[GOLD] Fuel performance records: {gold_report['counts'].get('fuel_performance', 0)}", flush=True)
        print(f"[GOLD] Aero performance records: {gold_report['counts'].get('aero_performance', 0)}", flush=True)
        print(f"[GOLD] Anomaly summary records: {gold_report['counts'].get('anomaly_summary', 0)}", flush=True)
        print(f"[GOLD] Execution time: {gold_report['duration_sec']}s", flush=True)

    t_end = time.time()
    total_duration = round(t_end - t_start, 3)
    results["total_duration_sec"] = total_duration

    print(f"\n[SUCCESS] ETL Pipeline Completed Successfully in {total_duration}s!", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="F1 Data Engineering ETL Pipeline CLI")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT_PATH, help="Path to input JSONL file or directory")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_BASE, help="Base output directory for Parquet data lake")
    parser.add_argument("--layer", "-l", type=str, choices=["bronze", "silver", "gold", "all"], default="all", help="Pipeline layer to execute")

    args = parser.parse_args()
    run_pipeline(input_path=args.input, output_base=args.output, layer=args.layer)


if __name__ == "__main__":
    main()
