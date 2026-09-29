# -*- coding: utf-8 -*-
"""
Automated Unit Tests for End-to-End ETL Pipeline Orchestration & Idempotency
"""

import os
import sys
import json
import tempfile
import pytest
import pyarrow.parquet as pq

# Ensure code directory is on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code')))

from etl.pipeline import run_pipeline
from data_generator.generator_v2 import SyntheticGeneratorV2


@pytest.fixture
def sample_jsonl_file():
    gen = SyntheticGeneratorV2(seed=42)
    events = gen.generate_dataset("RACE_DRY", sessions_count=2, laps_per_session=2)

    tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
    for e in events:
        tmp_file.write(json.dumps(e) + "\n")
    tmp_file.close()

    yield tmp_file.name, events

    if os.path.exists(tmp_file.name):
        os.remove(tmp_file.name)


def test_pipeline_end_to_end_all_layers(sample_jsonl_file):
    jsonl_path, raw_events = sample_jsonl_file

    with tempfile.TemporaryDirectory() as out_dir:
        results = run_pipeline(input_path=jsonl_path, output_base=out_dir, layer="all")

        assert "bronze" in results
        assert "silver" in results
        assert "gold" in results
        assert results["total_duration_sec"] > 0

        assert results["bronze"]["total_records"] == len(raw_events)
        assert results["silver"]["valid_count"] == len(raw_events)
        assert results["gold"]["counts"]["lap_performance"] == 4


def test_pipeline_idempotency(sample_jsonl_file):
    jsonl_path, raw_events = sample_jsonl_file

    with tempfile.TemporaryDirectory() as out_dir:
        # First execution
        res1 = run_pipeline(input_path=jsonl_path, output_base=out_dir, layer="all")

        silver_path = os.path.join(out_dir, "silver", "telemetry")
        dataset1 = pq.ParquetDataset(silver_path)
        count1 = len(dataset1.read())

        # Second execution (re-ingesting identical data to same output directory)
        res2 = run_pipeline(input_path=jsonl_path, output_base=out_dir, layer="all")

        dataset2 = pq.ParquetDataset(silver_path)
        count2 = len(dataset2.read())

        # Idempotency check: Record counts must be identical without duplicate inflation
        assert count1 == len(raw_events)
        assert count2 == len(raw_events)
        assert count1 == count2


def test_pipeline_individual_layers(sample_jsonl_file):
    jsonl_path, raw_events = sample_jsonl_file

    with tempfile.TemporaryDirectory() as out_dir:
        # Run Bronze only
        res_b = run_pipeline(input_path=jsonl_path, output_base=out_dir, layer="bronze")
        assert "bronze" in res_b
        assert "silver" not in res_b
        assert "gold" not in res_b

        # Run Silver only
        res_s = run_pipeline(input_path=jsonl_path, output_base=out_dir, layer="silver")
        assert "silver" in res_s

        # Run Gold only
        res_g = run_pipeline(input_path=jsonl_path, output_base=out_dir, layer="gold")
        assert "gold" in res_g
