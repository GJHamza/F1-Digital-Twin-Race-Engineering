# -*- coding: utf-8 -*-
"""
Baseline Models Module for Phase G.4.4 Tire Degradation Modeling
Provides Zero Degradation Baseline and Previous Degradation Baseline for comparative benchmarks.
"""

import numpy as np
import pandas as pd


class ZeroDegradationBaseline:
    """
    Zero Degradation Baseline: Always predicts future_wear_delta = 0.0 for all 4 wheels.
    """

    def __init__(self):
        self.model_name = "Zero Degradation Baseline"
        self.is_fitted = False

    def fit(self, X_train, y_train):
        """No-op fit."""
        self.is_fitted = True

    def predict(self, X) -> np.ndarray:
        """
        Predicts 0.0 delta for all 4 wheels.

        Args:
            X: Input feature dataset or array.

        Returns:
            np.ndarray: Array of shape (n_samples, 4) filled with 0.0.
        """
        if not self.is_fitted:
            raise RuntimeError("ZeroDegradationBaseline must be fitted before predict().")

        n_samples = len(X) if hasattr(X, "__len__") else 1
        return np.zeros((n_samples, 4), dtype=float)


class PreviousDegradationBaseline:
    """
    Previous Degradation Baseline: Extrapolates future wear delta using previous wear deltas.
    Falls back to Train mean deltas when previous deltas are unavailable.
    """

    def __init__(self, horizon_steps: int = 10):
        self.model_name = "Previous Degradation Baseline"
        self.horizon_steps = horizon_steps
        self.fallback_deltas = np.zeros(4, dtype=float)
        self.is_fitted = False

    def fit(self, X_train, y_train):
        """
        Computes mean target deltas from Train partition for fallback.

        Args:
            X_train: Training features.
            y_train: Training target deltas array of shape (n, 4).
        """
        y_arr = np.asarray(y_train, dtype=float)
        if len(y_arr) > 0 and y_arr.ndim == 2 and y_arr.shape[1] == 4:
            self.fallback_deltas = np.mean(y_arr, axis=0)
        self.is_fitted = True

    def predict(self, df_or_X) -> np.ndarray:
        """
        Predicts using previous_wear_delta_fl, fr, rl, rr columns.

        Args:
            df_or_X: DataFrame or array.

        Returns:
            np.ndarray: Extrapolated deltas array of shape (n_samples, 4).
        """
        if not self.is_fitted:
            raise RuntimeError("PreviousDegradationBaseline must be fitted before predict().")

        positions = ["fl", "fr", "rl", "rr"]
        if isinstance(df_or_X, pd.DataFrame):
            n_samples = len(df_or_X)
            preds = np.zeros((n_samples, 4), dtype=float)
            for idx, pos in enumerate(positions):
                col = f"previous_wear_delta_{pos}"
                if col in df_or_X.columns:
                    preds[:, idx] = df_or_X[col].fillna(self.fallback_deltas[idx]).to_numpy(dtype=float)
                else:
                    preds[:, idx] = self.fallback_deltas[idx]
            return preds
        elif hasattr(df_or_X, "__len__"):
            n_samples = len(df_or_X)
            return np.tile(self.fallback_deltas, (n_samples, 1))
        else:
            return self.fallback_deltas.reshape(1, 4)
