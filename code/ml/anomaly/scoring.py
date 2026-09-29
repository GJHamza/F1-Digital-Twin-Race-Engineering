# -*- coding: utf-8 -*-
"""
Anomaly Scoring & Severity Calibration Module for Phase G.4.2
Normalizes raw isolation scores to [0, 1] and maps severity levels (NORMAL, LOW, MEDIUM, HIGH)
calibrated on Validation set quantiles.
"""

import numpy as np


class AnomalyScoreCalibrator:
    """Calibrates normalized anomaly scores and severity thresholds."""

    def __init__(self, quantiles=None):
        self.quantiles = quantiles or {"LOW": 0.90, "MEDIUM": 0.95, "HIGH": 0.99}
        self.score_min = None
        self.score_max = None
        self.threshold_low = None
        self.threshold_medium = None
        self.threshold_high = None
        self.is_calibrated = False

    def calibrate(self, raw_scores_val):
        """
        Calibrates min/max normalization bounds and quantile severity thresholds
        STRICTLY on Validation dataset raw scores.

        Args:
            raw_scores_val (np.ndarray): Raw decision function scores from Validation set.

        Returns:
            self
        """
        # In sklearn IsolationForest, smaller/negative decision_function values = more anomalous.
        # We invert raw scores so higher value = more anomalous.
        inverted_val = -raw_scores_val

        self.score_min = float(np.min(inverted_val))
        self.score_max = float(np.max(inverted_val))

        norm_scores_val = self._normalize_array(inverted_val)

        self.threshold_low = float(np.quantile(norm_scores_val, self.quantiles["LOW"]))
        self.threshold_medium = float(np.quantile(norm_scores_val, self.quantiles["MEDIUM"]))
        self.threshold_high = float(np.quantile(norm_scores_val, self.quantiles["HIGH"]))

        self.is_calibrated = True
        return self

    def _normalize_array(self, inverted_scores):
        """Maps inverted decision scores to [0.0, 1.0] range."""
        if self.score_max == self.score_min:
            return np.zeros_like(inverted_scores)
        norm = (inverted_scores - self.score_min) / (self.score_max - self.score_min)
        return np.clip(norm, 0.0, 1.0)

    def score(self, raw_scores):
        """
        Computes normalized anomaly score in [0.0, 1.0].

        Args:
            raw_scores (np.ndarray): Raw decision function scores.

        Returns:
            np.ndarray: Normalized anomaly scores in [0.0, 1.0].
        """
        if not self.is_calibrated:
            raise RuntimeError("AnomalyScoreCalibrator must be calibrated on Validation set before scoring")

        inverted = -raw_scores
        return self._normalize_array(inverted)

    def map_severity(self, norm_scores):
        """
        Maps normalized anomaly scores to operational severity levels:
        NORMAL (< threshold_low)
        LOW (>= threshold_low and < threshold_medium)
        MEDIUM (>= threshold_medium and < threshold_high)
        HIGH (>= threshold_high)

        Args:
            norm_scores (np.ndarray): Normalized anomaly scores.

        Returns:
            np.ndarray: Array of severity strings ("NORMAL", "LOW", "MEDIUM", "HIGH").
        """
        if not self.is_calibrated:
            raise RuntimeError("AnomalyScoreCalibrator must be calibrated before mapping severity")

        severities = np.full(len(norm_scores), "NORMAL", dtype=object)
        severities[norm_scores >= self.threshold_low] = "LOW"
        severities[norm_scores >= self.threshold_medium] = "MEDIUM"
        severities[norm_scores >= self.threshold_high] = "HIGH"

        return severities
