"""
PhysioAI Lab — Regression Module
Implémente: linéaire, log, exponentielle, puissance, polynomiale, Ridge, Lasso
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import pearsonr
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.metrics import r2_score, mean_squared_error

from utils.data_utils import r_squared, rmse, mae


# ─── Fonctions de modèle ──────────────────────────────────────────────────────

def _linear(x, a, b):       return a * x + b
def _logarithmic(x, a, b):  return a * np.log(x) + b
def _exponential(x, a, b):  return a * np.exp(b * x)
def _power(x, a, b):        return a * np.power(np.abs(x), b)


# ─── Classe principale ────────────────────────────────────────────────────────

class RegressionEngine:
    """Moteur de régression multi-modèles."""

    MODELS = ["linear", "logarithmic", "exponential", "power", "polynomial", "ridge", "lasso"]

    def fit(self, x: np.ndarray, y: np.ndarray, model_type: str, **kwargs) -> dict:
        """Ajuste le modèle spécifié sur les données (x, y)."""
        dispatch = {
            "linear":       self._fit_linear,
            "logarithmic":  self._fit_logarithmic,
            "exponential":  self._fit_exponential,
            "power":        self._fit_power,
            "polynomial":   self._fit_polynomial,
            "ridge":        self._fit_ridge,
            "lasso":        self._fit_lasso,
        }
        if model_type not in dispatch:
            raise ValueError(f"Modèle inconnu: {model_type}. Choix: {self.MODELS}")
        return dispatch[model_type](x, y, **kwargs)

    # ── Courbes non-linéaires via curve_fit ─────────────────────────────────

    def _curve_fit_result(self, func, x, y, label: str, p0=None) -> dict:
        popt, pcov = curve_fit(func, x, y, p0=p0, maxfev=10000)
        y_pred = func(x, *popt)
        perr = np.sqrt(np.diag(pcov))
        return {
            "model": label,
            "parameters": {f"p{i}": float(v) for i, v in enumerate(popt)},
            "std_errors": {f"p{i}": float(v) for i, v in enumerate(perr)},
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "mae": mae(y, y_pred),
            "y_pred": y_pred.tolist(),
        }

    def _fit_linear(self, x, y, **kw) -> dict:
        return self._curve_fit_result(_linear, x, y, "linear", p0=[1, 0])

    def _fit_logarithmic(self, x, y, **kw) -> dict:
        if np.any(x <= 0):
            raise ValueError("x doit être > 0 pour la régression logarithmique.")
        return self._curve_fit_result(_logarithmic, x, y, "logarithmic", p0=[1, 0])

    def _fit_exponential(self, x, y, **kw) -> dict:
        return self._curve_fit_result(_exponential, x, y, "exponential", p0=[1, 0.01])

    def _fit_power(self, x, y, **kw) -> dict:
        if np.any(x <= 0):
            raise ValueError("x doit être > 0 pour la régression puissance.")
        return self._curve_fit_result(_power, x, y, "power", p0=[1, 1])

    # ── Modèles sklearn ─────────────────────────────────────────────────────

    def _fit_polynomial(self, x, y, degree: int = 3, **kw) -> dict:
        X = x.reshape(-1, 1)
        model = make_pipeline(PolynomialFeatures(degree), LinearRegression())
        model.fit(X, y)
        y_pred = model.predict(X)
        coefs = model.named_steps["linearregression"].coef_.tolist()
        intercept = float(model.named_steps["linearregression"].intercept_)
        return {
            "model": "polynomial",
            "degree": degree,
            "coefficients": coefs,
            "intercept": intercept,
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "mae": mae(y, y_pred),
            "y_pred": y_pred.tolist(),
        }

    def _fit_ridge(self, x, y, alpha: float = 1.0, degree: int = 3, **kw) -> dict:
        X = x.reshape(-1, 1)
        model = make_pipeline(PolynomialFeatures(degree), Ridge(alpha=alpha))
        model.fit(X, y)
        y_pred = model.predict(X)
        return {
            "model": "ridge",
            "alpha": alpha,
            "degree": degree,
            "coefficients": model.named_steps["ridge"].coef_.tolist(),
            "intercept": float(model.named_steps["ridge"].intercept_),
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "mae": mae(y, y_pred),
            "y_pred": y_pred.tolist(),
        }

    def _fit_lasso(self, x, y, alpha: float = 0.1, degree: int = 3, **kw) -> dict:
        X = x.reshape(-1, 1)
        model = make_pipeline(PolynomialFeatures(degree), Lasso(alpha=alpha, max_iter=10000))
        model.fit(X, y)
        y_pred = model.predict(X)
        return {
            "model": "lasso",
            "alpha": alpha,
            "degree": degree,
            "coefficients": model.named_steps["lasso"].coef_.tolist(),
            "intercept": float(model.named_steps["lasso"].intercept_),
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "mae": mae(y, y_pred),
            "y_pred": y_pred.tolist(),
        }

    def fit_all(self, x: np.ndarray, y: np.ndarray) -> list[dict]:
        """Essaie tous les modèles et retourne les résultats triés par R²."""
        results = []
        for model_type in ["linear", "polynomial", "ridge", "lasso"]:
            try:
                res = self.fit(x, y, model_type)
                results.append(res)
            except Exception as e:
                results.append({"model": model_type, "error": str(e)})
        for model_type in ["logarithmic", "exponential", "power"]:
            try:
                res = self.fit(x, y, model_type)
                results.append(res)
            except Exception as e:
                results.append({"model": model_type, "error": str(e)})
        valid = [r for r in results if "r2" in r]
        valid.sort(key=lambda r: r["r2"], reverse=True)
        return valid + [r for r in results if "r2" not in r]
