# -*- coding: utf-8 -*-
"""
Anomaly Preprocessing Pipeline for Phase G.4.2
Handles feature selection, numeric scaling (StandardScaler), and column order consistency.
STRICT DATA LEAKAGE PREVENTION: Scaler is fit ONLY on Train partition.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler


class AnomalyPreprocessor:
    """Preprocesses ML features for anomaly detection without data leakage."""

    def __init__(self, feature_columns=None, excluded_columns=None):
        self.feature_columns = feature_columns
        self.excluded_columns = excluded_columns or [
            "event_id", "session_id", "car_id", "driver_id", "timestamp"
        ]
        self.scaler = StandardScaler()
        self.fitted_columns = []
        self.is_fitted = False

    def _select_numeric_features(self, df):
        """Filters DataFrame to numeric features only, excluding identifiers."""
        if self.feature_columns:
            cols = [c for c in self.feature_columns if c in df.columns and c not in self.excluded_columns]
        else:
            cols = [c for c in df.columns if c not in self.excluded_columns and pd.api.types.is_numeric_dtype(df[c])]

        # Remove constant or zero-variance columns if fitting
        if not self.is_fitted:
            cols = [c for c in cols if df[c].nunique(dropna=True) > 1]

        return cols

    def fit(self, df_train):
        """
        Fits StandardScaler strictly on Train partition.

        Args:
            df_train (pd.DataFrame): Training ML feature DataFrame.

        Returns:
            self
        """
        self.fitted_columns = self._select_numeric_features(df_train)
        if not self.fitted_columns:
            raise ValueError("No valid numeric feature columns found in Training dataset")

        X_train = df_train[self.fitted_columns].copy()
        X_train = X_train.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        self.scaler.fit(X_train)
        self.is_fitted = True
        return self

    def transform(self, df):
        """
        Transforms input DataFrame using fitted scaler.

        Args:
            df (pd.DataFrame): Input ML feature DataFrame.

        Returns:
            np.ndarray: Scaled feature matrix with exact column ordering.
        """
        if not self.is_fitted:
            raise RuntimeError("AnomalyPreprocessor must be fit on Train partition before calling transform")

        X = df[self.fitted_columns].copy()
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        return self.scaler.transform(X)

    def fit_transform(self, df_train):
        """Convenience method to fit on Train and return scaled Train matrix."""
        self.fit(df_train)
        return self.transform(df_train)
