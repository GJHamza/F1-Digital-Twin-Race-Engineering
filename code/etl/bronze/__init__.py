# -*- coding: utf-8 -*-
"""
Bronze Layer Module for F1 Data Engineering ETL
Converts raw JSONL events into immutable, partitioned Parquet files.
"""

from .bronze_writer import write_bronze

__all__ = ["write_bronze"]
