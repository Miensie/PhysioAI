"""
ai/ml_models.py
================
Expose les fonctions standalone attendues par routes_ai.py :
  random_forest_regression, svr_regression, gradient_boosting, kmeans_clustering
"""

from __future__ import annotations
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score, mean_squared_error, silhouette_score
from loguru import logger
from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Helper interne
# ─────────────────────────────────────────────────────────────────────────────

def _split_and_pipe(model, X: np.ndarray, y: np.ndarray, test_size=0.2):
    """Split, construit un Pipeline StandardScaler+model, entraîne, évalue."""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, random_state=42
    )
    pipe = Pipeline([("scaler", StandardScaler()), ("model", model)])
    pipe.fit(X_tr, y_tr)
    y_pred_te = pipe.predict(X_te)
    y_pred_tr = pipe.predict(X_tr)
    return pipe, X_tr, X_te, y_tr, y_te, y_pred_tr, y_pred_te


# ─────────────────────────────────────────────────────────────────────────────
# RANDOM FOREST
# ─────────────────────────────────────────────────────────────────────────────

def random_forest_regression(
    X: List[List[float]],
    y: List[float],
    n_estimators: int = 100,
) -> Dict[str, Any]:
    logger.info(f"random_forest_regression  n_estimators={n_estimators}")
    Xa = np.array(X, dtype=float)
    ya = np.array(y, dtype=float)

    pipe, X_tr, X_te, y_tr, y_te, y_pred_tr, y_pred_te = _split_and_pipe(
        RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1),
        Xa, ya,
    )
    cv = cross_val_score(pipe, Xa, ya, cv=min(5, len(Xa) // 2), scoring="r2")

    return {
        "model":               "random_forest",
        "train_r2":            round(float(r2_score(y_tr, y_pred_tr)), 6),
        "test_r2":             round(float(r2_score(y_te, y_pred_te)), 6),
        "test_rmse":           round(float(np.sqrt(mean_squared_error(y_te, y_pred_te))), 6),
        "cv_r2_mean":          round(float(cv.mean()), 6),
        "cv_r2_std":           round(float(cv.std()), 6),
        "feature_importances": pipe["model"].feature_importances_.tolist(),
        "predictions":         y_pred_te.tolist(),
        "y_test":              y_te.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SVR
# ─────────────────────────────────────────────────────────────────────────────

def svr_regression(
    X: List[List[float]],
    y: List[float],
    kernel: str = "rbf",
    C: float = 1.0,
    epsilon: float = 0.1,
) -> Dict[str, Any]:
    logger.info(f"svr_regression  kernel={kernel}")
    Xa = np.array(X, dtype=float)
    ya = np.array(y, dtype=float)

    pipe, X_tr, X_te, y_tr, y_te, y_pred_tr, y_pred_te = _split_and_pipe(
        SVR(kernel=kernel, C=C, epsilon=epsilon),
        Xa, ya,
    )
    return {
        "model":       "svr",
        "kernel":      kernel,
        "train_r2":    round(float(r2_score(y_tr, y_pred_tr)), 6),
        "test_r2":     round(float(r2_score(y_te, y_pred_te)), 6),
        "test_rmse":   round(float(np.sqrt(mean_squared_error(y_te, y_pred_te))), 6),
        "predictions": y_pred_te.tolist(),
        "y_test":      y_te.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GRADIENT BOOSTING
# ─────────────────────────────────────────────────────────────────────────────

def gradient_boosting(
    X: List[List[float]],
    y: List[float],
    n_estimators: int = 100,
) -> Dict[str, Any]:
    logger.info(f"gradient_boosting  n_estimators={n_estimators}")
    Xa = np.array(X, dtype=float)
    ya = np.array(y, dtype=float)

    pipe, X_tr, X_te, y_tr, y_te, y_pred_tr, y_pred_te = _split_and_pipe(
        GradientBoostingRegressor(n_estimators=n_estimators, random_state=42),
        Xa, ya,
    )
    return {
        "model":       "gradient_boosting",
        "train_r2":    round(float(r2_score(y_tr, y_pred_tr)), 6),
        "test_r2":     round(float(r2_score(y_te, y_pred_te)), 6),
        "test_rmse":   round(float(np.sqrt(mean_squared_error(y_te, y_pred_te))), 6),
        "predictions": y_pred_te.tolist(),
        "y_test":      y_te.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# K-MEANS CLUSTERING
# ─────────────────────────────────────────────────────────────────────────────

def kmeans_clustering(
    X: List[List[float]],
    n_clusters: int = 3,
) -> Dict[str, Any]:
    logger.info(f"kmeans_clustering  k={n_clusters}")
    Xa = StandardScaler().fit_transform(np.array(X, dtype=float))
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(Xa)
    sil = float(silhouette_score(Xa, labels)) if n_clusters > 1 else 0.0

    # Elbow curve
    ks = range(1, min(9, len(Xa)))
    inertias = [
        KMeans(n_clusters=k, random_state=42, n_init=5).fit(Xa).inertia_
        for k in ks
    ]
    return {
        "model":       "kmeans",
        "n_clusters":  n_clusters,
        "labels":      labels.tolist(),
        "silhouette":  round(sil, 6),
        "centers":     km.cluster_centers_.tolist(),
        "inertia":     round(float(km.inertia_), 6),
        "elbow":       {"k": list(ks), "inertia": inertias},
    }
