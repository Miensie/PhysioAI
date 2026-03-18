"""
================================================================
optimization/optimizer.py
Optimisation et calibration automatique de paramètres :
  - Minimisation d'erreur (Nelder-Mead, L-BFGS-B, Differential Evolution)
  - Calibration curve_fit
  - Optimisation multi-objectif
  - Analyse de sensibilité
================================================================
"""

import logging
from typing import Any, Callable

import numpy as np
from scipy.optimize import curve_fit, differential_evolution, minimize

logger = logging.getLogger("physioai.optimizer")


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1 - ss_res / (ss_tot + 1e-15))


# ══════════════════════════════════════════════════════════════════════════════
#  CALIBRATION — curve_fit
# ══════════════════════════════════════════════════════════════════════════════

def calibrate_model(
    model_fn: Callable,
    x_data: list, y_data: list,
    param_names: list[str],
    p0: list[float] | None = None,
    bounds: tuple | None = None,
    method: str = "curve_fit",
) -> dict[str, Any]:
    """
    Calibre les paramètres d'un modèle par minimisation de l'erreur quadratique.

    Args:
        model_fn   : fonction f(x, *params) → y
        param_names: noms des paramètres
        p0         : valeurs initiales
        bounds     : ([min], [max]) pour chaque paramètre
        method     : "curve_fit" | "nelder_mead" | "differential_evolution"
    """
    x = np.asarray(x_data, dtype=np.float64)
    y = np.asarray(y_data, dtype=np.float64)
    n = len(y)
    p0 = p0 or [1.0] * len(param_names)

    if method == "curve_fit":
        try:
            kw = {}
            if bounds:
                kw["bounds"] = bounds
            popt, pcov = curve_fit(model_fn, x, y, p0=p0, maxfev=50000, **kw)
            y_pred  = model_fn(x, *popt)
            std_err = np.sqrt(np.diag(pcov)).tolist()
        except Exception as e:
            raise RuntimeError(f"curve_fit échoué : {e}")

    elif method == "nelder_mead":
        def objective(params):
            try:
                y_p = model_fn(x, *params)
                return _mse(y, y_p)
            except Exception:
                return 1e12

        res  = minimize(objective, p0, method="Nelder-Mead",
                        options={"maxiter": 50000, "xatol": 1e-8, "fatol": 1e-8})
        popt    = res.x
        y_pred  = model_fn(x, *popt)
        pcov    = None
        std_err = [None] * len(popt)

    elif method == "differential_evolution":
        if bounds is None:
            bounds = [(-100, 100)] * len(param_names)
        else:
            bounds = list(zip(bounds[0], bounds[1]))

        def objective(params):
            try:
                y_p = model_fn(x, *params)
                return _mse(y, y_p)
            except Exception:
                return 1e12

        res  = differential_evolution(objective, bounds, seed=42, maxiter=1000, tol=1e-9)
        popt    = res.x
        y_pred  = model_fn(x, *popt)
        pcov    = None
        std_err = [None] * len(popt)

    else:
        raise ValueError(f"Méthode '{method}' non reconnue.")

    params_dict = {name: float(val) for name, val in zip(param_names, popt)}
    r2_val      = _r2(y, y_pred)
    rmse_val    = float(np.sqrt(_mse(y, y_pred)))

    logger.info(f"Calibration ({method}) : R²={r2_val:.4f}, params={params_dict}")

    return {
        "method":      method,
        "params":      params_dict,
        "std_errors":  {name: se for name, se in zip(param_names, std_err)},
        "r2":          r2_val,
        "rmse":        rmse_val,
        "y_true":      y.tolist(),
        "y_pred":      y_pred.tolist(),
        "residuals":   (y - y_pred).tolist(),
        "n":           n,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MINIMISATION GÉNÉRALE
# ══════════════════════════════════════════════════════════════════════════════

def minimize_function(
    objective_values: list[float],
    param_values: list[float],
    method: str = "parabola",
) -> dict[str, Any]:
    """
    Trouve le minimum d'une fonction discrète (ex: RMSE vs paramètre).
    Utilise une interpolation parabolique ou spline.
    """
    from scipy.interpolate import UnivariateSpline

    p = np.asarray(param_values, dtype=np.float64)
    f = np.asarray(objective_values, dtype=np.float64)

    idx_min = int(np.argmin(f))
    p_min   = float(p[idx_min])
    f_min   = float(f[idx_min])

    # Interpolation spline pour trouver le minimum continu
    try:
        spline  = UnivariateSpline(p, f, s=0, k=min(3, len(p)-1))
        p_dense = np.linspace(p.min(), p.max(), 500)
        f_dense = spline(p_dense)
        idx_sp  = int(np.argmin(f_dense))
        p_opt   = float(p_dense[idx_sp])
        f_opt   = float(f_dense[idx_sp])
    except Exception:
        p_opt, f_opt = p_min, f_min
        p_dense, f_dense = p, f

    return {
        "p_optimal":     p_opt,
        "f_optimal":     f_opt,
        "p_discrete":    p.tolist(),
        "f_discrete":    f.tolist(),
        "p_dense":       p_dense.tolist(),
        "f_dense":       f_dense.tolist(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSE DE SENSIBILITÉ
# ══════════════════════════════════════════════════════════════════════════════

def sensitivity_analysis(
    model_fn: Callable,
    base_params: dict[str, float],
    x_data: list,
    y_data: list | None = None,
    variation_pct: float = 10.0,
) -> dict[str, Any]:
    """
    Analyse de sensibilité : mesure l'impact d'une variation ±variation_pct%
    de chaque paramètre sur la sortie du modèle.
    """
    x = np.asarray(x_data, dtype=np.float64)
    param_names = list(base_params.keys())
    base_vals   = list(base_params.values())

    y_base = model_fn(x, *base_vals)
    results = {}

    for i, (name, val) in enumerate(base_params.items()):
        if abs(val) < 1e-12:
            delta = variation_pct / 100
        else:
            delta = abs(val) * variation_pct / 100

        # Variation positive
        params_p = base_vals.copy()
        params_p[i] = val + delta
        y_plus = model_fn(x, *params_p)

        # Variation négative
        params_m = base_vals.copy()
        params_m[i] = val - delta
        y_minus = model_fn(x, *params_m)

        # Indice de sensibilité normalisé
        dy_mean = float(np.mean(np.abs(y_plus - y_minus)))
        sens    = dy_mean / (2 * delta + 1e-15) * (abs(val) / (np.std(y_base) + 1e-15))

        results[name] = {
            "base_value":   val,
            "delta":        delta,
            "sensitivity":  float(sens),
            "y_plus":       y_plus.tolist(),
            "y_minus":      y_minus.tolist(),
            "impact_range": [float(y_minus.min()), float(y_plus.max())],
        }

    # Classement par sensibilité
    ranked = sorted(results.items(), key=lambda kv: kv[1]["sensitivity"], reverse=True)

    return {
        "base_params": base_params,
        "variation_pct": variation_pct,
        "y_base":      y_base.tolist(),
        "results":     results,
        "ranking":     [name for name, _ in ranked],
    }
