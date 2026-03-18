"""api/routes_optimize.py — Endpoints /optimize"""
import sys, os
_b = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _b not in sys.path: sys.path.insert(0, _b)


import logging
import numpy as np
from fastapi import APIRouter, HTTPException
from api.schemas import OptimizeRequest, SensitivityRequest
from optimization.optimizer import calibrate_model, sensitivity_analysis

router = APIRouter()
logger = logging.getLogger("physioai.api.optimize")


def _build_physics_fn(model_name: str):
    """Construit la fonction physique à partir du nom du modèle."""
    from modeling.physical_models import (
        kinetics_order0, kinetics_order1, kinetics_order2, newton_cooling
    )

    if model_name == "kinetics":
        # Retourne une fonction f(t, C0, k) — ordre déterminé dynamiquement
        return kinetics_order1   # ordre 1 par défaut, override via param_names

    dispatch = {
        "kinetics_order0": kinetics_order0,   # f(t, C0, k)
        "kinetics_order1": kinetics_order1,   # f(t, C0, k)
        "kinetics_order2": kinetics_order2,   # f(t, C0, k)
        "cooling":         lambda t, h, T0=100, T_env=20: newton_cooling(t, T0, T_env, h),
    }

    fn = dispatch.get(model_name)
    if fn is None:
        raise ValueError(f"Modèle '{model_name}' non supporté pour l'optimisation.")
    return fn


@router.post("/calibrate", summary="Calibration automatique des paramètres")
async def calibrate(req: OptimizeRequest):
    """
    Calibre les paramètres d'un modèle physique par minimisation de l'erreur.

    Méthodes disponibles :
    - curve_fit              : Levenberg-Marquardt (rapide, local)
    - nelder_mead            : Simplex (robuste, sans gradient)
    - differential_evolution : Évolution différentielle (global, lent)
    """
    try:
        fn = _build_physics_fn(req.physics_model.value)

        bounds = None
        if req.bounds_min and req.bounds_max:
            bounds = (req.bounds_min, req.bounds_max)

        result = calibrate_model(
            model_fn=fn,
            x_data=req.x_data,
            y_data=req.y_data,
            param_names=req.param_names,
            p0=req.p0,
            bounds=bounds,
            method=req.method.value,
        )
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"/optimize/calibrate : {e}")
        raise HTTPException(400, str(e))


@router.post("/sensitivity", summary="Analyse de sensibilité")
async def sensitivity(req: SensitivityRequest):
    """
    Calcule la sensibilité du modèle à chaque paramètre.
    Mesure l'impact d'une variation ±N% sur la sortie.
    """
    try:
        fn = _build_physics_fn(req.physics_model.value)

        result = sensitivity_analysis(
            model_fn=fn,
            base_params=req.base_params,
            x_data=req.x_data,
            variation_pct=req.variation_pct,
        )
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"/optimize/sensitivity : {e}")
        raise HTTPException(400, str(e))


@router.post("/auto", summary="Optimisation automatique complète")
async def auto_optimize(
    model: str, x_data: list[float], y_data: list[float],
    method: str = "curve_fit",
):
    """
    Essaie automatiquement plusieurs modèles physiques et retourne
    le meilleur ajustement avec les paramètres calibrés.
    """
    try:
        from modeling.physical_models import (
            kinetics_order0, kinetics_order1, kinetics_order2
        )
        from sklearn.metrics import r2_score

        x = np.asarray(x_data)
        y = np.asarray(y_data)

        candidates = [
            ("kinetics_order0", kinetics_order0, ["C0", "k"], [y.max(), 0.01]),
            ("kinetics_order1", kinetics_order1, ["C0", "k"], [y.max(), 0.01]),
            ("kinetics_order2", kinetics_order2, ["C0", "k"], [y.max(), 0.01]),
        ]

        best    = None
        results = []

        for name, fn, params, p0 in candidates:
            try:
                from optimization.optimizer import calibrate_model
                res = calibrate_model(fn, x_data, y_data, params, p0,
                                      bounds=([0, 1e-6], [np.inf, np.inf]),
                                      method=method)
                results.append({"model": name, "r2": res["r2"], "params": res["params"]})
                if best is None or res["r2"] > best["r2"]:
                    best = {"model": name, "r2": res["r2"], "params": res["params"], "full": res}
            except Exception:
                pass

        results.sort(key=lambda r: r["r2"], reverse=True)
        return {"status": "ok", "best": best, "all_results": results}

    except Exception as e:
        logger.error(f"/optimize/auto : {e}")
        raise HTTPException(400, str(e))