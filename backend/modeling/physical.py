"""
modeling/physical.py
=====================
Modèles physiques et chimiques du génie des procédés.
Toutes les fonctions sont exportées directement (pas de classes)
pour correspondre aux imports des routes API.

Fonctions exportées :
  Cinétique  : kinetics_order0, kinetics_order1, kinetics_order2, fit_kinetics
  Réacteurs  : cstr_transient, pfr_steady_state
  Diffusion  : fick_diffusion
  Chaleur    : heat_transfer_newton
  Écoulement : darcy_flow
  Équilibre  : antoine_vapor_pressure
  RTD        : tanks_in_series_rtd
"""

from __future__ import annotations
import numpy as np
from scipy.integrate import odeint
from scipy.optimize import curve_fit
from scipy.special import erfc
from typing import List, Dict, Any, Optional
from loguru import logger


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# CINÉTIQUE CHIMIQUE
# ─────────────────────────────────────────────────────────────────────────────

def kinetics_order0(t: List[float], C0: float, k: float) -> Dict[str, Any]:
    """Cinétique ordre 0 : C(t) = max(C0 - k·t, 0)"""
    logger.debug("kinetics_order0")
    ta = np.array(t, dtype=float)
    C  = np.maximum(C0 - k * ta, 0.0)
    return {
        "model":    "kinetics_order0",
        "equation": "C(t) = C₀ - k·t",
        "params":   {"C0": C0, "k": k},
        "t":        ta.tolist(),
        "C":        C.tolist(),
    }


def kinetics_order1(t: List[float], C0: float, k: float) -> Dict[str, Any]:
    """Cinétique ordre 1 : C(t) = C0·exp(-k·t)"""
    logger.debug("kinetics_order1")
    ta = np.array(t, dtype=float)
    C  = C0 * np.exp(-k * ta)
    return {
        "model":    "kinetics_order1",
        "equation": "C(t) = C₀·exp(-k·t)",
        "params":   {"C0": C0, "k": k},
        "t":        ta.tolist(),
        "C":        C.tolist(),
    }


def kinetics_order2(t: List[float], C0: float, k: float) -> Dict[str, Any]:
    """Cinétique ordre 2 : C(t) = C0 / (1 + k·C0·t)"""
    logger.debug("kinetics_order2")
    ta = np.array(t, dtype=float)
    C  = C0 / (1.0 + k * C0 * ta)
    return {
        "model":    "kinetics_order2",
        "equation": "C(t) = C₀ / (1 + k·C₀·t)",
        "params":   {"C0": C0, "k": k},
        "t":        ta.tolist(),
        "C":        C.tolist(),
    }


