"""
================================================================
modeling/physical_models.py
Modèles physico-chimiques :
  - Bilan de matière (CSTR, PFR, batch)
  - Cinétique chimique (ordre 0, 1, 2)
  - Diffusion (loi de Fick 1D)
  - Transfert de chaleur (refroidissement de Newton)
================================================================
"""

import logging
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import curve_fit

logger = logging.getLogger("physioai.physics")


# ══════════════════════════════════════════════════════════════════════════════
#  CINÉTIQUE CHIMIQUE
# ══════════════════════════════════════════════════════════════════════════════

def kinetics_order0(t: np.ndarray, C0: float, k: float) -> np.ndarray:
    """C(t) = C0 - k·t  (réaction ordre 0)"""
    return np.maximum(C0 - k * t, 0)


def kinetics_order1(t: np.ndarray, C0: float, k: float) -> np.ndarray:
    """C(t) = C0·exp(-k·t)  (réaction ordre 1)"""
    return C0 * np.exp(-k * t)


def kinetics_order2(t: np.ndarray, C0: float, k: float) -> np.ndarray:
    """C(t) = C0 / (1 + k·C0·t)  (réaction ordre 2)"""
    denom = 1.0 + k * C0 * t
    return C0 / np.where(denom > 1e-15, denom, 1e-15)


def arrhenius(T: np.ndarray, A: float, Ea: float, R: float = 8.314) -> np.ndarray:
    """k(T) = A·exp(-Ea / R·T)  (loi d'Arrhénius)"""
    return A * np.exp(-Ea / (R * T))


