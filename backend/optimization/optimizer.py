"""
PhysioAI Lab — Optimization Module
Minimisation d'erreur, ajustement automatique de paramètres.
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import minimize, differential_evolution, curve_fit
from typing import Callable, Optional

from utils.data_utils import r_squared, rmse


class ParameterOptimizer:
    """Optimiseur générique pour calibration de modèles."""

    def optimize(
        self,
        model_func: Callable,
        x: np.ndarray,
        y: np.ndarray,
        param_names: list[str],
        bounds: Optional[list[tuple]] = None,
        method: str = "least_squares",
        p0: Optional[list] = None,
    ) -> dict:
        """
        Optimise les paramètres d'une fonction modèle.

        Args:
            model_func: callable(x, *params) → y_pred
            x, y: données expérimentales
            param_names: noms des paramètres
            bounds: [(min, max), ...] par paramètre
            method: 'least_squares' | 'nelder_mead' | 'differential_evolution'
            p0: valeurs initiales
        """
        if p0 is None:
            p0 = [1.0] * len(param_names)

        if method == "least_squares":
            return self._least_squares(model_func, x, y, param_names, bounds, p0)
        elif method == "nelder_mead":
            return self._nelder_mead(model_func, x, y, param_names, p0)
        elif method == "differential_evolution":
            return self._differential_evolution(model_func, x, y, param_names, bounds)
        else:
            raise ValueError(f"Méthode inconnue: {method}")

    def _least_squares(self, func, x, y, param_names, bounds, p0):
        """scipy.optimize.curve_fit — méthode Levenberg-Marquardt."""
        try:
            if bounds:
                lower = [b[0] for b in bounds]
                upper = [b[1] for b in bounds]
                popt, pcov = curve_fit(func, x, y, p0=p0, bounds=(lower, upper), maxfev=20000)
            else:
                popt, pcov = curve_fit(func, x, y, p0=p0, maxfev=20000)

            perr = np.sqrt(np.diag(pcov))
            y_pred = func(x, *popt)
            return {
                "method": "least_squares",
                "converged": True,
                "parameters": dict(zip(param_names, [float(v) for v in popt])),
                "std_errors": dict(zip(param_names, [float(v) for v in perr])),
                "r2": r_squared(y, y_pred),
                "rmse": rmse(y, y_pred),
                "y_pred": y_pred.tolist(),
            }
        except Exception as e:
            return {"method": "least_squares", "converged": False, "error": str(e)}

    def _nelder_mead(self, func, x, y, param_names, p0):
        """scipy.optimize.minimize avec méthode Nelder-Mead."""
        def objective(params):
            y_pred = func(x, *params)
            return float(np.sum((y - y_pred) ** 2))

        result = minimize(objective, p0, method="Nelder-Mead",
                          options={"maxiter": 10000, "xatol": 1e-8})
        y_pred = func(x, *result.x)
        return {
            "method": "nelder_mead",
            "converged": result.success,
            "parameters": dict(zip(param_names, [float(v) for v in result.x])),
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "objective_value": float(result.fun),
            "n_iterations": result.nit,
            "y_pred": y_pred.tolist(),
        }

    def _differential_evolution(self, func, x, y, param_names, bounds):
        """Algorithme évolutionnaire global — robuste aux optima locaux."""
        if not bounds:
            bounds = [(-100, 100)] * len(param_names)

        def objective(params):
            try:
                y_pred = func(x, *params)
                return float(np.sum((y - y_pred) ** 2))
            except Exception:
                return 1e12

        result = differential_evolution(
            objective, bounds, maxiter=1000, tol=1e-8, seed=42, polish=True
        )
        y_pred = func(x, *result.x)
        return {
            "method": "differential_evolution",
            "converged": result.success,
            "parameters": dict(zip(param_names, [float(v) for v in result.x])),
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "objective_value": float(result.fun),
            "n_iterations": int(result.nit),
            "y_pred": y_pred.tolist(),
        }
