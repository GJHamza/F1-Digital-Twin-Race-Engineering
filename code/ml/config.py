# -*- coding: utf-8 -*-
"""
ML Dataset Configuration for Phase G.4.1 Feature Engineering & ML Foundation
Manages paths, storage backends, temporal split ratios, and feature lists.
"""

import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Storage Configuration
ETL_STORAGE_BACKEND = os.getenv("ETL_STORAGE_BACKEND", "local")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")

# Local Storage Paths
LOCAL_SILVER_PATH = os.path.join(PROJECT_ROOT, "data_lake", "silver", "telemetry")
LOCAL_ML_PATH = os.path.join(PROJECT_ROOT, "data_lake", "ml", "features")

# S3A MinIO Storage Paths
S3_SILVER_PATH = f"s3a://{MINIO_BUCKET}/silver/telemetry"
S3_ML_PATH = f"s3a://{MINIO_BUCKET}/ml/features"


class MLConfig:
    """Configuration container for ML Feature Engineering & Dataset Generation."""

    def __init__(self, storage_backend=None, silver_source=None, output_dir=None):
        self.storage_backend = storage_backend or ETL_STORAGE_BACKEND

        if silver_source is not None:
            self.silver_source = silver_source
        else:
            self.silver_source = S3_SILVER_PATH if self.storage_backend == "minio" else LOCAL_SILVER_PATH

        if output_dir is not None:
            self.output_dir = output_dir
        else:
            self.output_dir = S3_ML_PATH if self.storage_backend == "minio" else LOCAL_ML_PATH

        # Temporal Split Ratios (Default: 70% Train, 15% Validation, 15% Test)
        self.train_ratio = 0.70
        self.val_ratio = 0.15
        self.test_ratio = 0.15

        # Feature Column Definitions
        self.feature_columns = [
            # Performance Features
            "speed_kmh",
            "speed_ms",
            "acceleration_estimate",
            "g_force",

            # Tyre Features
            "tire_temp_avg",
            "tire_temp_max",
            "tire_wear_avg",
            "tire_wear_max",
            "tire_stress_index",
            "tire_wear_rate",

            # Aerodynamic Features
            "downforce",
            "drag_coefficient",
            "wind_speed",
            "aero_efficiency",
            "downforce_per_speed",

            # Powertrain Features
            "rpm",
            "torque",
            "torque_per_rpm",
            "estimated_power_kw",
            "fuel_level",
            "fuel_remaining_pct",

            # Temporal / Rolling Features
            "elapsed_time_sec",
            "rolling_speed_mean_5",
            "rolling_speed_std_5",
            "rolling_tire_temp_5",
            "rolling_tire_wear_5",
        ]

        self.identifier_columns = [
            "event_id",
            "session_id",
            "car_id",
            "driver_id",
            "lap_number",
            "timestamp"
        ]
