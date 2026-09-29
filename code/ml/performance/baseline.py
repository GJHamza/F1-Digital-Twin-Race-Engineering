# -*- coding: utf-8 -*-
"""
Baseline Models Module for Phase G.4.3
Provides Mean Baseline and Previous-Lap Baseline models for comparative regression benchmark.
"""

import numpy as np
import pandas as pd


class MeanBaselineModel:
    """
    Mean Baseline Model: Always predicts the arithmetic mean of lap_time_sec from the Train partition.
    """

    def __init__(self):
        self.model_name = "Mean Baseline"
        self.mean_target = 0.0
        self.is_fitted = False

    def fit(self, X_train, y_train):
        """
        Calculates the mean of y_train.

        Args:
            X_train: Ignored.
            y_train (pd.Series or np.ndarray): Training target lap times.
        """
        y_arr = np.asarray(y_train, dtype=float)
        if len(y_arr) == 0:
            self.mean_target = 60.0
        else:
            self.mean_target = float(np.mean(y_arr))
        self.is_fitted = True

    def predict(self, X) -> np.ndarray:
        """
        Predicts mean target for all samples.

        Args:
            X: Input dataset (DataFrame or array).

        Returns:
            np.ndarray: Constant mean predictions.
        """
        if not self.is_fitted:
            raise RuntimeError("MeanBaselineModel must be fitted before predict().")
        n_samples = len(X) if hasattr(X, "__len__") else 1
        return np.full(n_samples, self.mean_target, dtype=float)


class PreviousLapBaselineModel:
    """
    Previous-Lap Baseline Model: Predicts current lap time using previous_lap_time_sec feature.
    Falls back to Train target mean when previous lap time is unavailable.
    """

    def __init__(self):
        self.model_name = "Previous-Lap Baseline"
        self.fallback_mean = 60.0
        self.is_fitted = False

    def fit(self, X_train, y_train):
        """
        Saves Train mean target for fallback.

        Args:
            X_train: Training features.
            y_train: Training target lap times.
        """
        y_arr = np.asarray(y_train, dtype=float)
        if len(y_arr) > 0:
            self.fallback_mean = float(np.mean(y_arr))
        self.is_fitted = True

    def predict(self, df_or_X) -> np.ndarray:
        """
        Predicts using previous_lap_time_sec feature.

        Args:
            df_or_X: DataFrame containing 'previous_lap_time_sec' column or array.

        Returns:
            np.ndarray: Previous lap time predictions.
        """
        if not self.is_fitted:
            raise RuntimeError("PreviousLapBaselineModel must be fitted before predict().")

        if isinstance(df_or_X, pd.DataFrame) and "previous_lap_time_sec" in df_or_X.columns:
            preds = df_or_X["previous_lap_time_sec"].fillna(self.fallback_mean).to_numpy(dtype=float)
            return preds
        elif hasattr(df_or_X, "__len__"):
            return np.full(len(df_or_X), self.fallback_mean, dtype=float)
        else:
            return np.array([self.fallback_mean], dtype=float)