def fit_kinetics(
    t_data: List[float],
    C_data: List[float],
    order: int = 1,
) -> Dict[str, Any]:
    """Calibration de k et C0 sur données expérimentales via curve_fit."""
    logger.info(f"fit_kinetics ordre={order}")
    ta, Ca = np.array(t_data, dtype=float), np.array(C_data, dtype=float)

    if order == 0:
        def model(t, C0, k): return np.maximum(C0 - k * t, 0.0)
    elif order == 1:
        def model(t, C0, k): return C0 * np.exp(-k * t)
    else:  # order 2
        def model(t, C0, k): return C0 / (1.0 + k * C0 * t)

    popt, pcov = curve_fit(
        model, ta, Ca,
        p0=[float(Ca[0]), 0.01],
        bounds=(0, np.inf),
        maxfev=50000,
    )
    C0_fit, k_fit = float(popt[0]), float(popt[1])
    perr = np.sqrt(np.diag(pcov))
    C_fit = model(ta, C0_fit, k_fit)

    return {
        "model":  f"kinetics_order{order}",
        "order":  order,
        "C0":     C0_fit,
        "k":      k_fit,
        "C0_std": float(perr[0]),
        "k_std":  float(perr[1]),
        "r2":     round(_r2(Ca, C_fit), 6),
        "t":      ta.tolist(),
        "C":      C_fit.tolist(),   # ← courbe calibrée (lue par le frontend)
        "t_fit":  ta.tolist(),
        "C_fit":  C_fit.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BILAN DE MATIÈRE — CSTR
# ─────────────────────────────────────────────────────────────────────────────

def cstr_transient(
    t: List[float],
    V: float,
    F: float,
    C_in: float,
    C0: float,
    k: float,
) -> Dict[str, Any]:
    """
    CSTR transitoire avec réaction ordre 1 :
    V·dC/dt = F·(C_in - C) - k·V·C
    """
    logger.debug("cstr_transient")
    ta = np.array(t, dtype=float)

    def ode(C, t):
        return (F * (C_in - C) - k * V * C) / V

    C     = odeint(ode, C0, ta).flatten()
    C_eq  = C_in / (1.0 + k * V / F) if F > 0 else 0.0

    return {
        "model":         "cstr_transient",
        "equation":      "V·dC/dt = F·(C_in - C) - k·V·C",
        "params":        {"V": V, "F": F, "C_in": C_in, "C0": C0, "k": k},
        "equilibrium_C": round(float(C_eq), 6),
        "t":             ta.tolist(),
        "C":             C.tolist(),
    }


def pfr_steady_state(
    z: List[float],
    F: float,
    A: float,
    C0: float,
    k: float,
    order: int = 1,
) -> Dict[str, Any]:
    """PFR état stationnaire : u·dC/dz = -k·Cⁿ"""
    logger.debug(f"pfr ordre={order}")
    za = np.array(z, dtype=float)
    u  = F / A

    def ode(C, z):
        return -(k * max(float(C), 0.0) ** order) / u

    C = odeint(ode, C0, za).flatten()
    return {
        "model":    f"pfr_order{order}",
        "equation": f"u·dC/dz = -k·C^{order}",
        "params":   {"F": F, "A": A, "C0": C0, "k": k, "order": order},
        "z":        za.tolist(),
        "C":        C.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DIFFUSION — LOI DE FICK
# ─────────────────────────────────────────────────────────────────────────────

def fick_diffusion(
    x: List[float],
    t: float,
    D: float,
    C0: float,
    Cs: float,
) -> Dict[str, Any]:
    """
    Diffusion 1D semi-infinie (2ème loi de Fick) :
    C(x,t) = C0 + (Cs - C0)·erfc(x / (2·√(D·t)))
    """
    logger.debug("fick_diffusion")
    xa = np.array(x, dtype=float)
    xi = xa / (2.0 * np.sqrt(D * t + 1e-30))
    C  = C0 + (Cs - C0) * erfc(xi)
    return {
        "model":    "fick_diffusion",
        "equation": "C(x,t) = C₀ + (Cs-C₀)·erfc(x/2√(D·t))",
        "params":   {"D": D, "C0": C0, "Cs": Cs, "t": t},
        "x":        xa.tolist(),
        "C":        C.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFERT DE CHALEUR — LOI DE NEWTON
# ─────────────────────────────────────────────────────────────────────────────

def heat_transfer_newton(
    t: List[float],
    T0: float,
    T_inf: float,
    h: float,
    m: float,
    cp: float,
) -> Dict[str, Any]:
    """
    Refroidissement / chauffage de Newton :
    T(t) = T∞ + (T0 - T∞)·exp(-h·t / (m·Cp))
    """
    logger.debug("heat_transfer_newton")
    ta = np.array(t, dtype=float)
    k  = h / (m * cp + 1e-30)
    T  = T_inf + (T0 - T_inf) * np.exp(-k * ta)
    return {
        "model":    "heat_transfer_newton",
        "equation": "T(t) = T∞ + (T₀-T∞)·exp(-h·t/(m·Cp))",
        "params":   {"T0": T0, "T_inf": T_inf, "h": h, "m": m, "cp": cp},
        "t":        ta.tolist(),
        "T":        T.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# LOI DE DARCY
# ─────────────────────────────────────────────────────────────────────────────

def darcy_flow(
    dP: float,
    mu: float,
    k_perm: float,
    L: float,
    A: float,
) -> Dict[str, Any]:
    """Loi de Darcy : Q = k·A·ΔP / (μ·L)"""
    Q = k_perm * A * dP / (mu * L)
    return {
        "model":    "darcy_flow",
        "equation": "Q = k·A·ΔP / (μ·L)",
        "params":   {"dP": dP, "mu": mu, "k": k_perm, "L": L, "A": A},
        "Q":        round(float(Q), 10),
        "v_darcy":  round(float(Q / A), 10),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ÉQUATION D'ANTOINE
# ─────────────────────────────────────────────────────────────────────────────

def antoine_vapor_pressure(
    T_range: List[float],
    A: float,
    B: float,
    C: float,
) -> Dict[str, Any]:
    """log₁₀(P) = A - B/(C+T)  →  P en mmHg (paramètres NIST)"""
    Ta = np.array(T_range, dtype=float)
    P  = 10.0 ** (A - B / (C + Ta))
    return {
        "model":    "antoine",
        "equation": "log₁₀(P) = A - B/(C+T)",
        "params":   {"A": A, "B": B, "C": C},
        "T":        Ta.tolist(),
        "P_sat":    P.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTION DES TEMPS DE SÉJOUR — Tanks-in-Series
# ─────────────────────────────────────────────────────────────────────────────

def tanks_in_series_rtd(
    t: List[float],
    tau: float,
    N: int,
) -> Dict[str, Any]:
    """
    E(t) = (N/τ)ᴺ · t^(N-1) · exp(-N·t/τ) / (N-1)!
    """
    from math import factorial
    logger.debug(f"tanks_in_series N={N}")
    ta = np.array(t, dtype=float)
    # Éviter t=0 pour t^(N-1) si N>1
    ta_safe = np.where(ta <= 0, 1e-12, ta)
    E  = ((N / tau) ** N * ta_safe ** (N - 1) * np.exp(-N * ta_safe / tau)) / factorial(N - 1)
    return {
        "model":    "tanks_in_series",
        "equation": "E(t) = (N/τ)ᴺ·tᴺ⁻¹·exp(-N·t/τ)/(N-1)!",
        "params":   {"tau": tau, "N": N},
        "t":        ta.tolist(),
        "E":        E.tolist(),
    }