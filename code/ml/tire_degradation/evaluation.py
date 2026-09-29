# -*- coding: utf-8 -*-
"""
Evaluation & Physical Validation Module for Phase G.4.4 Tire Degradation Modeling
Calculates per-wheel (FL, FR, RL, RR) and Global MAE/RMSE/R2 metrics and checks physical bounds.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def calculate_tire_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Computes per-wheel (FL, FR, RL, RR) and GLOBAL regression metrics.

    Args:
        y_true (np.ndarray): Ground truth array of shape (n, 4).
        y_pred (np.ndarray): Predicted deltas array of shape (n, 4).

    Returns:
        dict: Dict containing per-wheel and global MAE, RMSE, R2.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)

    wheels = ["FL", "FR", "RL", "RR"]

    if len(y_t) == 0:
        empty_m = {w: {"mae": 0.0, "rmse": 0.0, "r2": 0.0} for w in wheels}
        empty_m["GLOBAL"] = {"mae": 0.0, "rmse": 0.0, "r2": 0.0}
        return empty_m

    per_wheel = {}
    for i, w in enumerate(wheels):
        yt_w = y_t[:, i]
        yp_w = y_p[:, i]

        mae_w = float(mean_absolute_error(yt_w, yp_w))
        rmse_w = float(np.sqrt(mean_squared_error(yt_w, yp_w)))
        r2_w = float(r2_score(yt_w, yp_w)) if len(yt_w) > 1 and np.var(yt_w) > 1e-9 else 1.0

        per_wheel[w] = {
            "mae": round(mae_w, 4),
            "rmse": round(rmse_w, 4),
            "r2": round(r2_w, 4)
        }

    # Global multi-output average
    g_mae = float(np.mean([per_wheel[w]["mae"] for w in wheels]))
    g_rmse = float(np.mean([per_wheel[w]["rmse"] for w in wheels]))
    g_r2 = float(np.mean([per_wheel[w]["r2"] for w in wheels]))

    per_wheel["GLOBAL"] = {
        "mae": round(g_mae, 4),
        "rmse": round(g_rmse, 4),
        "r2": round(g_r2, 4)
    }

    return per_wheel


def validate_physical_bounds(df_predictions: pd.DataFrame) -> dict:
    """
    Performs physical sanity check on predicted wear deltas and predicted future wear %.

    Args:
        df_predictions (pd.DataFrame): Prediction output DataFrame.

    Returns:
        dict: Validation report detailing out-of-bounds counts and clipping summary.
    """
    if df_predictions is None or df_predictions.empty:
        return {"total_predictions": 0, "out_of_bounds_count": 0, "is_physically_valid": True}

    wheels = ["fl", "fr", "rl", "rr"]
    oob_count = 0

    for w in wheels:
        delta_col = f"predicted_delta_{w}"
        wear_col = f"predicted_wear_{w}"

        if delta_col in df_predictions.columns:
            neg_deltas = (df_predictions[delta_col] < 0.0).sum()
            oob_count += int(neg_deltas)

        if wear_col in df_predictions.columns:
            over_100 = (df_predictions[wear_col] > 100.0).sum()
            under_0 = (df_predictions[wear_col] < 0.0).sum()
            oob_count += int(over_100 + under_0)

    report = {
        "total_predictions": len(df_predictions),
        "out_of_bounds_count": oob_count,
        "is_physically_valid": bool(oob_count == 0),
        "physical_rules_applied": [
            "Future wear delta must be >= 0.0",
            "Predicted total tire wear % must be in [0.0, 100.0]"
        ]
    }

    return report


def evaluate_tire_degradation_models(models: dict, df_train: pd.DataFrame, df_val: pd.DataFrame, df_test: pd.DataFrame, preprocessor, feature_columns: list, target_columns: list) -> dict:
    """
    Evaluates models across Train, Validation, and Test sets per wheel and globally.
    Selects best model strictly based on Validation MAE Global.

    Args:
        models (dict): Dict mapping model_name -> model instance.
        df_train (pd.DataFrame): Training set.
        df_val (pd.DataFrame): Validation set.
        df_test (pd.DataFrame): Test set.
        preprocessor (TireDegradationPreprocessor): Fitted preprocessor.
        feature_columns (list): List of feature names.
        target_columns (list): List of target delta names.

    Returns:
        dict: Evaluation report containing comparison table DataFrame and best model name.
    """
    rows = []
    metrics_by_model = {}

    y_train = df_train[target_columns].values if not df_train.empty else np.zeros((0, 4))
    y_val = df_val[target_columns].values if not df_val.empty else np.zeros((0, 4))
    y_test = df_test[target_columns].values if not df_test.empty else np.zeros((0, 4))

    if preprocessor is not None and preprocessor.is_fitted:
        X_train_scaled = preprocessor.transform(df_train) if not df_train.empty else np.zeros((0, len(feature_columns)))
        X_val_scaled = preprocessor.transform(df_val) if not df_val.empty else np.zeros((0, len(feature_columns)))
        X_test_scaled = preprocessor.transform(df_test) if not df_test.empty else np.zeros((0, len(feature_columns)))
    else:
        X_train_scaled = df_train[feature_columns].values if not df_train.empty else np.zeros((0, len(feature_columns)))
        X_val_scaled = df_val[feature_columns].values if not df_val.empty else np.zeros((0, len(feature_columns)))
        X_test_scaled = df_test[feature_columns].values if not df_test.empty else np.zeros((0, len(feature_columns)))

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

            if hasattr(model, "predict"):
                if "Baseline" in name:
                    y_pred = model.predict(df_split)
                else:
                    y_pred = model.predict(X_scaled)
            else:
                y_pred = np.zeros((len(y_true), 4))

            m = calculate_tire_metrics(y_true, y_pred)
            metrics_by_model[name][split_name] = m

            for wheel in ["FL", "FR", "RL", "RR", "GLOBAL"]:
                rows.append({
                    "Model": name,
                    "Split": split_name,
                    "Wheel": wheel,
                    "MAE": m[wheel]["mae"],
                    "RMSE": m[wheel]["rmse"],
                    "R2": m[wheel]["r2"]
                })

            if split_name == "Validation":
                val_g_mae = m["GLOBAL"]["mae"]
                if val_g_mae < best_val_mae:
                    best_val_mae = val_g_mae
                    best_model_name = name

    df_comparison = pd.DataFrame(rows)

    return {
        "comparison_table": df_comparison,
        "best_model_name": best_model_name or list(models.keys())[0],
        "metrics_by_model": metrics_by_model
    }
