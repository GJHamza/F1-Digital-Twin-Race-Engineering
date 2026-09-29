# -*- coding: utf-8 -*-
"""
Anomaly Explainability Engine for Phase G.4.2
Identifies top contributing signals per anomaly based on feature Z-score deviations relative to Train baseline.
IMPORTANT: Signals indicate statistical deviations, not causal attribution.
"""

import json
import numpy as np
import pandas as pd


class AnomalyExplainer:
    """Computes top contributing signal deviations for anomalies."""

    def __init__(self, feature_names, train_means, train_stds):
        self.feature_names = feature_names
        self.means = np.asarray(train_means)
        self.stds = np.asarray(train_stds)
        self.stds[self.stds == 0.0] = 1e-5

    def explain_sample(self, scaled_sample_row, top_k=3):
        """
        Identifies top K feature names with highest absolute Z-score deviation.

        Args:
            scaled_sample_row (np.ndarray or list): Single sample feature vector.
            top_k (int): Number of top contributing signals to return.

        Returns:
            list: List of top K feature name strings.
        """
        arr = np.asarray(scaled_sample_row)
        z_scores = np.abs((arr - self.means) / self.stds)
        top_indices = np.argsort(z_scores)[::-1][:top_k]
        return [self.feature_names[i] for i in top_indices if i < len(self.feature_names)]

    def explain_dataframe(self, X_scaled, top_k=3):
        """
        Computes top K contributing signals for each row in feature matrix.

        Args:
            X_scaled (np.ndarray or pd.DataFrame): Feature matrix.
            top_k (int): Number of top signals per row.

        Returns:
            list: List of JSON string representation of top signal lists.
        """
        matrix = X_scaled.values if isinstance(X_scaled, pd.DataFrame) else np.asarray(X_scaled)
        n_samples = len(matrix)
        explanations_json = []

        for i in range(n_samples):
            top_feats = self.explain_sample(matrix[i], top_k=top_k)
            explanations_json.append(json.dumps(top_feats))

        return explanations_json
