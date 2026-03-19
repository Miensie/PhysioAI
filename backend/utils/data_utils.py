"""
PhysioAI Lab — Data Utilities
Helper functions for data validation, conversion and statistics
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Any


def to_numpy(data: Any) -> tuple[np.ndarray, np.ndarray]:
    """Convert dict/list payload to (x, y) numpy arrays."""
    if isinstance(data, dict):
        x = np.asarray(data.get("x", []), dtype=float)
        y = np.asarray(data.get("y", []), dtype=float)
    elif isinstance(data, (list, tuple)) and len(data) == 2:
        x, y = np.asarray(data[0], dtype=float), np.asarray(data[1], dtype=float)
    else:
        raise ValueError("Data must be {'x': [...], 'y': [...]} or [x_list, y_list]")
    if x.shape != y.shape:
        raise ValueError(f"x and y must have the same length (got {len(x)} vs {len(y)})")
    return x, y


def descriptive_stats(y: np.ndarray) -> dict:
    """Compute descriptive statistics for an array."""
    return {
        "count": int(len(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y, ddof=1)) if len(y) > 1 else 0.0,
        "min": float(np.min(y)),
        "q25": float(np.percentile(y, 25)),
        "median": float(np.median(y)),
        "q75": float(np.percentile(y, 75)),
        "max": float(np.max(y)),
        "skewness": float(pd.Series(y).skew()),
        "kurtosis": float(pd.Series(y).kurtosis()),
    }


def r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Coefficient of determination R²."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))
