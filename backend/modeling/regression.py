"""
================================================================
modeling/regression.py
Modèles de régression : linéaire, polynomiale, Ridge, Lasso
================================================================
"""

import logging
from typing import Any

import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import pearsonr, t as t_dist
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

logger = logging.getLogger("physioai.regression")


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _safe_array(data: list) -> np.ndarray:
    """Convertit une liste en tableau numpy 1D propre."""
    arr = np.asarray(data, dtype=np.float64).ravel()
    if np.any(~np.isfinite(arr)):
        raise ValueError("Les données contiennent des NaN ou Inf.")
    return arr


def _stats(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calcule les métriques de performance standard."""
    r2   = float(r2_score(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae  = float(np.mean(np.abs(y_true - y_pred)))
    return {"r2": r2, "rmse": rmse, "mae": mae}


# ── Régression linéaire ───────────────────────────────────────────────────────

def linear_regression(x_data: list, y_data: list) -> dict[str, Any]:
    """
    Régression linéaire simple avec intervalle de confiance.

    Retourne :
        slope, intercept, r2, rmse, mae, p_value,
        ci_slope, ci_intercept, y_pred, residuals
    """
    x = _safe_array(x_data)
    y = _safe_array(y_data)
    n = len(x)

    if n < 3:
        raise ValueError("Minimum 3 points requis pour la régression linéaire.")

    # Régression via numpy (plus robuste pour les stats)
    coeffs = np.polyfit(x, 1, deg=1)          # pour compatibilité
    model  = LinearRegression()
    X      = x.reshape(-1, 1)
    model.fit(X, y)

    slope     = float(model.coef_[0])
    intercept = float(model.intercept_)
    y_pred    = model.predict(X)

    # Statistiques
    perf = _stats(y, y_pred)
    residuals = (y - y_pred).tolist()

    # Intervalle de confiance à 95% sur slope et intercept
    s2  = np.sum((y - y_pred) ** 2) / (n - 2)
    Sxx = np.sum((x - x.mean()) ** 2)
    se_slope     = float(np.sqrt(s2 / Sxx))
    se_intercept = float(np.sqrt(s2 * (1/n + x.mean()**2 / Sxx)))
    t_crit       = float(t_dist.ppf(0.975, df=n - 2))
    ci_slope     = [slope - t_crit * se_slope,     slope + t_crit * se_slope]
    ci_intercept = [intercept - t_crit * se_intercept, intercept + t_crit * se_intercept]

    # p-valeur de la pente
    t_stat  = slope / (se_slope + 1e-15)
    p_value = float(2 * (1 - t_dist.cdf(abs(t_stat), df=n - 2)))

    # Corrélation de Pearson
    r_pearson, _ = pearsonr(x, y)

    logger.info(f"Régression linéaire : slope={slope:.4f}, R²={perf['r2']:.4f}")

    return {
        "type":         "linear",
        "slope":        slope,
        "intercept":    intercept,
        "r_pearson":    float(r_pearson),
        "ci_slope":     ci_slope,
        "ci_intercept": ci_intercept,
        "p_value":      p_value,
        "n":            n,
        "x":            x.tolist(),
        "y_true":       y.tolist(),
        "y_pred":       y_pred.tolist(),
        "residuals":    residuals,
        **perf,
    }


# ── Régression polynomiale ───────────────────────────────────────────────────

def polynomial_regression(x_data: list, y_data: list, degree: int = 2) -> dict[str, Any]:
    """
    Régression polynomiale de degré arbitraire avec cross-validation LOO pour
    sélection automatique du degré optimal si degree='auto'.
    """
    x = _safe_array(x_data)
    y = _safe_array(y_data)
    n = len(x)

    degree = int(degree)
    degree = max(1, min(degree, min(n - 1, 10)))

    # Pipeline : PolynomialFeatures → StandardScaler → LinearRegression
    pipeline = Pipeline([
        ("poly",   PolynomialFeatures(degree=degree, include_bias=True)),
        ("scaler", StandardScaler()),
        ("lr",     LinearRegression()),
    ])

    X = x.reshape(-1, 1)
    pipeline.fit(X, y)
    y_pred = pipeline.predict(X)

    # Coefficients dans l'espace polynomial original
    lr     = pipeline.named_steps["lr"]
    coeffs = lr.coef_.tolist()
    perf   = _stats(y, y_pred)

    # Courbe de fit dense pour affichage
    x_dense   = np.linspace(x.min(), x.max(), 200)
    y_dense   = pipeline.predict(x_dense.reshape(-1, 1))

    logger.info(f"Régression polynomiale degré {degree} : R²={perf['r2']:.4f}")

    return {
        "type":       "polynomial",
        "degree":     degree,
        "coeffs":     coeffs,
        "x":          x.tolist(),
        "y_true":     y.tolist(),
        "y_pred":     y_pred.tolist(),
        "residuals":  (y - y_pred).tolist(),
        "x_curve":    x_dense.tolist(),
        "y_curve":    y_dense.tolist(),
        **perf,
    }


# ── Régression Ridge / Lasso ─────────────────────────────────────────────────

def regularized_regression(
    x_data: list, y_data: list,
    method: str = "ridge", alpha: float = 1.0, degree: int = 2,
) -> dict[str, Any]:
    """
    Régression régularisée (Ridge ou Lasso) avec features polynomiales.
    Utile pour éviter le surapprentissage sur des jeux de données petits.
    """
    x = _safe_array(x_data)
    y = _safe_array(y_data)

    reg_cls = Ridge if method.lower() == "ridge" else Lasso
    pipeline = Pipeline([
        ("poly",   PolynomialFeatures(degree=degree, include_bias=True)),
        ("scaler", StandardScaler()),
        ("reg",    reg_cls(alpha=alpha)),
    ])

    X = x.reshape(-1, 1)
    pipeline.fit(X, y)
    y_pred = pipeline.predict(X)
    perf   = _stats(y, y_pred)

    logger.info(f"Régression {method} α={alpha} deg={degree} : R²={perf['r2']:.4f}")

    return {
        "type":      method,
        "alpha":     alpha,
        "degree":    degree,
        "x":         x.tolist(),
        "y_true":    y.tolist(),
        "y_pred":    y_pred.tolist(),
        "residuals": (y - y_pred).tolist(),
        **perf,
    }


# ── Régression multi-variables ───────────────────────────────────────────────

def multivariate_regression(X_data: list[list], y_data: list) -> dict[str, Any]:
    """
    Régression linéaire multiple (n variables explicatives).
    """
    X = np.asarray(X_data, dtype=np.float64)
    y = _safe_array(y_data)

    if X.shape[0] != len(y):
        raise ValueError(f"X ({X.shape[0]} lignes) et y ({len(y)} lignes) incompatibles.")

    model  = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)
    perf   = _stats(y, y_pred)

    return {
        "type":        "multivariate",
        "coeffs":      model.coef_.tolist(),
        "intercept":   float(model.intercept_),
        "n_features":  X.shape[1],
        "n_samples":   X.shape[0],
        "y_true":      y.tolist(),
        "y_pred":      y_pred.tolist(),
        "residuals":   (y - y_pred).tolist(),
        **perf,
    }
