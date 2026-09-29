# -*- coding: utf-8 -*-
"""
Regression Models Module for Phase G.4.3
Wraps Scikit-Learn RandomForestRegressor and GradientBoostingRegressor with reproducibility and feature importances.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from ml.performance.config import PerformanceConfig


class PerformanceRegressionModel:
    """
    Wrapper for Scikit-Learn ML Regression models with fixed random_state=42.
    """

    def __init__(self, model_type="random_forest", random_state=42, n_estimators=100, **kwargs):
        self.model_type = model_type
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.is_fitted = False

        if model_type in ["random_forest", "rf"]:
            self.model_name = "RandomForestRegressor"
            self.model = RandomForestRegressor(
                n_estimators=n_estimators,
                random_state=random_state,
                **kwargs
            )
        elif model_type in ["gradient_boosting", "gbr", "gb"]:
            self.model_name = "GradientBoostingRegressor"
            self.model = GradientBoostingRegressor(
                n_estimators=n_estimators,
                random_state=random_state,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported model_type: '{model_type}'. Choose 'random_forest' or 'gradient_boosting'.")

    def fit(self, X_train, y_train):
        """
        Trains regressor model on training features and targets.

        Args:
            X_train (np.ndarray or pd.DataFrame): Scaled training features.
            y_train (pd.Series or np.ndarray): Target lap times.
        """
        X_arr = np.asarray(X_train, dtype=float)
        y_arr = np.asarray(y_train, dtype=float)

        if len(X_arr) == 0:
            raise ValueError("Cannot fit model on empty training data.")

        self.model.fit(X_arr, y_arr)
        self.is_fitted = True

    def predict(self, X) -> np.ndarray:
        """
        Predicts lap times for given feature matrix.

        Args:
            X (np.ndarray or pd.DataFrame): Feature matrix.

        Returns:
            np.ndarray: Predicted lap times in seconds.
        """
        if not self.is_fitted:
            raise RuntimeError(f"{self.model_name} must be fitted before calling predict().")

        X_arr = np.asarray(X, dtype=float)
        return self.model.predict(X_arr)

    def get_feature_importances(self, feature_names=None) -> pd.DataFrame:
        """
        Extracts feature importances and returns a sorted DataFrame.

        Args:
            feature_names (list, optional): List of feature names matching columns.

        Returns:
            pd.DataFrame: Feature importances sorted in descending order.
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before extracting feature importances.")

        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        else:
            importances = np.zeros(len(feature_names or []))

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(len(importances))]

        df_imp = pd.DataFrame({
            "feature": feature_names,
            "importance": importances
        }).sort_values(by="importance", ascending=False).reset_index(drop=True)

        return df_imp

    def save(self, filepath: str, metadata: dict = None):
        """
        Persists model artifact and metadata to disk.

        Args:
            filepath (str): Target file path.
            metadata (dict, optional): Associated training metadata.
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        payload = {
            "model_name": self.model_name,
            "model_type": self.model_type,
            "random_state": self.random_state,
            "n_estimators": self.n_estimators,
            "model": self.model,
            "metadata": metadata or {}
        }
        joblib.dump(payload, filepath)

    @classmethod
    def load(cls, filepath: str):
        """
        Loads saved model artifact from disk.

        Args:
            filepath (str): Source file path.

        Returns:
            PerformanceRegressionModel: Restored model wrapper.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")

        payload = joblib.load(filepath)
        instance = cls(
            model_type=payload.get("model_type", "random_forest"),
            random_state=payload.get("random_state", 42),
            n_estimators=payload.get("n_estimators", 100)
        )
        instance.model = payload["model"]
        instance.is_fitted = True
        return instance
