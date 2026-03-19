import numpy as np
from fastapi import APIRouter, HTTPException
from loguru import logger
from api.schemas import SimulationRequest
from modeling.physical import (kinetics_order0, kinetics_order1, kinetics_order2,
    cstr_transient, fick_diffusion, heat_transfer_newton, tanks_in_series_rtd)

router = APIRouter()

@router.post("/simulate")
async def simulate(req: SimulationRequest):
    t = np.linspace(req.t_start, req.t_end, req.n_points).tolist()
    p = req.params
    try:
        if req.model == "kinetics_order0":  return kinetics_order0(t, p.get("C0",1), p.get("k",0.1))
        elif req.model == "kinetics_order1":return kinetics_order1(t, p.get("C0",1), p.get("k",0.1))
        elif req.model == "kinetics_order2":return kinetics_order2(t, p.get("C0",1), p.get("k",0.1))
        elif req.model == "cstr":    return cstr_transient(t,p.get("V",1),p.get("F",0.1),p.get("C_in",1),p.get("C0",0),p.get("k",0.5))
        elif req.model == "heat":    return heat_transfer_newton(t,p.get("T0",100),p.get("T_inf",20),p.get("h",10),p.get("m",1),p.get("cp",4186))
        elif req.model == "rtd":     return tanks_in_series_rtd(t, p.get("tau",10), p.get("N",3))
        elif req.model == "diffusion":
            x_arr = np.linspace(0, p.get("L",0.01), req.n_points).tolist()
            return fick_diffusion(x_arr, p.get("t",100), p.get("D",1e-9), p.get("C0",0), p.get("Cs",1))
        else: raise HTTPException(400, f"Modèle inconnu: {req.model}")
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))
