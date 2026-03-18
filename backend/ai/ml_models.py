"""
================================================================
ai/ml_models.py
Machine Learning avancé :
  - Random Forest Regressor / Classifier
  - Support Vector Regression (SVR)
  - Gradient Boosting
  - Clustering (K-Means, DBSCAN, Agglomeratif)
================================================================
"""

import logging
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import (
    mean_squared_error,
    r2_score,
    silhouette_score,
)
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

logger = logging.getLogger("physioai.ml")


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _prep(X_raw: list[list], y_raw: list | None = None):
    """Prépare X (et optionnellement y) pour sklearn."""
    X = np.asarray(X_raw, dtype=np.float64)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    scaler = StandardScaler()
    X_s    = scaler.fit_transform(X)
    y      = np.asarray(y_raw, dtype=np.float64).ravel() if y_raw is not None else None
    return X, X_s, y, scaler


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    r2   = float(r2_score(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae  = float(np.mean(np.abs(y_true - y_pred)))
    return {"r2": r2, "rmse": rmse, "mae": mae}


# ── Random Forest ─────────────────────────────────────────────────────────────

def random_forest_regression(
    X_data: list[list], y_data: list,
    n_estimators: int = 100,
    max_depth: int | None = None,
    cv_folds: int = 5,
) -> dict[str, Any]:
    """
    Random Forest Regressor avec validation croisée.
    Retourne les importances de variables et les scores OOB.
    """
    X, X_s, y, scaler = _prep(X_data, y_data)
    n = len(y)

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        oob_score=True,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_s, y)
    y_pred = model.predict(X_s)
    perf   = _metrics(y, y_pred)

    # Cross-validation
    k = min(cv_folds, n)
    cv_r2 = float(cross_val_score(model, X_s, y, cv=k, scoring="r2").mean())

    # Importance des features
    feat_imp = model.feature_importances_.tolist()

    logger.info(f"Random Forest : R²={perf['r2']:.4f}, OOB={model.oob_score_:.4f}, CV-R²={cv_r2:.4f}")

    return {
        "model":              "random_forest",
        "n_estimators":       n_estimators,
        "max_depth":          max_depth,
        "oob_score":          float(model.oob_score_),
        "cv_r2":              cv_r2,
        "feature_importance": feat_imp,
        "y_true":             y.tolist(),
        "y_pred":             y_pred.tolist(),
        "residuals":          (y - y_pred).tolist(),
        **perf,
    }


# ── SVR ───────────────────────────────────────────────────────────────────────

def svr_regression(
    X_data: list[list], y_data: list,
    kernel: str = "rbf",
    C: float = 1.0, epsilon: float = 0.1, gamma: str = "scale",
    cv_folds: int = 5,
) -> dict[str, Any]:
    """
    Support Vector Regression.
    Noyaux supportés : rbf, linear, poly, sigmoid.
    """
    X, X_s, y, scaler = _prep(X_data, y_data)
    n = len(y)

    model = SVR(kernel=kernel, C=C, epsilon=epsilon, gamma=gamma)
    model.fit(X_s, y)
    y_pred = model.predict(X_s)
    perf   = _metrics(y, y_pred)

    k     = min(cv_folds, n)
    cv_r2 = float(cross_val_score(model, X_s, y, cv=k, scoring="r2").mean())

    logger.info(f"SVR ({kernel}) : R²={perf['r2']:.4f}, CV-R²={cv_r2:.4f}")

    return {
        "model":      "svr",
        "kernel":     kernel,
        "C":          C,
        "epsilon":    epsilon,
        "cv_r2":      cv_r2,
        "n_sv":       int(model.n_support_.sum()),
        "y_true":     y.tolist(),
        "y_pred":     y_pred.tolist(),
        "residuals":  (y - y_pred).tolist(),
        **perf,
    }


# ── Gradient Boosting ─────────────────────────────────────────────────────────

def gradient_boosting(
    X_data: list[list], y_data: list,
    n_estimators: int = 100, learning_rate: float = 0.1,
    max_depth: int = 3, cv_folds: int = 5,
) -> dict[str, Any]:
    """Gradient Boosting Regressor (scikit-learn)."""
    X, X_s, y, _ = _prep(X_data, y_data)

    model = GradientBoostingRegressor(
        n_estimators=n_estimators, learning_rate=learning_rate,
        max_depth=max_depth, random_state=42,
    )
    model.fit(X_s, y)
    y_pred = model.predict(X_s)
    perf   = _metrics(y, y_pred)

    k     = min(cv_folds, len(y))
    cv_r2 = float(cross_val_score(model, X_s, y, cv=k, scoring="r2").mean())

    return {
        "model":              "gradient_boosting",
        "n_estimators":       n_estimators,
        "learning_rate":      learning_rate,
        "feature_importance": model.feature_importances_.tolist(),
        "cv_r2":              cv_r2,
        "y_true":             y.tolist(),
        "y_pred":             y_pred.tolist(),
        **perf,
    }


# ── Clustering ────────────────────────────────────────────────────────────────

def kmeans_clustering(
    X_data: list[list],
    k: int | None = None,
    max_k: int = 10,
) -> dict[str, Any]:
    """
    K-Means avec sélection automatique de k (méthode du coude + Silhouette).
    """
    X, X_s, _, _ = _prep(X_data)
    n = X_s.shape[0]

    # Sélection automatique de k
    if k is None:
        inertias    = []
        sil_scores  = []
        k_range     = range(2, min(max_k + 1, n))
        for ki in k_range:
            km = KMeans(n_clusters=ki, random_state=42, n_init=10)
            km.fit(X_s)
            inertias.append(float(km.inertia_))
            sil_scores.append(float(silhouette_score(X_s, km.labels_)))
        k = int(k_range[int(np.argmax(sil_scores))])
        elbow_data = {"k_range": list(k_range), "inertias": inertias, "silhouettes": sil_scores}
    else:
        elbow_data = None

    model  = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(X_s)
    sil    = float(silhouette_score(X_s, labels)) if k > 1 else 0.0

    return {
        "model":       "kmeans",
        "k":           k,
        "labels":      labels.tolist(),
        "centers":     model.cluster_centers_.tolist(),
        "inertia":     float(model.inertia_),
        "silhouette":  sil,
        "elbow_data":  elbow_data,
        "X":           X.tolist(),
    }


def dbscan_clustering(
    X_data: list[list],
    eps: float = 0.5, min_samples: int = 5,
) -> dict[str, Any]:
    """DBSCAN : détecte le nombre de clusters automatiquement + outliers."""
    X, X_s, _, _ = _prep(X_data)

    model  = DBSCAN(eps=eps, min_samples=min_samples)
    labels = model.fit_predict(X_s)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise    = int(np.sum(labels == -1))

    sil = float(silhouette_score(X_s, labels)) if n_clusters > 1 else 0.0

    return {
        "model":      "dbscan",
        "eps":        eps,
        "min_samples": min_samples,
        "n_clusters": n_clusters,
        "n_noise":    n_noise,
        "labels":     labels.tolist(),
        "silhouette": sil,
        "X":          X.tolist(),
    }
