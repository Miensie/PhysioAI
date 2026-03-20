"""
ai/physical_scorer.py
======================
Teste et calibre tous les modèles physiques sur les données expérimentales.
Retourne le R² de chaque modèle pour permettre un classement objectif.
Utilisé par ai_advisor.py et routes_predict.py (décision rapide).
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import curve_fit
from scipy.special import erfc
from sklearn.metrics import r2_score
from typing import List, Dict, Any, Tuple
from loguru import logger


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot < 1e-12:
        return 1.0 if ss_res < 1e-12 else 0.0
    return float(1 - ss_res / ss_tot)


def _fit(fn, x, y, p0, bounds=(-np.inf, np.inf)) -> Tuple[np.ndarray, float]:
    """Calibration curve_fit avec fallback. Retourne (popt, r2)."""
    popt, _ = curve_fit(fn, x, y, p0=p0, bounds=bounds, maxfev=20000)
    r2 = _safe_r2(y, fn(x, *popt))
    return popt, r2


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions modèles physiques
# ─────────────────────────────────────────────────────────────────────────────

def _kinetics0(x, C0, k):
    return np.maximum(C0 - k * x, 0.0)

def _kinetics1(x, C0, k):
    return C0 * np.exp(-k * x)

def _kinetics2(x, C0, k):
    return C0 / (1.0 + k * C0 * x)

def _heat_newton(x, T0, T_inf, rate):
    """T(t) = T_inf + (T0-T_inf)*exp(-rate*t)  où rate = h/(m*Cp)"""
    return T_inf + (T0 - T_inf) * np.exp(-rate * x)

def _fick_semi(x, Cs, C0, D_t):
    """C(x,t) = C0 + (Cs-C0)*erfc(x/2*sqrt(D*t))  — D*t groupé"""
    xi = x / (2.0 * np.sqrt(np.abs(D_t) + 1e-30))
    return C0 + (Cs - C0) * erfc(xi)

def _cstr(x, Ceq, tau_eff):
    """C(t) ≈ Ceq*(1 - exp(-t/tau_eff))  — approximation CSTR ordre 1"""
    return Ceq * (1.0 - np.exp(-x / (np.abs(tau_eff) + 1e-9)))

def _rtd_peak(x, tau, N):
    """Mode du RTD Tanks-in-Series — pic de E(t)"""
    from math import factorial
    N_int = max(1, int(round(N)))
    x_safe = np.where(x <= 0, 1e-9, x)
    E = ((N_int / tau) ** N_int * x_safe ** (N_int - 1)
         * np.exp(-N_int * x_safe / tau)) / factorial(N_int - 1)
    return E

def _antoine(x, A, B, C_param):
    """log10(P) = A - B/(C+T)"""
    return 10.0 ** (A - B / (C_param + x))

def _michaelis_menten(x, Vmax, Km):
    """v = Vmax*S/(Km+S)"""
    return Vmax * x / (Km + x)

def _langmuir(x, qm, KL):
    """qe = qm*KL*Ce/(1+KL*Ce)"""
    return qm * KL * x / (1.0 + KL * x)

def _arrhenius_like(x, A, Ea_R):
    """k = A*exp(-Ea/R/T) — Ea/R groupé, x = 1/T"""
    return A * np.exp(-Ea_R * x)


# ─────────────────────────────────────────────────────────────────────────────
# Constructeurs de description
# ─────────────────────────────────────────────────────────────────────────────

def _desc_kinetics0(popt):
    return (f"C(t) = max({popt[0]:.4f} - {popt[1]:.4f}·t, 0)",
            {"C0": popt[0], "k": popt[1]})

def _desc_kinetics1(popt):
    return (f"C(t) = {popt[0]:.4f}·exp(-{popt[1]:.4f}·t)",
            {"C0": popt[0], "k": popt[1]})

def _desc_kinetics2(popt):
    return (f"C(t) = {popt[0]:.4f} / (1 + {popt[1]:.4f}·{popt[0]:.4f}·t)",
            {"C0": popt[0], "k": popt[1]})

def _desc_heat(popt):
    return (f"T(t) = {popt[1]:.3f} + {popt[0]-popt[1]:.3f}·exp(-{popt[2]:.5f}·t)",
            {"T0": popt[0], "T_inf": popt[1], "rate_h_mCp": popt[2]})

def _desc_fick(popt):
    return (f"C(x) = {popt[1]:.4f} + ({popt[0]-popt[1]:.4f})·erfc(x/2sqrt(Dt))",
            {"Cs": popt[0], "C0": popt[1], "D_t": popt[2]})

def _desc_cstr(popt):
    return (f"C(t) = {popt[0]:.4f}·(1 - exp(-t/{popt[1]:.4f}))",
            {"Ceq": popt[0], "tau_eff": popt[1]})

def _desc_mm(popt):
    return (f"v = {popt[0]:.4f}·S / ({popt[1]:.4f} + S)",
            {"Vmax": popt[0], "Km": popt[1]})

def _desc_langmuir(popt):
    return (f"qe = {popt[0]:.4f}·{popt[1]:.4f}·Ce / (1 + {popt[1]:.4f}·Ce)",
            {"qm": popt[0], "KL": popt[1]})

def _desc_rtd(popt):
    return (f"E(t) — Tanks-in-Series : tau={popt[0]:.3f}, N={int(round(popt[1]))}",
            {"tau": popt[0], "N": int(round(popt[1]))})

def _desc_antoine(popt):
    return (f"log10(P) = {popt[0]:.4f} - {popt[1]:.4f}/({popt[2]:.4f}+T)",
            {"A": popt[0], "B": popt[1], "C": popt[2]})

def _desc_arrhenius(popt):
    return (f"k = {popt[0]:.4e}·exp(-{popt[1]:.2f}/T)",
            {"A": popt[0], "Ea_R": popt[1]})


# ─────────────────────────────────────────────────────────────────────────────
# Catalogue complet des modèles physiques à tester
# ─────────────────────────────────────────────────────────────────────────────

def _get_candidates(x: np.ndarray, y: np.ndarray) -> List[Dict]:
    """
    Retourne la liste des modèles physiques à tenter,
    avec paramètres initiaux adaptés aux données.
    """
    x_range = float(x.max() - x.min()) + 1e-9
    y_mean  = float(np.mean(y))
    y_max   = float(y.max())
    y_min   = float(y.min())
    y_range = float(y_max - y_min) + 1e-9
    x_mean  = float(np.mean(x))

    return [
        # ── Cinétique ──────────────────────────────────────────────────────────
        {
            "name": "kinetics_order1",
            "label": "Cinetique Ordre 1",
            "fn": _kinetics1,
            "p0": [y_max, 1.0 / (x_mean + 1e-9)],
            "bounds": ([0, 0], [y_max * 10, np.inf]),
            "desc": _desc_kinetics1,
            "domain": "Chimie / pharmacologie / radioactivite",
        },
        {
            "name": "kinetics_order2",
            "label": "Cinetique Ordre 2",
            "fn": _kinetics2,
            "p0": [y_max, 0.01],
            "bounds": ([0, 0], [y_max * 10, np.inf]),
            "desc": _desc_kinetics2,
            "domain": "Reactions bimoleculaires",
        },
        {
            "name": "kinetics_order0",
            "label": "Cinetique Ordre 0",
            "fn": _kinetics0,
            "p0": [y_max, y_range / x_range],
            "bounds": ([0, 0], [y_max * 10, np.inf]),
            "desc": _desc_kinetics0,
            "domain": "Reactions a concentration elevee / saturees",
        },
        # ── Thermique ──────────────────────────────────────────────────────────
        {
            "name": "heat_transfer_newton",
            "label": "Transfert Chaleur Newton",
            "fn": _heat_newton,
            "p0": [y_max, y_min, 1.0 / (x_mean + 1e-9)],
            "bounds": ([-np.inf, -np.inf, 0], [np.inf, np.inf, np.inf]),
            "desc": _desc_heat,
            "domain": "Refroidissement / chauffage transitoire",
        },
        # ── Diffusion ──────────────────────────────────────────────────────────
        {
            "name": "diffusion_fick",
            "label": "Diffusion Fick (semi-infini)",
            "fn": _fick_semi,
            "p0": [y_max, y_min, (x_range / 4) ** 2],
            "bounds": ([-np.inf, -np.inf, 0], [np.inf, np.inf, np.inf]),
            "desc": _desc_fick,
            "domain": "Diffusion de masse dans solide / liquide",
        },
        # ── Réacteurs ──────────────────────────────────────────────────────────
        {
            "name": "cstr_transient",
            "label": "CSTR Transitoire",
            "fn": _cstr,
            "p0": [y_max, x_mean],
            "bounds": ([0, 0], [y_max * 10, x_range * 10]),
            "desc": _desc_cstr,
            "domain": "Reacteur continu agite en regime transitoire",
        },
        # ── Cinétique enzymatique / adsorption ────────────────────────────────
        {
            "name": "michaelis_menten",
            "label": "Michaelis-Menten",
            "fn": _michaelis_menten,
            "p0": [y_max, x_mean],
            "bounds": ([0, 0], [y_max * 10, x_range * 10]),
            "desc": _desc_mm,
            "domain": "Cinetique enzymatique / saturation",
        },
        {
            "name": "langmuir_adsorption",
            "label": "Isotherme Langmuir",
            "fn": _langmuir,
            "p0": [y_max, 1.0 / (x_mean + 1e-9)],
            "bounds": ([0, 0], [y_max * 10, np.inf]),
            "desc": _desc_langmuir,
            "domain": "Adsorption de surface / saturation",
        },
        # ── DTS ───────────────────────────────────────────────────────────────
        {
            "name": "rtd_tanks_in_series",
            "label": "DTS Tanks-in-Series",
            "fn": _rtd_peak,
            "p0": [x_mean, 3.0],
            "bounds": ([0, 1], [x_range * 10, 20]),
            "desc": _desc_rtd,
            "domain": "Distribution des temps de sejour",
        },
        # ── Équilibre thermodynamique ─────────────────────────────────────────
        {
            "name": "antoine_vapor_pressure",
            "label": "Equation d'Antoine",
            "fn": _antoine,
            "p0": [8.0, 1500.0, 230.0],
            "bounds": ([0, 0, 0], [20, 5000, 500]),
            "desc": _desc_antoine,
            "domain": "Pression de vapeur saturante vs temperature",
        },
        # ── Arrhénius ─────────────────────────────────────────────────────────
        {
            "name": "arrhenius",
            "label": "Loi d'Arrhenius",
            "fn": _arrhenius_like,
            "p0": [y_max, x_mean * 1000],
            "bounds": ([0, 0], [np.inf, np.inf]),
            "desc": _desc_arrhenius,
            "domain": "Constante de vitesse vs temperature (1/T en x)",
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def score_physical_models(x: List[float], y: List[float]) -> Dict[str, Any]:
    """
    Teste et calibre tous les modèles physiques sur les données.
    Retourne un classement par R² avec équation et paramètres calibrés.
    """
    logger.info(f"score_physical_models — {len(x)} points — {len(_get_candidates(np.array(x), np.array(y)))} modeles")

    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)

    candidates = _get_candidates(xa, ya)
    results    = {}

    for cand in candidates:
        name = cand["name"]
        try:
            popt, r2 = _fit(cand["fn"], xa, ya, cand["p0"], cand["bounds"])
            equation, params = cand["desc"](popt)
            results[name] = {
                "r2":       round(r2, 6),
                "equation": equation,
                "params":   {k: round(float(v), 8) for k, v in params.items()},
                "label":    cand["label"],
                "domain":   cand["domain"],
            }
        except Exception as e:
            logger.debug(f"  Modele {name} non applicable: {e}")
            results[name] = {
                "r2":    -1.0,
                "label": cand["label"],
                "domain": cand["domain"],
                "error": str(e)[:80],
            }

    # Classement par R² décroissant (exclure erreurs)
    ranking = sorted(
        [(k, v) for k, v in results.items() if "error" not in v and v["r2"] >= 0],
        key=lambda x: x[1]["r2"], reverse=True
    )

    best = ranking[0] if ranking else None

    return {
        "scores":  results,
        "ranking": [
            {
                "model":    k,
                "label":    v["label"],
                "r2":       v["r2"],
                "equation": v.get("equation", ""),
                "domain":   v.get("domain", ""),
                "params":   v.get("params", {}),
            }
            for k, v in ranking
        ],
        "best_physical": {
            "model":    best[0] if best else None,
            "label":    best[1]["label"] if best else None,
            "r2":       best[1]["r2"] if best else None,
            "equation": best[1].get("equation", "") if best else None,
            "params":   best[1].get("params", {}) if best else {},
        } if best else None,
        "n_tested":    len(candidates),
        "n_successful": len(ranking),
    }