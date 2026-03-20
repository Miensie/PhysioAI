"""
api/routes_physical.py
=======================
Expose les 11 fonctions physiques de modeling/physical.py :

  POST /physical/kinetics    — cinétique ordre 0/1/2 + calibration
  POST /physical/pfr         — réacteur piston (PFR) multi-ordres
  POST /physical/cstr        — CSTR transitoire
  POST /physical/diffusion   — diffusion Fick 1D semi-infinie
  POST /physical/heat        — transfert de chaleur Newton
  POST /physical/darcy       — écoulement milieu poreux (Darcy)
  POST /physical/antoine     — pression de vapeur saturante
  POST /physical/rtd         — distribution temps de séjour (Tanks-in-Series)
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import (
    KineticsRequest, CSTRRequest, FickRequest, HeatRequest,
    PFRRequest, DarcyRequest, AntoineRequest, RTDRequest,
)
from modeling.physical import (
    kinetics_order0,
    kinetics_order1,
    kinetics_order2,
    fit_kinetics,
    cstr_transient,
    pfr_steady_state,
    fick_diffusion,
    heat_transfer_newton,
    darcy_flow,
    antoine_vapor_pressure,
    tanks_in_series_rtd,
)

router = APIRouter()


# ── 1. Cinétique chimique (ordre 0 / 1 / 2 + calibration) ────────────────────

@router.post("/physical/kinetics",
             summary="Cinétique chimique",
             description="Simule ou calibre un modèle cinétique ordre 0, 1 ou 2.")
async def route_kinetics(req: KineticsRequest):
    logger.info(f"POST /physical/kinetics  ordre={req.order}  fit={req.fit}")
    try:
        if req.fit and req.C:
            return fit_kinetics(req.t, req.C, req.order)
        elif req.order == 0:
            return kinetics_order0(req.t, req.C0, req.k)
        elif req.order == 1:
            return kinetics_order1(req.t, req.C0, req.k)
        else:
            return kinetics_order2(req.t, req.C0, req.k)
    except Exception as e:
        logger.error(f"kinetics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 2. PFR — Réacteur Piston ──────────────────────────────────────────────────

@router.post("/physical/pfr",
             summary="Réacteur Piston (PFR)",
             description="Profil axial de concentration en régime stationnaire.")
async def route_pfr(req: PFRRequest):
    logger.info(f"POST /physical/pfr  ordre={req.order}")
    try:
        return pfr_steady_state(req.z, req.F, req.A, req.C0, req.k, req.order)
    except Exception as e:
        logger.error(f"PFR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 3. CSTR Transitoire ───────────────────────────────────────────────────────

@router.post("/physical/cstr",
             summary="CSTR Transitoire",
             description="Évolution temporelle de la concentration dans un CSTR.")
async def route_cstr(req: CSTRRequest):
    logger.info("POST /physical/cstr")
    try:
        return cstr_transient(req.t, req.V, req.F, req.C_in, req.C0, req.k)
    except Exception as e:
        logger.error(f"CSTR error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 4. Diffusion — Loi de Fick ────────────────────────────────────────────────

@router.post("/physical/diffusion",
             summary="Diffusion (Loi de Fick)",
             description="Profil de concentration par diffusion 1D semi-infinie.")
async def route_diffusion(req: FickRequest):
    logger.info("POST /physical/diffusion")
    try:
        return fick_diffusion(req.x, req.t, req.D, req.C0, req.Cs)
    except Exception as e:
        logger.error(f"Fick error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 5. Transfert de Chaleur — Newton ─────────────────────────────────────────

@router.post("/physical/heat",
             summary="Transfert de Chaleur (Newton)",
             description="Refroidissement ou chauffage transitoire d'un corps.")
async def route_heat(req: HeatRequest):
    logger.info("POST /physical/heat")
    try:
        return heat_transfer_newton(req.t, req.T0, req.T_inf, req.h, req.m, req.cp)
    except Exception as e:
        logger.error(f"Heat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 6. Loi de Darcy ───────────────────────────────────────────────────────────

@router.post("/physical/darcy",
             summary="Loi de Darcy",
             description="Débit et vitesse d'écoulement en milieu poreux.")
async def route_darcy(req: DarcyRequest):
    logger.info("POST /physical/darcy")
    try:
        return darcy_flow(req.dP, req.mu, req.k_perm, req.L, req.A)
    except Exception as e:
        logger.error(f"Darcy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 7. Équation d'Antoine ─────────────────────────────────────────────────────

@router.post("/physical/antoine",
             summary="Équation d'Antoine",
             description="Pression de vapeur saturante en fonction de la température.")
async def route_antoine(req: AntoineRequest):
    logger.info("POST /physical/antoine")
    try:
        return antoine_vapor_pressure(req.T_range, req.A, req.B, req.C)
    except Exception as e:
        logger.error(f"Antoine error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 8. Distribution des Temps de Séjour ──────────────────────────────────────

@router.post("/physical/rtd",
             summary="Distribution des Temps de Séjour",
             description="Modèle Tanks-in-Series pour la DTS d'un réacteur.")
async def route_rtd(req: RTDRequest):
    logger.info(f"POST /physical/rtd  N={req.N}  tau={req.tau}")
    try:
        return tanks_in_series_rtd(req.t, req.tau, req.N)
    except Exception as e:
        logger.error(f"RTD error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
