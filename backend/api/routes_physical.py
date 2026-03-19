from fastapi import APIRouter, HTTPException
from loguru import logger
from api.schemas import KineticsRequest, CSTRRequest, FickRequest, HeatRequest
from modeling.physical import (kinetics_order0, kinetics_order1, kinetics_order2,
    fit_kinetics, fick_diffusion, cstr_transient, heat_transfer_newton, tanks_in_series_rtd)

router = APIRouter()

@router.post("/physical/kinetics")
async def kinetics(req: KineticsRequest):
    try:
        if req.fit and req.C:
            return fit_kinetics(req.t, req.C, req.order)
        elif req.order == 0: return kinetics_order0(req.t, req.C0, req.k)
        elif req.order == 1: return kinetics_order1(req.t, req.C0, req.k)
        else:                return kinetics_order2(req.t, req.C0, req.k)
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/physical/cstr")
async def cstr(req: CSTRRequest):
    try: return cstr_transient(req.t, req.V, req.F, req.C_in, req.C0, req.k)
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/physical/diffusion")
async def diffusion(req: FickRequest):
    try: return fick_diffusion(req.x, req.t, req.D, req.C0, req.Cs)
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/physical/heat")
async def heat(req: HeatRequest):
    try: return heat_transfer_newton(req.t, req.T0, req.T_inf, req.h, req.m, req.cp)
    except Exception as e: raise HTTPException(500, str(e))
