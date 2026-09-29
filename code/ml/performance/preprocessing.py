# -*- coding: utf-8 -*-
"""
Dataset Preparation & Preprocessing Module for Phase G.4.3
Implements chronological 70/15/15 temporal splitting and Train-only StandardScaler fit/transform.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from ml.performance.config import PerformanceConfig


class PerformancePreprocessor:
    """
    StandardScaler wrapper for Performance Prediction.
    Fit strictly on Train partition to eliminate data leakage.
    """

    def __init__(self, feature_columns=None):
        self.feature_columns = feature_columns or PerformanceConfig().feature_columns
        self.scaler = StandardScaler()
        self.fill_values = {}
        self.is_fitted = False

    def fit(self, df_train: pd.DataFrame):
        """
        Fits median imputers and StandardScaler strictly on TRAIN partition.

        Args:
            df_train (pd.DataFrame): Train split DataFrame.
        """
        if df_train is None or df_train.empty:
            raise ValueError("Cannot fit preprocessor on empty train DataFrame.")

        # Compute medians for imputation strictly on Train
        X_train = df_train[self.feature_columns].copy()
        for col in self.feature_columns:
            median_val = float(X_train[col].median()) if col in X_train.columns and not X_train[col].dropna().empty else 0.0
            if np.isnan(median_val):
                median_val = 0.0
            self.fill_values[col] = median_val

        # Fill NaNs/infs for fitting
        X_train_clean = X_train.fillna(self.fill_values).replace([np.inf, -np.inf], 0.0)
        self.scaler.fit(X_train_clean)
        self.is_fitted = True

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transforms DataFrame features using pre-fitted parameters.

        Args:
            df (pd.DataFrame): Feature DataFrame (Train, Validation, or Test).

        Returns:
            np.ndarray: Scaled feature array.
        """
        if not self.is_fitted:
            raise RuntimeError("Preprocessor must be fitted on Train data before transform().")

        X = df[self.feature_columns].copy()
        X_clean = X.fillna(self.fill_values).replace([np.inf, -np.inf], 0.0)
        return self.scaler.transform(X_clean)

    def fit_transform(self, df_train: pd.DataFrame) -> np.ndarray:
        self.fit(df_train)
        return self.transform(df_train)


def perform_temporal_split(df_featured: pd.DataFrame, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15):
    """
    Splits the lap dataset chronologically into Train (70%), Validation (15%), and Test (15%).

    Args:
        df_featured (pd.DataFrame): Lap dataset with targets and features.
        train_ratio (float): Ratio for train partition (0.70).
        val_ratio (float): Ratio for validation partition (0.15).
        test_ratio (float): Ratio for test partition (0.15).

    Returns:
        tuple: (df_train, df_val, df_test, split_info)
    """
    if df_featured is None or df_featured.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, {"total_rows": 0, "train_count": 0, "val_count": 0, "test_count": 0}

    df_sorted = df_featured.sort_values(
        by=["session_id", "car_id", "lap_number"] if "session_id" in df_featured.columns else ["lap_number"]
    ).reset_index(drop=True)

    n_total = len(df_sorted)
    n_train = int(np.round(n_total * train_ratio))
    n_val = int(np.round(n_total * val_ratio))

    # Adjust to ensure exact coverage of all rows
    if n_train + n_val >= n_total and n_total > 2:
        n_train = max(1, n_total - 2)
        n_val = 1

    df_train = df_sorted.iloc[:n_train].copy()
    df_val = df_sorted.iloc[n_train:n_train + n_val].copy()
    df_test = df_sorted.iloc[n_train + n_val:].copy()

    split_info = {
        "total_rows": n_total,
        "train_count": len(df_train),
        "val_count": len(df_val),
        "test_count": len(df_test),
        "train_pct": round(len(df_train) / n_total * 100, 2),
        "val_pct": round(len(df_val) / n_total * 100, 2),
        "test_pct": round(len(df_test) / n_total * 100, 2),
    }

    return df_train, df_val, df_test, split_info


def prepare_performance_dataset(df_silver: pd.DataFrame, df_laps: pd.DataFrame, config=None):
    """
    Executes feature engineering, temporal split, and preprocessor fitting.

    Args:
        df_silver (pd.DataFrame): Telemetry dataset.
        df_laps (pd.DataFrame): Target lap dataset.
        config (PerformanceConfig, optional): Configuration object.

    Returns:
        tuple: (df_train, df_val, df_test, preprocessor, feature_cols, split_info)
    """
    from ml.performance.features import compute_pre_lap_features

    if config is None:
        config = PerformanceConfig()

    df_featured = compute_pre_lap_features(df_silver, df_laps)
    df_train, df_val, df_test, split_info = perform_temporal_split(
        df_featured,
        train_ratio=config.train_ratio,
        val_ratio=config.val_ratio,
        test_ratio=config.test_ratio
    )

    preprocessor = PerformancePreprocessor(feature_columns=config.feature_columns)
    if not df_train.empty:
        preprocessor.fit(df_train)

    return df_train, df_val, df_test, preprocessor, config.feature_columns, split_info
