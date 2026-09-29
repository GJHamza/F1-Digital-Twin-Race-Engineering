# -*- coding: utf-8 -*-
"""
Statistical Baseline Anomaly Detector for Phase G.4.2
Computes Z-score / IQR statistical deviations as a reference baseline against Isolation Forest.
STRICT DATA LEAKAGE PREVENTION: Means and Standard Deviations are fit ONLY on Train partition.
"""

import pandas as pd
import numpy as np


class ZScoreBaselineDetector:
    """Statistical Z-score Baseline Anomaly Detector."""

    def __init__(self, z_threshold=3.0):
        self.z_threshold = z_threshold
        self.means = None
        self.stds = None
        self.feature_names = None
        self.is_fitted = False

    def fit(self, X_train, feature_names=None):
        """
        Fits baseline mean and standard deviation on scaled or raw Train feature matrix.

        Args:
            X_train (np.ndarray or pd.DataFrame): Training feature matrix.
            feature_names (list, optional): List of feature names.

        Returns:
            self
        """
        if isinstance(X_train, pd.DataFrame):
            self.feature_names = list(X_train.columns)
            matrix = X_train.values
        else:
            self.feature_names = feature_names
            matrix = np.asarray(X_train)

        self.means = np.mean(matrix, axis=0)
        self.stds = np.std(matrix, axis=0)
        # Avoid division by zero for constant features
        self.stds[self.stds == 0.0] = 1e-5

        self.is_fitted = True
        return self

    def predict_score(self, X):
        """
        Computes maximum absolute Z-score across features for each sample.

        Args:
            X (np.ndarray or pd.DataFrame): Feature matrix.

        Returns:
            np.ndarray: Max Z-score array.
        """
        if not self.is_fitted:
            raise RuntimeError("ZScoreBaselineDetector must be fit on Train before scoring")

        matrix = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        z_scores = np.abs((matrix - self.means) / self.stds)
        max_z = np.max(z_scores, axis=1)
        return max_z

    def predict_label(self, X):
        """
        Predicts binary anomaly label (1 if max Z-score > z_threshold, 0 otherwise).

        Args:
            X (np.ndarray or pd.DataFrame): Feature matrix.

        Returns:
            np.ndarray: Binary label array (0 or 1).
        """
        max_z = self.predict_score(X)
        return (max_z > self.z_threshold).astype(int)
