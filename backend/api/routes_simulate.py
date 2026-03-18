"""api/routes_simulate.py — Endpoints /simulate"""
import sys, os
_b = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _b not in sys.path: sys.path.insert(0, _b)


import logging
import numpy as np
from fastapi import APIRouter, HTTPException
from api.schemas import SimulateRequest
from modeling.physical_models import (
    simulate_kinetics, simulate_diffusion,
    simulate_batch_reactor, simulate_cstr_steady_state, simulate_cooling,
    kinetics_order0, kinetics_order1, kinetics_order2,
)

router = APIRouter()
logger = logging.getLogger("physioai.api.simulate")


@router.post("/", summary="Simulation physique")
async def simulate(req: SimulateRequest):
    """
    Lance une simulation du modèle physique sélectionné sur une grille temporelle.
    Optionnellement compare le modèle aux données observées.
    """
    try:
        p   = req.params
        m   = req.model.value
        t   = np.linspace(req.t_start, req.t_end, req.n_points)

        if m == "kinetics":
            order = int(p.get("order", 1))
            C0    = p.get("C0", 1.0)
            k     = p.get("k", 0.1)
            res   = simulate_kinetics(t.tolist(), order=order, C0_guess=C0, k_guess=k, t_max=req.t_end)

        elif m == "batch_reactor":
            res = simulate_batch_reactor(
                C0=p.get("C0", 1.0), k=p.get("k", 0.1),
                order=int(p.get("order", 1)),
                t_end=req.t_end, n_points=req.n_points, V=p.get("V", 1.0),
            )
        elif m == "cstr":
            import numpy as np
            tau_range = np.logspace(-1, 3, req.n_points).tolist()
            res = simulate_cstr_steady_state(
                C0=p.get("C0", 1.0), k=p.get("k", 0.1),
                order=int(p.get("order", 1)), tau_values=tau_range,
            )
        elif m == "diffusion":
            res = simulate_diffusion(
                D=p.get("D", 1e-9),
                C_surface=p.get("C_surface", 1.0),
                C_init=p.get("C_init", 0.0),
                x_max=p.get("x_max", 1e-3),
                t_values=p.get("t_values", [1, 10, 100, 1000]),
            )
        elif m == "cooling":
            res = simulate_cooling(
                T0=p.get("T0", 100.0), T_env=p.get("T_env", 20.0),
                h=p.get("h", 0.05), t_end=req.t_end, n_points=req.n_points,
            )
        else:
            raise ValueError(f"Modèle '{m}' non supporté pour la simulation.")

        # Comparaison modèle vs données si fournies
        if req.compare_with:
            t_obs = np.asarray(req.compare_with.get("t", []), dtype=np.float64)
            y_obs = np.asarray(req.compare_with.get("y", []), dtype=np.float64)
            res["comparison"] = {
                "t_obs": t_obs.tolist(),
                "y_obs": y_obs.tolist(),
            }

        return {"status": "ok", **res}
    except Exception as e:
        logger.error(f"/simulate : {e}")
        raise HTTPException(400, str(e))


@router.post("/temporal", summary="Évolution temporelle multi-paramètres")
async def simulate_temporal(
    model: str, params_list: list[dict], t_end: float = 100.0, n_points: int = 200
):
    """Simule le même modèle pour plusieurs jeux de paramètres (comparaison)."""
    try:
        t = np.linspace(0, t_end, n_points).tolist()
        curves = []

        for i, p in enumerate(params_list):
            order = int(p.get("order", 1))
            C0, k = p.get("C0", 1.0), p.get("k", 0.1)
            fn_map = {0: kinetics_order0, 1: kinetics_order1, 2: kinetics_order2}
            fn = fn_map.get(order, kinetics_order1)
            C  = fn(np.asarray(t), C0, k).tolist()
            curves.append({"params": p, "t": t, "C": C, "label": p.get("label", f"Courbe {i+1}")})

        return {"status": "ok", "curves": curves}
    except Exception as e:
        raise HTTPException(400, str(e))