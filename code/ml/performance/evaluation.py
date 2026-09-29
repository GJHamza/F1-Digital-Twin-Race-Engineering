# -*- coding: utf-8 -*-
"""
Evaluation & Model Comparison Module for Phase G.4.3
Computes MAE, RMSE, R2, and MAPE metrics across Train, Validation, and Test partitions.
Selects best model strictly based on Validation performance.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def calculate_metrics(y_true, y_pred) -> dict:
    """
    Computes MAE, RMSE, R2, and MAPE metrics for regression targets.

    Args:
        y_true (array-like): Ground truth lap times.
        y_pred (array-like): Predicted lap times.

    Returns:
        dict: Dict containing mae, rmse, r2, and mape metrics rounded to 4 decimals.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)

    if len(y_t) == 0:
        return {"mae": 0.0, "rmse": 0.0, "r2": 0.0, "mape": 0.0}

    mae = float(mean_absolute_error(y_t, y_p))
    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    r2 = float(r2_score(y_t, y_p)) if len(y_t) > 1 and np.var(y_t) > 1e-9 else 1.0

    # Avoid division by zero in MAPE
    mask = (y_t != 0.0)
    if np.any(mask):
        mape = float(np.mean(np.abs((y_t[mask] - y_p[mask]) / y_t[mask])) * 100.0)
    else:
        mape = 0.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "mape": round(mape, 4)
    }


def evaluate_regression_models(models: dict, df_train: pd.DataFrame, df_val: pd.DataFrame, df_test: pd.DataFrame, preprocessor, feature_columns: list, target_column: str = "lap_time_sec") -> dict:
    """
    Evaluates a set of regression models across Train, Validation, and Test partitions.

    Args:
        models (dict): Dictionary mapping model_name -> fitted model instance.
        df_train (pd.DataFrame): Training set.
        df_val (pd.DataFrame): Validation set.
        df_test (pd.DataFrame): Test set.
        preprocessor (PerformancePreprocessor): Fitted preprocessor for ML models.
        feature_columns (list): List of feature column names.
        target_column (str): Target column name.

    Returns:
        dict: Summary containing comparison DataFrame, best model name, and detailed metrics.
    """
    rows = []
    metrics_by_model = {}

    # Extract target series
    y_train = df_train[target_column].values if not df_train.empty else np.array([])
    y_val = df_val[target_column].values if not df_val.empty else np.array([])
    y_test = df_test[target_column].values if not df_test.empty else np.array([])

    # Transform features for ML models
    if preprocessor is not None and preprocessor.is_fitted:
        X_train_scaled = preprocessor.transform(df_train) if not df_train.empty else np.array([])
        X_val_scaled = preprocessor.transform(df_val) if not df_val.empty else np.array([])
        X_test_scaled = preprocessor.transform(df_test) if not df_test.empty else np.array([])
    else:
        X_train_scaled = df_train[feature_columns].values if not df_train.empty else np.array([])
        X_val_scaled = df_val[feature_columns].values if not df_val.empty else np.array([])
        X_test_scaled = df_test[feature_columns].values if not df_test.empty else np.array([])

    best_val_mae = float("inf")
    best_model_name = None

    for name, model in models.items():
        metrics_by_model[name] = {}

        for split_name, df_split, y_true, X_scaled in [
            ("Train", df_train, y_train, X_train_scaled),
            ("Validation", df_val, y_val, X_val_scaled),
            ("Test", df_test, y_test, X_test_scaled)
        ]:
            if len(df_split) == 0:
                continue

            # Predict based on model signature (baseline models vs ML models)
            if hasattr(model, "predict"):
                if "Baseline" in name:
                    y_pred = model.predict(df_split)
                else:
                    y_pred = model.predict(X_scaled)
            else:
                y_pred = np.full(len(y_true), np.mean(y_train) if len(y_train) > 0 else 60.0)

            m = calculate_metrics(y_true, y_pred)
            metrics_by_model[name][split_name] = m

            rows.append({
                "Model": name,
                "Split": split_name,
                "MAE": m["mae"],
                "RMSE": m["rmse"],
                "R2": m["r2"],
                "MAPE": m["mape"]
            })

            # Check best model strictly based on Validation MAE
            if split_name == "Validation":
                if m["mae"] < best_val_mae:
                    best_val_mae = m["mae"]
                    best_model_name = name

    df_comparison = pd.DataFrame(rows)

    return {
        "comparison_table": df_comparison,
        "best_model_name": best_model_name or list(models.keys())[0],
        "metrics_by_model": metrics_by_model
    }
