"""
modeling/regression.py
=======================
Fonctions standalone de régression — importées directement par routes_regression.py
via `from modeling import regression as reg`.
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import curve_fit
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.metrics import r2_score, mean_squared_error
from loguru import logger
from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
    r2   = float(r2_score(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae  = float(np.mean(np.abs(y_true - y_pred)))
    return {"r2": round(r2,6), "rmse": round(rmse,6), "mae": round(mae,6)}

def _curve(xa: np.ndarray, n: int = 200) -> np.ndarray:
    return np.linspace(xa.min(), xa.max(), n)


# ─────────────────────────────────────────────────────────────────────────────
# Régression linéaire
# ─────────────────────────────────────────────────────────────────────────────

def linear_regression(x: List[float], y: List[float]) -> Dict[str, Any]:
    logger.debug("linear_regression")
    xa, ya = np.array(x).reshape(-1,1), np.array(y)
    m  = LinearRegression().fit(xa, ya)
    xi = _curve(xa.flatten()).reshape(-1,1)
    return {
        "model":    "linear",
        "equation": f"y = {m.coef_[0]:.6f}·x + {m.intercept_:.6f}",
        "params":   {"slope": float(m.coef_[0]), "intercept": float(m.intercept_)},
        "metrics":  _metrics(ya, m.predict(xa)),
        "x_fit":    xi.flatten().tolist(),
        "y_fit":    m.predict(xi).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Régression logarithmique
# ─────────────────────────────────────────────────────────────────────────────

def logarithmic_regression(x: List[float], y: List[float]) -> Dict[str, Any]:
    logger.debug("logarithmic_regression")
    xa, ya = np.array(x), np.array(y)
    def fn(x, a, b): return a * np.log(np.abs(x) + 1e-9) + b
    popt, _ = curve_fit(fn, xa, ya, maxfev=10000)
    xi = _curve(xa)
    return {
        "model":    "logarithmic",
        "equation": f"y = {popt[0]:.6f}·ln(x) + {popt[1]:.6f}",
        "params":   {"a": float(popt[0]), "b": float(popt[1])},
        "metrics":  _metrics(ya, fn(xa, *popt)),
        "x_fit":    xi.tolist(),
        "y_fit":    fn(xi, *popt).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Régression exponentielle
# ─────────────────────────────────────────────────────────────────────────────

def exponential_regression(x: List[float], y: List[float]) -> Dict[str, Any]:
    logger.debug("exponential_regression")
    xa, ya = np.array(x), np.array(y)
    def fn(x, a, b, c): return a * np.exp(b * x) + c
    popt, _ = curve_fit(fn, xa, ya, p0=[1., 0.1, 0.], maxfev=50000)
    xi = _curve(xa)
    return {
        "model":    "exponential",
        "equation": f"y = {popt[0]:.6f}·exp({popt[1]:.6f}·x) + {popt[2]:.6f}",
        "params":   {"a": float(popt[0]), "b": float(popt[1]), "c": float(popt[2])},
        "metrics":  _metrics(ya, fn(xa, *popt)),
        "x_fit":    xi.tolist(),
        "y_fit":    fn(xi, *popt).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Régression puissance
# ─────────────────────────────────────────────────────────────────────────────

def power_regression(x: List[float], y: List[float]) -> Dict[str, Any]:
    logger.debug("power_regression")
    xa, ya = np.array(x), np.array(y)
    def fn(x, a, b): return a * np.power(np.abs(x) + 1e-9, b)
    popt, _ = curve_fit(fn, xa, ya, p0=[1., 1.], maxfev=10000)
    xi = _curve(xa)
    return {
        "model":    "power",
        "equation": f"y = {popt[0]:.6f}·x^{popt[1]:.6f}",
        "params":   {"a": float(popt[0]), "b": float(popt[1])},
        "metrics":  _metrics(ya, fn(xa, *popt)),
        "x_fit":    xi.tolist(),
        "y_fit":    fn(xi, *popt).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Régression polynomiale
# ─────────────────────────────────────────────────────────────────────────────

def polynomial_regression(x: List[float], y: List[float],
                           degree: int = 3) -> Dict[str, Any]:
    logger.debug(f"polynomial_regression deg={degree}")
    xa, ya = np.array(x).reshape(-1,1), np.array(y)
    pipe = Pipeline([
        ("poly", PolynomialFeatures(degree, include_bias=False)),
        ("lin",  LinearRegression()),
    ])
    pipe.fit(xa, ya)
    xi = _curve(xa.flatten()).reshape(-1,1)
    return {
        "model":    f"polynomial_deg{degree}",
        "equation": f"Polynôme degré {degree}",
        "params":   {"coefs": pipe["lin"].coef_.tolist(),
                     "intercept": float(pipe["lin"].intercept_)},
        "metrics":  _metrics(ya, pipe.predict(xa)),
        "x_fit":    xi.flatten().tolist(),
        "y_fit":    pipe.predict(xi).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ridge
# ─────────────────────────────────────────────────────────────────────────────

def ridge_regression(x: List[float], y: List[float],
                     alpha: float = 1.0) -> Dict[str, Any]:
    logger.debug(f"ridge alpha={alpha}")
    xa, ya = np.array(x).reshape(-1,1), np.array(y)
    m  = Ridge(alpha=alpha).fit(xa, ya)
    xi = _curve(xa.flatten()).reshape(-1,1)
    return {
        "model":    "ridge",
        "equation": f"y = {m.coef_[0]:.6f}·x + {m.intercept_:.6f} (α={alpha})",
        "params":   {"slope": float(m.coef_[0]), "intercept": float(m.intercept_), "alpha": alpha},
        "metrics":  _metrics(ya, m.predict(xa)),
        "x_fit":    xi.flatten().tolist(),
        "y_fit":    m.predict(xi).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Lasso
# ─────────────────────────────────────────────────────────────────────────────

def lasso_regression(x: List[float], y: List[float],
                     alpha: float = 0.1) -> Dict[str, Any]:
    logger.debug(f"lasso alpha={alpha}")
    xa, ya = np.array(x).reshape(-1,1), np.array(y)
    m  = Lasso(alpha=alpha, max_iter=10000).fit(xa, ya)
    xi = _curve(xa.flatten()).reshape(-1,1)
    return {
        "model":    "lasso",
        "equation": f"y = {m.coef_[0]:.6f}·x + {m.intercept_:.6f} (α={alpha})",
        "params":   {"slope": float(m.coef_[0]), "intercept": float(m.intercept_), "alpha": alpha},
        "metrics":  _metrics(ya, m.predict(xa)),
        "x_fit":    xi.flatten().tolist(),
        "y_fit":    m.predict(xi).tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Meilleur modèle automatique
# ─────────────────────────────────────────────────────────────────────────────

def best_regression(x: List[float], y: List[float]) -> Dict[str, Any]:
    """Lance tous les modèles et retourne le meilleur par R²."""
    runners = {
        "linear":      lambda: linear_regression(x, y),
        "logarithmic": lambda: logarithmic_regression(x, y),
        "exponential": lambda: exponential_regression(x, y),
        "power":       lambda: power_regression(x, y),
        "polynomial3": lambda: polynomial_regression(x, y, 3),
        "ridge":       lambda: ridge_regression(x, y),
        "lasso":       lambda: lasso_regression(x, y),
    }
    results = {}
    for name, fn in runners.items():
        try:
            results[name] = fn()
        except Exception as e:
            logger.warning(f"Modèle {name} échoué: {e}")

    best = max(results, key=lambda k: results[k]["metrics"]["r2"])
    return {"best_model": best, "all_models": results}