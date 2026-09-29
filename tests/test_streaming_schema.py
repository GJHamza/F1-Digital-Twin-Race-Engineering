# -*- coding: utf-8 -*-
"""
Unit Tests for PySpark Streaming StructType Schema
Verifies schema structure, required fields, and compatibility with Schema V1 payloads.
"""

import os
import sys
import pytest

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from streaming.schema import get_telemetry_spark_schema
from pyspark.sql.types import StructType, DoubleType, StringType, IntegerType


def test_spark_schema_instantiation():
    """Verify PySpark StructType schema instantiates correctly with required top-level fields."""
    schema = get_telemetry_spark_schema()
    assert isinstance(schema, StructType)

    field_names = schema.fieldNames()
    required_top_level = [
        "schema_version",
        "session_id",
        "event_id",
        "car_id",
        "timestamp",
        "telemetry",
        "aerodynamics",
        "tires",
        "speed",
        "rpm",
        "gear"
    ]
    for fn in required_top_level:
        assert fn in field_names, f"Missing required top-level field '{fn}' in Spark schema"


def test_spark_schema_nested_structs():
    """Verify nested telemetry, aerodynamics, and tires struct fields."""
    schema = get_telemetry_spark_schema()

    telemetry_field = schema["telemetry"].dataType
    assert isinstance(telemetry_field, StructType)
    assert "speed" in telemetry_field.fieldNames()
    assert "rpm" in telemetry_field.fieldNames()
    assert "gear" in telemetry_field.fieldNames()

    aero_field = schema["aerodynamics"].dataType
    assert isinstance(aero_field, StructType)
    assert "downforce" in aero_field.fieldNames()
    assert "drag_coefficient" in aero_field.fieldNames()

    tires_field = schema["tires"].dataType
    assert isinstance(tires_field, StructType)
    assert "tire_temp" in tires_field.fieldNames()
    assert "tire_wear" in tires_field.fieldNames()
