# -*- coding: utf-8 -*-
"""
Anomaly Detection Configuration for Phase G.4.2 Telemetry Anomaly Detection
Manages model hyper-parameters, contamination rates, severity thresholds, and storage paths.
"""

import os
from ml.config import ETL_STORAGE_BACKEND, MINIO_BUCKET, PROJECT_ROOT, LOCAL_ML_PATH, S3_ML_PATH

# Storage Paths for Anomalies
LOCAL_ANOMALY_PATH = os.path.join(PROJECT_ROOT, "data_lake", "ml", "anomalies")
S3_ANOMALY_PATH = f"s3a://{MINIO_BUCKET}/ml/anomalies"


class AnomalyConfig:
    """Configuration container for Telemetry Anomaly Detection Engine."""

    def __init__(self, storage_backend=None, ml_source=None, output_dir=None):
        self.storage_backend = storage_backend or ETL_STORAGE_BACKEND

        if ml_source is not None:
            self.ml_source = ml_source
        else:
            self.ml_source = S3_ML_PATH if self.storage_backend == "minio" else LOCAL_ML_PATH

        if output_dir is not None:
            self.output_dir = output_dir
        else:
            self.output_dir = S3_ANOMALY_PATH if self.storage_backend == "minio" else LOCAL_ANOMALY_PATH

        # Model Hyperparameters
        self.random_state = 42
        self.contamination = 0.05
        self.n_estimators = 100
        self.model_version = "1.0.0"

        # Baseline Z-score threshold
        self.z_threshold = 3.0

        # Severity Quantile Calibration Thresholds (Calibrated on Validation set)
        self.severity_quantiles = {
            "LOW": 0.90,     # Top 10% anomaly score
            "MEDIUM": 0.95,  # Top 5% anomaly score
            "HIGH": 0.99     # Top 1% anomaly score
        }

        # Features to EXCLUDE from model training (Identifiers & timestamps)
        self.excluded_columns = [
            "event_id",
            "session_id",
            "car_id",
            "driver_id",
            "timestamp",
            "dt_timestamp",
            "rejection_reason",
            "rejected_at"
        ]
