# -*- coding: utf-8 -*-
"""
PySpark StructType Schema Definition for F1 Telemetry V1 Payload
Enforces explicit typing and compatibility across Schema V1 and legacy flat payloads.
"""

from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
    ArrayType,
    TimestampType
)


def get_telemetry_spark_schema():
    """
    Returns explicit PySpark StructType schema matching Schema V1 telemetry events.
    """
    telemetry_struct = StructType([
        StructField("speed", DoubleType(), True),
        StructField("rpm", IntegerType(), True),
        StructField("gear", IntegerType(), True),
        StructField("torque", DoubleType(), True),
        StructField("g_force", DoubleType(), True),
        StructField("pos_x", DoubleType(), True),
        StructField("pos_z", DoubleType(), True),
        StructField("acceleration", DoubleType(), True),
        StructField("steering", DoubleType(), True),
        StructField("throttle", DoubleType(), True),
        StructField("brake", DoubleType(), True),
        StructField("drs_active", DoubleType(), True),
        StructField("ers_store", DoubleType(), True)
    ])

    aerodynamics_struct = StructType([
        StructField("wind_speed", DoubleType(), True),
        StructField("drag_coefficient", DoubleType(), True),
        StructField("downforce", DoubleType(), True),
        StructField("front_wing_angle", DoubleType(), True),
        StructField("rear_wing_angle", DoubleType(), True)
    ])

    tires_struct = StructType([
        StructField("tire_temp", ArrayType(DoubleType()), True),
        StructField("tire_wear", ArrayType(DoubleType()), True),
        StructField("tire_compound", StringType(), True),
        StructField("tire_pressure", ArrayType(DoubleType()), True)
    ])

    anomaly_struct = StructType([
        StructField("type", StringType(), True),
        StructField("severity", StringType(), True),
        StructField("message", StringType(), True)
    ])

    return StructType([
        # Metadata
        StructField("schema_version", StringType(), True),
        StructField("session_id", StringType(), True),
        StructField("event_id", StringType(), True),
        StructField("car_id", StringType(), True),
        StructField("car_name", StringType(), True),
        StructField("team", StringType(), True),
        StructField("driver_id", StringType(), True),
        StructField("driver_name", StringType(), True),
        StructField("lap_number", IntegerType(), True),
        StructField("timestamp", StringType(), True),
        StructField("fuel_level", DoubleType(), True),

        # Nested V1 Objects
        StructField("telemetry", telemetry_struct, True),
        StructField("aerodynamics", aerodynamics_struct, True),
        StructField("tires", tires_struct, True),
        StructField("active_anomalies", StringType(), True),


        # Backwards-Compatible Flat Fields
        StructField("speed", DoubleType(), True),
        StructField("rpm", IntegerType(), True),
        StructField("gear", IntegerType(), True),
        StructField("torque", DoubleType(), True),
        StructField("g_force", DoubleType(), True),
        StructField("downforce", DoubleType(), True),
        StructField("drag_coefficient", DoubleType(), True),
        StructField("wind_speed", DoubleType(), True),
        StructField("pos_x", DoubleType(), True),
        StructField("pos_z", DoubleType(), True)
    ])
