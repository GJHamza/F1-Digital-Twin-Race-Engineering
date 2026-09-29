# -*- coding: utf-8 -*-
"""
Isolation Forest Anomaly Detector Model Wrapper for Phase G.4.2
Wraps sklearn IsolationForest for reproducible unsupervised telemetry anomaly detection.
STRICT DATA LEAKAGE PREVENTION: Model is fit ONLY on Train partition.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


class IsolationForestDetector:
    """Wrapper for Scikit-learn IsolationForest anomaly detector."""

    def __init__(self, n_estimators=100, contamination=0.05, random_state=42):
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.is_fitted = False

    def fit(self, X_train):
        """
        Fits Isolation Forest model strictly on Train feature matrix.

        Args:
            X_train (np.ndarray or pd.DataFrame): Training scaled feature matrix.

        Returns:
            self
        """
        matrix = X_train.values if isinstance(X_train, pd.DataFrame) else np.asarray(X_train)
        self.model.fit(matrix)
        self.is_fitted = True
        return self

    def decision_function(self, X):
        """
        Computes raw decision function scores from Isolation Forest.
        Note: Lower decision scores indicate more anomalous points.

        Args:
            X (np.ndarray or pd.DataFrame): Feature matrix.

        Returns:
            np.ndarray: Raw decision function scores.
        """
        if not self.is_fitted:
            raise RuntimeError("IsolationForestDetector must be fit on Train before decision_function")

        matrix = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        return self.model.decision_function(matrix)

    def predict(self, X):
        """
        Predicts binary anomaly status (1 for anomaly, 0 for normal).
        Note: sklearn IsolationForest outputs -1 for anomaly, 1 for normal.
        We map -1 -> 1 (Anomaly) and 1 -> 0 (Normal).

        Args:
            X (np.ndarray or pd.DataFrame): Feature matrix.

        Returns:
            np.ndarray: Binary label array (0 for normal, 1 for anomaly).
        """
        if not self.is_fitted:
            raise RuntimeError("IsolationForestDetector must be fit on Train before predict")

        matrix = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        raw_preds = self.model.predict(matrix)
        return np.where(raw_preds == -1, 1, 0)
