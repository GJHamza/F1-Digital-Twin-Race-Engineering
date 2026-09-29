# -*- coding: utf-8 -*-
"""
Configuration Module for Phase G.4.4 Tire Degradation Modeling
Defines paths, horizon steps, split ratios, wheel definitions, targets, and feature columns.
"""

import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Storage Configuration
ETL_STORAGE_BACKEND = os.getenv("ETL_STORAGE_BACKEND", "local")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "f1-data-lake")

# Default Configurable Horizon Steps (t + 10)
DEFAULT_HORIZON_STEPS = int(os.getenv("TIRE_DEGRADATION_HORIZON", "10"))

# Local Storage Paths
LOCAL_SILVER_PATH = os.path.join(PROJECT_ROOT, "data_lake", "silver", "telemetry")
LOCAL_TIRE_PATH = os.path.join(PROJECT_ROOT, "data_lake", "ml", "tire_degradation")
LOCAL_MODELS_PATH = os.path.join(LOCAL_TIRE_PATH, "models")

# S3A MinIO Storage Paths
S3_SILVER_PATH = f"s3a://{MINIO_BUCKET}/silver/telemetry"
S3_TIRE_PATH = f"s3a://{MINIO_BUCKET}/ml/tire_degradation"
S3_MODELS_PATH = f"s3a://{MINIO_BUCKET}/ml/tire_degradation/models"


class TireDegradationConfig:
    """Configuration container for G.4.4 Tire Degradation Modeling."""

    def __init__(self, storage_backend=None, silver_source=None, output_dir=None, horizon_steps=None):
        self.storage_backend = storage_backend or ETL_STORAGE_BACKEND
        self.horizon_steps = horizon_steps if horizon_steps is not None else DEFAULT_HORIZON_STEPS
        self.random_state = 42

        if silver_source is not None:
            self.silver_source = silver_source
        else:
            self.silver_source = S3_SILVER_PATH if self.storage_backend == "minio" else LOCAL_SILVER_PATH

        if output_dir is not None:
            self.output_dir = output_dir
        else:
            self.output_dir = S3_TIRE_PATH if self.storage_backend == "minio" else LOCAL_TIRE_PATH

        self.models_dir = os.path.join(self.output_dir, "models") if not self.output_dir.startswith("s3") else f"{self.output_dir}/models"

        # Temporal Split Ratios (70% Train, 15% Validation, 15% Test)
        self.train_ratio = 0.70
        self.val_ratio = 0.15
        self.test_ratio = 0.15

        # 4 Wheel Positions
        self.wheel_positions = ["fl", "fr", "rl", "rr"]

        # Target Column Definitions (Future Wear Delta over H steps)
        self.target_columns = [
            "future_wear_delta_fl",
            "future_wear_delta_fr",
            "future_wear_delta_rl",
            "future_wear_delta_rr"
        ]

        # Feature Column Definitions (Available at observation t)
        self.feature_columns = [
            # Vehicle Dynamics & Performance
            "speed_kmh",
            "speed_ms",
            "acceleration_estimate",
            "g_force",

            # Individual Wheel Current Wear (%)
            "tire_wear_fl",
            "tire_wear_fr",
            "tire_wear_rl",
            "tire_wear_rr",

            # Individual Wheel Current Temperatures (°C)
            "tire_temp_fl",
            "tire_temp_fr",
            "tire_temp_rl",
            "tire_temp_rr",

            # Aggregated Tyre Metrics
            "tire_wear_avg",
            "tire_wear_max",
            "tire_temp_avg",
            "tire_temp_max",
            "tire_stress_index",
            "tire_wear_rate",

            # Aerodynamics
            "downforce",
            "drag_coefficient",
            "wind_speed",
            "aero_efficiency",

            # Powertrain & Fuel
            "rpm",
            "torque",
            "estimated_power_kw",
            "fuel_remaining_pct",

            # Historic Temporal / Previous Wear Rates (Backward-looking)
            "elapsed_time_sec",
            "previous_wear_delta_fl",
            "previous_wear_delta_fr",
            "previous_wear_delta_rl",
            "previous_wear_delta_rr",
        ]

        # Identifier Columns
        self.identifier_columns = [
            "event_id",
            "session_id",
            "car_id",
            "driver_id",
            "lap_number",
            "timestamp"
        ]
