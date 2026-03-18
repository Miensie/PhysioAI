"""api/routes_model.py — Endpoints /model"""
import sys, os
_b = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _b not in sys.path: sys.path.insert(0, _b)


import logging
from fastapi import APIRouter, HTTPException
from api.schemas import RegressionRequest, PhysicsRequest
from modeling.regression import (
    linear_regression, polynomial_regression,
    regularized_regression, multivariate_regression,
)
from modeling.physical_models import (
    simulate_kinetics, simulate_diffusion,
    simulate_batch_reactor, simulate_cstr_steady_state, simulate_cooling,
)

router = APIRouter()
logger = logging.getLogger("physioai.api.model")


@router.post("/regression", summary="Régression statistique")
async def model_regression(req: RegressionRequest):
    """Régression linéaire, polynomiale, Ridge ou Lasso."""
    try:
        if req.type == "linear":
            res = linear_regression(req.x, req.y)
        elif req.type == "polynomial":
            res = polynomial_regression(req.x, req.y, degree=req.degree)
        elif req.type in ("ridge", "lasso"):
            res = regularized_regression(req.x, req.y, method=req.type, alpha=req.alpha, degree=req.degree)
        elif req.type == "multivariate":
            res = multivariate_regression([req.x], req.y)
        else:
            raise ValueError(f"Type de régression inconnu : {req.type}")
        return {"status": "ok", **res}
    except Exception as e:
        logger.error(f"/model/regression : {e}")
        raise HTTPException(400, str(e))


@router.post("/physics", summary="Modèle physique")
async def model_physics(req: PhysicsRequest):
    """Modèles physico-chimiques : cinétique, diffusion, réacteurs, refroidissement."""
    try:
        m = req.model.value
        if m == "kinetics":
            res = simulate_kinetics(
                t_data=req.t or [], C_data=req.C,
                order=int(req.order),
                C0_guess=req.C0_guess, k_guess=req.k_guess,
                t_max=req.t_max,
            )
        elif m == "diffusion":
            res = simulate_diffusion(
                D=req.D, C_surface=req.C_surface, C_init=req.C_init,
                x_max=req.x_max, t_values=req.t_values,
            )
        elif m == "batch_reactor":
            res = simulate_batch_reactor(
                C0=req.C0_guess, k=req.k_guess,
                order=int(req.order), t_end=req.t_end, V=req.V,
            )
        elif m == "cstr":
            res = simulate_cstr_steady_state(
                C0=req.C0_guess, k=req.k_guess, order=int(req.order),
            )
        elif m == "cooling":
            res = simulate_cooling(
                T0=req.T0, T_env=req.T_env, h=req.h,
                t_end=req.t_end,
                T_data=req.T_data, t_obs=req.t_obs,
            )
        else:
            raise ValueError(f"Modèle physique inconnu : {m}")
        return {"status": "ok", **res}
    except Exception as e:
        logger.error(f"/model/physics : {e}")
        raise HTTPException(400, str(e))