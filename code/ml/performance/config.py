# -*- coding: utf-8 -*-
"""
Performance Prediction Configuration for Phase G.4.3
Defines storage locations, temporal split ratios, feature list, target column, and model hyper-parameters.
"""

import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Storage Configuration
ETL_STORAGE_BACKEND = os.getenv("ETL_STORAGE_BACKEND", "local")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")

# Local Storage Paths
LOCAL_SILVER_PATH = os.path.join(PROJECT_ROOT, "data_lake", "silver", "telemetry")
LOCAL_PERFORMANCE_PATH = os.path.join(PROJECT_ROOT, "data_lake", "ml", "performance")
LOCAL_MODELS_PATH = os.path.join(LOCAL_PERFORMANCE_PATH, "models")

# S3A MinIO Storage Paths
S3_SILVER_PATH = f"s3a://{MINIO_BUCKET}/silver/telemetry"
S3_PERFORMANCE_PATH = f"s3a://{MINIO_BUCKET}/ml/performance"
S3_MODELS_PATH = f"s3a://{MINIO_BUCKET}/ml/performance/models"


class PerformanceConfig:
    """Configuration class for G.4.3 Lap Time / Performance Prediction."""

    def __init__(self, storage_backend=None, silver_source=None, output_dir=None):
        self.storage_backend = storage_backend or ETL_STORAGE_BACKEND
        self.random_state = 42

        if silver_source is not None:
            self.silver_source = silver_source
        else:
            self.silver_source = S3_SILVER_PATH if self.storage_backend == "minio" else LOCAL_SILVER_PATH

        if output_dir is not None:
            self.output_dir = output_dir
        else:
            self.output_dir = S3_PERFORMANCE_PATH if self.storage_backend == "minio" else LOCAL_PERFORMANCE_PATH

        self.models_dir = os.path.join(self.output_dir, "models") if not self.output_dir.startswith("s3") else f"{self.output_dir}/models"

        # Temporal Split Ratios (70% Train, 15% Validation, 15% Test)
        self.train_ratio = 0.70
        self.val_ratio = 0.15
        self.test_ratio = 0.15

        # Target Column Definition
        self.target_column = "lap_time_sec"

        # Predictor Feature Definitions (Available before/at lap start or from previous laps)
        self.feature_columns = [
            # Pre-lap / Historic Performance Features
            "average_speed_before_lap",
            "max_speed_before_lap",
            "average_acceleration_before_lap",
            "average_g_force_before_lap",

            # Pre-lap Tyre Features
            "tire_temp_avg_before_lap",
            "tire_temp_max_before_lap",
            "tire_wear_avg_before_lap",
            "tire_wear_max_before_lap",
            "tire_stress_index_before_lap",
            "tire_wear_rate_before_lap",

            # Pre-lap Aerodynamic Features
            "average_downforce_before_lap",
            "average_drag_coefficient_before_lap",
            "average_wind_speed_before_lap",
            "average_aero_efficiency_before_lap",

            # Pre-lap Powertrain Features
            "average_rpm_before_lap",
            "average_torque_before_lap",
            "estimated_power_kw_before_lap",
            "fuel_remaining_pct_before_lap",

            # Temporal / Context Features
            "previous_lap_time_sec",
            "rolling_lap_time_mean",
            "rolling_lap_time_std",
            "elapsed_session_time_sec",
            "lap_number",
        ]

        # Identifier Columns
        self.identifier_columns = [
            "lap_id",
            "session_id",
            "car_id",
            "driver_id",
            "lap_number",
            "lap_start_timestamp",
            "lap_end_timestamp"
        ]