def simulate_kinetics(
    t_data: list, C_data: list | None = None,
    order: int = 1,
    C0_guess: float = 1.0, k_guess: float = 0.1,
    t_max: float | None = None, n_points: int = 200,
) -> dict[str, Any]:
    """
    Simule et/ou calibre une cinétique chimique d'ordre 0, 1 ou 2.

    Si C_data fourni : calibration par curve_fit
    Sinon            : simulation pure avec les paramètres guess
    """
    t = np.asarray(t_data, dtype=np.float64)
    if t_max is None:
        t_max = float(t.max()) * 1.1 if len(t) > 0 else 10.0

    model_map = {0: kinetics_order0, 1: kinetics_order1, 2: kinetics_order2}
    if order not in model_map:
        raise ValueError(f"Ordre {order} non supporté. Choisir 0, 1 ou 2.")
    f_model = model_map[order]

    # ── Calibration si données ──
    params   = {"C0": C0_guess, "k": k_guess}
    cov      = None
    r2       = None
    y_pred   = None
    residuals = None

    if C_data is not None:
        C = np.asarray(C_data, dtype=np.float64)
        p0 = [C0_guess, k_guess]
        bounds = ([0, 0], [np.inf, np.inf])
        try:
            popt, pcov = curve_fit(f_model, t, C, p0=p0, bounds=bounds, maxfev=10000)
            params = {"C0": float(popt[0]), "k": float(popt[1])}
            cov    = pcov.tolist()
            y_pred = f_model(t, *popt).tolist()
            residuals = (C - np.array(y_pred)).tolist()
            ss_res = np.sum((C - np.array(y_pred)) ** 2)
            ss_tot = np.sum((C - C.mean()) ** 2)
            r2 = float(1 - ss_res / (ss_tot + 1e-15))
            logger.info(f"Cinétique ordre {order} calibrée : C0={params['C0']:.4f}, k={params['k']:.4f}, R²={r2:.4f}")
        except Exception as e:
            logger.warning(f"Calibration cinétique échouée : {e}")

    # ── Simulation sur grille dense ──
    t_sim   = np.linspace(0, t_max, n_points)
    C0, k   = params["C0"], params["k"]
    C_sim   = f_model(t_sim, C0, k)

    # Demi-vie
    half_life = None
    if order == 1 and k > 0:
        half_life = float(np.log(2) / k)
    elif order == 0 and k > 0:
        half_life = float(C0 / (2 * k))
    elif order == 2 and k > 0 and C0 > 0:
        half_life = float(1 / (k * C0))

    return {
        "model":      f"kinetics_order{order}",
        "order":      order,
        "params":     params,
        "covariance": cov,
        "r2":         r2,
        "t_obs":      t.tolist(),
        "C_obs":      C_data,
        "C_pred_obs": y_pred,
        "residuals":  residuals,
        "t_sim":      t_sim.tolist(),
        "C_sim":      C_sim.tolist(),
        "half_life":  half_life,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  DIFFUSION — Loi de Fick
# ══════════════════════════════════════════════════════════════════════════════

def fick_1d_analytical(
    x: np.ndarray, t: float, D: float,
    C_surface: float = 1.0, C_init: float = 0.0, n_terms: int = 50,
) -> np.ndarray:
    """
    Solution analytique de l'équation de diffusion 1D (Fick 2ème loi)
    pour une plaque semi-infinie :
        C(x,t) = C_surface · erfc(x / (2·√(D·t)))
    """
    from scipy.special import erfc
    C = (C_surface - C_init) * erfc(x / (2 * np.sqrt(D * t + 1e-15))) + C_init
    return C


def simulate_diffusion(
    D: float = 1e-9, C_surface: float = 1.0, C_init: float = 0.0,
    x_max: float = 1e-3, t_values: list | None = None,
    nx: int = 100,
) -> dict[str, Any]:
    """
    Simule la diffusion 1D (Fick) à plusieurs instants.

    Args:
        D         : coefficient de diffusion [m²/s]
        C_surface : concentration de surface [mol/m³]
        C_init    : concentration initiale [mol/m³]
        x_max     : profondeur maximale [m]
        t_values  : liste des temps [s]
        nx        : nombre de points spatiaux
    """
    if t_values is None:
        t_values = [1, 10, 100, 1000]

    x      = np.linspace(0, x_max, nx)
    profiles = {}

    for t in t_values:
        C = fick_1d_analytical(x, float(t), D, C_surface, C_init)
        profiles[f"t={t}s"] = C.tolist()

    # Flux de surface J = -D · dC/dx|_{x=0}
    fluxes = {
        f"t={t}s": float(-D * (C_surface - C_init) / np.sqrt(np.pi * D * float(t) + 1e-15))
        for t in t_values
    }

    return {
        "model":    "fick_1d",
        "D":        D,
        "x":        x.tolist(),
        "x_unit":   "m",
        "profiles": profiles,
        "fluxes":   fluxes,
        "t_values": t_values,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BILAN DE MATIÈRE — Réacteurs
# ══════════════════════════════════════════════════════════════════════════════

def _batch_ode(t, y, k, order):
    """ODE pour réacteur batch : dC/dt = -k·C^n"""
    C = max(y[0], 0)
    if order == 0:   return [-k]
    elif order == 1: return [-k * C]
    elif order == 2: return [-k * C**2]
    else:            return [-k * C**order]


def simulate_batch_reactor(
    C0: float, k: float, order: int = 1,
    t_end: float = 100.0, n_points: int = 300,
    V: float = 1.0,  # volume [L]
) -> dict[str, Any]:
    """
    Simule un réacteur batch (fermé) avec cinétique d'ordre n.
    Résout l'ODE via scipy solve_ivp (Runge-Kutta 4/5).
    """
    t_span  = (0, t_end)
    t_eval  = np.linspace(0, t_end, n_points)
    y0      = [C0]

    sol = solve_ivp(
        fun=_batch_ode, t_span=t_span, y0=y0,
        args=(k, order), t_eval=t_eval,
        method="RK45", rtol=1e-8, atol=1e-10,
    )

    if not sol.success:
        raise RuntimeError(f"Intégration ODE échouée : {sol.message}")

    C    = sol.y[0]
    conv = 1.0 - C / (C0 + 1e-15)  # taux de conversion X

    # Masse produite (bilan)
    M_consumed = (C0 - C) * V  # [mol]

    return {
        "model":      "batch_reactor",
        "order":      order,
        "params":     {"C0": C0, "k": k, "V": V},
        "t":          sol.t.tolist(),
        "C":          C.tolist(),
        "conversion": conv.tolist(),
        "M_consumed": M_consumed.tolist(),
        "t_end":      t_end,
        "solver":     "RK45",
    }


def simulate_cstr_steady_state(
    C0: float, k: float, order: int = 1,
    tau_values: list | None = None,
) -> dict[str, Any]:
    """
    CSTR (Continuous Stirred Tank Reactor) — état stationnaire.
    Bilan : C0 - C = τ · r(C)  →  résolution analytique si possible.
    """
    if tau_values is None:
        tau_values = np.logspace(-1, 3, 50).tolist()

    tau = np.asarray(tau_values, dtype=np.float64)
    C_out = np.zeros_like(tau)

    for i, t in enumerate(tau):
        if order == 0:
            C_out[i] = max(C0 - k * t, 0)
        elif order == 1:
            C_out[i] = C0 / (1 + k * t)
        elif order == 2:
            # Résolution quadratique : k·C² + C/τ - C0/τ = 0
            a, b, c = k, 1/t, -C0/t
            disc = b**2 - 4*a*c
            C_out[i] = (-b + np.sqrt(max(disc, 0))) / (2*a)

    conv = 1.0 - C_out / (C0 + 1e-15)

    return {
        "model":      "CSTR_steady",
        "order":      order,
        "params":     {"C0": C0, "k": k},
        "tau":        tau.tolist(),
        "C_out":      C_out.tolist(),
        "conversion": conv.tolist(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSFERT DE CHALEUR — Refroidissement de Newton
# ══════════════════════════════════════════════════════════════════════════════

def newton_cooling(
    t: np.ndarray, T0: float, T_env: float, h: float, m: float = 1.0, Cp: float = 1.0
) -> np.ndarray:
    """
    T(t) = T_env + (T0 - T_env) · exp(-h·t / (m·Cp))
    h  : coefficient de transfert [W/K]
    m  : masse [kg]
    Cp : chaleur spécifique [J/(kg·K)]
    """
    alpha = h / (m * Cp + 1e-15)
    return T_env + (T0 - T_env) * np.exp(-alpha * t)


def simulate_cooling(
    T0: float = 100.0, T_env: float = 20.0, h: float = 0.05,
    t_end: float = 200.0, n_points: int = 200,
    T_data: list | None = None, t_obs: list | None = None,
) -> dict[str, Any]:
    """Simule le refroidissement de Newton. Calibre h si des données sont fournies."""
    t_sim = np.linspace(0, t_end, n_points)
    params = {"T0": T0, "T_env": T_env, "h": h}
    r2 = None

    if T_data is not None and t_obs is not None:
        t_obs_arr = np.asarray(t_obs, dtype=np.float64)
        T_obs_arr = np.asarray(T_data, dtype=np.float64)
        try:
            f = lambda t, h_: newton_cooling(t, T0, T_env, h_)
            popt, _ = curve_fit(f, t_obs_arr, T_obs_arr, p0=[h], bounds=(0, np.inf))
            params["h"] = float(popt[0])
            T_pred = f(t_obs_arr, popt[0])
            ss_res = np.sum((T_obs_arr - T_pred)**2)
            ss_tot = np.sum((T_obs_arr - T_obs_arr.mean())**2)
            r2 = float(1 - ss_res / (ss_tot + 1e-15))
        except Exception as e:
            logger.warning(f"Calibration refroidissement échouée : {e}")

    T_sim = newton_cooling(t_sim, params["T0"], params["T_env"], params["h"])

    return {
        "model":  "newton_cooling",
        "params": params,
        "r2":     r2,
        "t_sim":  t_sim.tolist(),
        "T_sim":  T_sim.tolist(),
        "t_obs":  t_obs,
        "T_obs":  T_data,
    }
