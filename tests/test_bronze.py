# -*- coding: utf-8 -*-
"""
Automated Unit Tests for Bronze Layer ETL Writer
"""

import os
import sys
import tempfile
import pytest
import pandas as pd
import pyarrow.parquet as pq

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from etl.bronze.bronze_writer import write_bronze
from data_generator.generator_v2 import SyntheticGeneratorV2


@pytest.fixture
def sample_events():
    gen = SyntheticGeneratorV2(seed=42)
    return gen.generate_dataset("RACE_DRY", sessions_count=1, laps_per_session=2)


def test_write_bronze_from_list(sample_events):
    with tempfile.TemporaryDirectory() as tmpdir:
        report = write_bronze(sample_events, output_dir=tmpdir)

        assert report["total_records"] == len(sample_events)
        assert report["files_written"] >= 1
        assert report["duration_sec"] >= 0

        # Read back parquet files
        dataset = pq.ParquetDataset(tmpdir)
        df_read = dataset.read().to_pandas()

        assert len(df_read) == len(sample_events)
        assert "ingestion_timestamp" in df_read.columns
        assert "source" in df_read.columns
        assert "pipeline_version" in df_read.columns
        assert "date" in df_read.columns

        # Verify event_id preservation
        assert set(df_read["event_id"]) == set(e["event_id"] for e in sample_events)


def test_write_bronze_from_jsonl(sample_events):
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = os.path.join(tmpdir, "test_input.jsonl")
        import json
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for e in sample_events:
                f.write(json.dumps(e) + "\n")

        bronze_output = os.path.join(tmpdir, "bronze")
        report = write_bronze(jsonl_path, output_dir=bronze_output)

        assert report["total_records"] == len(sample_events)
        assert os.path.exists(bronze_output)


def test_write_bronze_empty_input():
    with tempfile.TemporaryDirectory() as tmpdir:
        report = write_bronze([], output_dir=tmpdir)
        assert report["total_records"] == 0
        assert report["files_written"] == 0
