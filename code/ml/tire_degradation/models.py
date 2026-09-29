# -*- coding: utf-8 -*-
"""
Multi-Output ML Regression Models Module for Phase G.4.4 Tire Degradation Modeling
Wraps Scikit-Learn RandomForestRegressor and MultiOutputRegressor(GradientBoostingRegressor).
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from ml.tire_degradation.config import TireDegradationConfig


class TireDegradationModel:
    """Multi-Output ML Regression wrapper for 4 wheel tire degradation prediction."""

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
            self.model = MultiOutputRegressor(
                GradientBoostingRegressor(
                    n_estimators=n_estimators,
                    random_state=random_state,
                    **kwargs
                )
            )
        else:
            raise ValueError(f"Unsupported model_type: '{model_type}'. Choose 'random_forest' or 'gradient_boosting'.")

    def fit(self, X_train, y_train):
        """
        Trains multi-output regressor model on training features and 4-wheel target deltas.

        Args:
            X_train (np.ndarray or pd.DataFrame): Scaled training features.
            y_train (np.ndarray or pd.DataFrame): Target deltas array of shape (n, 4).
        """
        X_arr = np.asarray(X_train, dtype=float)
        y_arr = np.asarray(y_train, dtype=float)

        if len(X_arr) == 0:
            raise ValueError("Cannot fit model on empty training data.")

        self.model.fit(X_arr, y_arr)
        self.is_fitted = True

    def predict(self, X) -> np.ndarray:
        """
        Predicts future wear deltas for all 4 wheels.

        Args:
            X (np.ndarray or pd.DataFrame): Feature matrix.

        Returns:
            np.ndarray: Array of shape (n_samples, 4) with predicted deltas.
        """
        if not self.is_fitted:
            raise RuntimeError(f"{self.model_name} must be fitted before predict().")

        X_arr = np.asarray(X, dtype=float)
        return self.model.predict(X_arr)

    def get_feature_importances(self, feature_names=None) -> pd.DataFrame:
        """
        Extracts and aggregates feature importances across the 4 output models.

        Args:
            feature_names (list, optional): Feature column names matching X.

        Returns:
            pd.DataFrame: Aggregated feature importances sorted descending.
        """
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before extracting feature importances.")

        n_features = len(feature_names or [])

        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        elif hasattr(self.model, "estimators_"):
            # MultiOutputRegressor: average importances across single-output estimators
            all_imps = [est.feature_importances_ for est in self.model.estimators_ if hasattr(est, "feature_importances_")]
            importances = np.mean(all_imps, axis=0) if all_imps else np.zeros(n_features)
        else:
            importances = np.zeros(n_features)

        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(len(importances))]

        df_imp = pd.DataFrame({
            "feature": feature_names,
            "importance": importances
        }).sort_values(by="importance", ascending=False).reset_index(drop=True)

        return df_imp

    def save(self, filepath: str, metadata: dict = None):
        """Persists model artifact to disk."""
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
        """Restores model artifact from disk."""
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
