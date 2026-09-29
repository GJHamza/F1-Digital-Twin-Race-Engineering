# -*- coding: utf-8 -*-
"""
Streaming & Incremental ETL Orchestrator CLI for F1 Digital Twin
Connects: Kafka -> PySpark Structured Streaming (Bronze) -> Silver Incremental -> Gold Incremental.
"""

import os
import sys
import time
import argparse

ETL_DIR = os.path.abspath(os.path.dirname(__file__))
CODE_DIR = os.path.abspath(os.path.join(ETL_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(CODE_DIR, ".."))
for p in [ETL_DIR, CODE_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from streaming.config import StreamingConfig
from streaming.telemetry_stream import run_streaming_pipeline
from etl.silver.incremental_transformer import transform_silver_incremental
from etl.gold.incremental_builder import build_gold_incremental


def run_full_incremental_pipeline(
    config=None,
    once=True,
    bronze_path=None,
    silver_path=None,
    quarantine_path=None,
    gold_path=None,
    state_path=None
):
    """
    Executes full streaming & incremental ETL pipeline cycle:
    1. PySpark Structured Streaming (Kafka -> Bronze MinIO)
    2. Silver Incremental (Validation, Cleaning, Deduplication, Derived Metrics, Quarantine)
    3. Gold Incremental (5 Analytical Datasets update)
    """
    t_start = time.time()
    if config is None:
        config = StreamingConfig()

    results = {}

    # 1. STREAMING BRONZE
    print("\n[STEP 1 - BRONZE STREAMING] Ingesting Kafka stream into Bronze MinIO...", flush=True)
    run_streaming_pipeline(config=config, once=once, starting_offsets="earliest")
    results["bronze_streaming"] = "COMPLETED"

    # 2. SILVER INCREMENTAL
    print("\n[STEP 2 - SILVER INCREMENTAL] Processing Bronze delta into Silver Incremental...", flush=True)
    silver_res = transform_silver_incremental(
        bronze_source=bronze_path or config.bronze_path,
        output_dir=silver_path,
        quarantine_dir=quarantine_path,
        state_path=state_path
    )
    results["silver_incremental"] = silver_res
    print(f"[SILVER INCREMENTAL] New Bronze files processed: {silver_res['new_files_processed']}", flush=True)
    print(f"[SILVER INCREMENTAL] Valid records added: {silver_res['valid_count']}", flush=True)
    print(f"[SILVER INCREMENTAL] Quarantine records: {silver_res['quarantine_count']}", flush=True)
    print(f"[SILVER INCREMENTAL] Duplicates skipped: {silver_res['duplicate_count']}", flush=True)

    # 3. GOLD INCREMENTAL
    print("\n[STEP 3 - GOLD INCREMENTAL] Updating 5 Gold analytical datasets...", flush=True)
    gold_res = build_gold_incremental(
        silver_source=silver_path,
        output_dir=gold_path
    )
    results["gold_incremental"] = gold_res
    print(f"[GOLD INCREMENTAL] Datasets updated: {gold_res['gold_datasets_updated']}", flush=True)
    print(f"[GOLD INCREMENTAL] Counts: {gold_res['counts']}", flush=True)

    t_end = time.time()
    total_duration = round(t_end - t_start, 3)
    results["total_duration_sec"] = total_duration

    print(f"\n[SUCCESS] Full Incremental Streaming ETL Pipeline completed in {total_duration}s!", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="F1 Telemetry Streaming Incremental ETL Orchestrator")
    parser.add_argument("--once", action="store_true", default=True, help="Run single micro-batch cycle and exit")
    args = parser.parse_args()

    run_full_incremental_pipeline(once=args.once)


if __name__ == "__main__":
    main()
