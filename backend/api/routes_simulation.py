"""
api/routes_simulation.py
=========================
POST /simulate — Lance n'importe quel modèle physique
sur un domaine temporel ou spatial généré automatiquement.

Modèles supportés :
  kinetics_order0/1/2, cstr, pfr, diffusion, heat, darcy, antoine, rtd
"""

import numpy as np
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import SimulationRequest
from modeling.physical import (
    kinetics_order0, kinetics_order1, kinetics_order2,
    cstr_transient, pfr_steady_state,
    fick_diffusion, heat_transfer_newton,
    darcy_flow, antoine_vapor_pressure,
    tanks_in_series_rtd,
)

router = APIRouter()


@router.post("/simulate",
             summary="Simulation universelle",
             description="Simule n'importe quel modèle physique sur un domaine auto-généré.")
async def simulate(req: SimulationRequest):
    logger.info(f"POST /simulate  modèle={req.model}")
    t   = np.linspace(req.t_start, req.t_end, req.n_points).tolist()
    p   = req.params

    try:
        # ── Cinétique ──────────────────────────────────────────────────────────
        if req.model == "kinetics_order0":
            return kinetics_order0(t, p.get("C0", 1.0), p.get("k", 0.1))

        elif req.model == "kinetics_order1":
            return kinetics_order1(t, p.get("C0", 1.0), p.get("k", 0.1))

        elif req.model == "kinetics_order2":
            return kinetics_order2(t, p.get("C0", 1.0), p.get("k", 0.1))

        # ── Réacteurs ──────────────────────────────────────────────────────────
        elif req.model == "cstr":
            return cstr_transient(
                t,
                V=p.get("V", 1.0),
                F=p.get("F", 0.1),
                C_in=p.get("C_in", 1.0),
                C0=p.get("C0", 0.0),
                k=p.get("k", 0.5),
            )

        elif req.model == "pfr":
            z = np.linspace(0, p.get("L", 1.0), req.n_points).tolist()
            return pfr_steady_state(
                z,
                F=p.get("F", 1.0),
                A=p.get("A", 0.1),
                C0=p.get("C0", 1.0),
                k=p.get("k", 0.1),
                order=int(p.get("order", 1)),
            )

        # ── Diffusion ──────────────────────────────────────────────────────────
        elif req.model == "diffusion":
            x = np.linspace(0, p.get("L", 0.01), req.n_points).tolist()
            return fick_diffusion(
                x,
                t=p.get("t", 100.0),
                D=p.get("D", 1e-9),
                C0=p.get("C0", 0.0),
                Cs=p.get("Cs", 1.0),
            )

        # ── Transfert de chaleur ───────────────────────────────────────────────
        elif req.model == "heat":
            return heat_transfer_newton(
                t,
                T0=p.get("T0", 100.0),
                T_inf=p.get("T_inf", 20.0),
                h=p.get("h", 10.0),
                m=p.get("m", 1.0),
                cp=p.get("cp", 4186.0),
            )

        # ── Darcy ──────────────────────────────────────────────────────────────
        elif req.model == "darcy":
            # Darcy est un calcul scalaire — on retourne directement
            return darcy_flow(
                dP=p.get("dP", 1000.0),
                mu=p.get("mu", 0.001),
                k_perm=p.get("k_perm", 1e-12),
                L=p.get("L", 1.0),
                A=p.get("A", 0.01),
            )

        # ── Antoine ────────────────────────────────────────────────────────────
        elif req.model == "antoine":
            T_range = np.linspace(
                p.get("T_min", req.t_start),
                p.get("T_max", req.t_end),
                req.n_points,
            ).tolist()
            return antoine_vapor_pressure(
                T_range,
                A=p.get("A", 8.07131),
                B=p.get("B", 1730.63),
                C=p.get("C", 233.426),
            )

        # ── DTS / RTD ──────────────────────────────────────────────────────────
        elif req.model == "rtd":
            return tanks_in_series_rtd(
                t,
                tau=p.get("tau", 10.0),
                N=int(p.get("N", 3)),
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Modèle '{req.model}' inconnu. "
                    "Valeurs valides : kinetics_order0, kinetics_order1, kinetics_order2, "
                    "cstr, pfr, diffusion, heat, darcy, antoine, rtd"
                ),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur simulation {req.model}: {e}")
        raise HTTPException(status_code=500, detail=str(e))