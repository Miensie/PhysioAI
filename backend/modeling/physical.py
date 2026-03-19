"""
PhysioAI Lab — Physical Models Module
Bilans matière, cinétique chimique, diffusion (Fick), transfert de chaleur, etc.
Résolution numérique via scipy.integrate.
"""

from __future__ import annotations
import numpy as np
from scipy.integrate import solve_ivp, odeint
from scipy.optimize import curve_fit
from typing import Callable

from utils.data_utils import r_squared, rmse


# ══════════════════════════════════════════════════════════════════════════════
# 1. CINÉTIQUE CHIMIQUE
# ══════════════════════════════════════════════════════════════════════════════

class ChemicalKinetics:
    """Modèles cinétiques : ordre 0, 1, 2 — A → Produits."""

    @staticmethod
    def order0(t: np.ndarray, C0: float, k: float) -> np.ndarray:
        """C(t) = C0 - k*t  (ordre 0)"""
        return np.maximum(C0 - k * t, 0.0)

    @staticmethod
    def order1(t: np.ndarray, C0: float, k: float) -> np.ndarray:
        """C(t) = C0 * exp(-k*t)  (ordre 1)"""
        return C0 * np.exp(-k * t)

    @staticmethod
    def order2(t: np.ndarray, C0: float, k: float) -> np.ndarray:
        """C(t) = C0 / (1 + k*C0*t)  (ordre 2)"""
        return C0 / (1.0 + k * C0 * t)

    @staticmethod
    def michaelis_menten(S: np.ndarray, Vmax: float, Km: float) -> np.ndarray:
        """v = Vmax*S / (Km + S)  (enzymatique)"""
        return Vmax * S / (Km + S)

    def calibrate(self, t: np.ndarray, C: np.ndarray, order: int) -> dict:
        """Calibre k (et C0) sur des données expérimentales."""
        models = {0: self.order0, 1: self.order1, 2: self.order2}
        if order not in models:
            raise ValueError("order must be 0, 1 or 2")
        func = models[order]
        try:
            popt, pcov = curve_fit(func, t, C, p0=[C[0], 0.01], bounds=(0, np.inf), maxfev=10000)
            C0_fit, k_fit = popt
            C_pred = func(t, C0_fit, k_fit)
            perr = np.sqrt(np.diag(pcov))
            return {
                "order": order,
                "C0": float(C0_fit),
                "k": float(k_fit),
                "std_C0": float(perr[0]),
                "std_k": float(perr[1]),
                "half_life": float(np.log(2) / k_fit) if order == 1 else None,
                "r2": r_squared(C, C_pred),
                "rmse": rmse(C, C_pred),
                "C_pred": C_pred.tolist(),
            }
        except Exception as e:
            return {"error": str(e), "order": order}


# ══════════════════════════════════════════════════════════════════════════════
# 2. BILAN DE MATIÈRE — RÉACTEUR
# ══════════════════════════════════════════════════════════════════════════════

class MaterialBalance:
    """
    Bilan de matière pour un réacteur CSTR ou PFR simplifié.
    dC/dt = F_in*C_in/V - F_out*C/V - r(C)
    """

    def __init__(self, V: float, F_in: float, F_out: float, C_in: float):
        self.V = V          # Volume du réacteur (L)
        self.F_in = F_in    # Débit entrant (L/s)
        self.F_out = F_out  # Débit sortant (L/s)
        self.C_in = C_in    # Concentration entrée (mol/L)

    def _ode(self, t, C, k, order):
        if order == 0:
            r = k
        elif order == 1:
            r = k * C[0]
        elif order == 2:
            r = k * C[0] ** 2
        else:
            r = 0.0
        dC_dt = (self.F_in * self.C_in - self.F_out * C[0]) / self.V - r
        return [dC_dt]

    def simulate(self, t_span: tuple, C0: float, k: float, order: int = 1,
                 n_points: int = 200) -> dict:
        t_eval = np.linspace(t_span[0], t_span[1], n_points)
        sol = solve_ivp(
            self._ode, t_span, [C0], t_eval=t_eval,
            args=(k, order), method="RK45", dense_output=True
        )
        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")
        return {
            "t": sol.t.tolist(),
            "C": sol.y[0].tolist(),
            "V": self.V,
            "F_in": self.F_in,
            "F_out": self.F_out,
            "C_in": self.C_in,
            "k": k,
            "order": order,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 3. DIFFUSION — LOI DE FICK (1D)
# ══════════════════════════════════════════════════════════════════════════════

class FickDiffusion:
    """
    Diffusion 1D par la 2ème loi de Fick : ∂C/∂t = D * ∂²C/∂x²
    Solution analytique pour un domaine semi-infini (C(0,t)=C_s, C(∞,t)=C_0).
    """

    @staticmethod
    def semi_infinite(x: np.ndarray, t: float, D: float, Cs: float, C0: float) -> np.ndarray:
        """C(x,t) = C0 + (Cs-C0)*erfc(x / (2*sqrt(D*t)))"""
        from scipy.special import erfc
        xi = x / (2.0 * np.sqrt(D * t + 1e-30))
        return C0 + (Cs - C0) * erfc(xi)

    @staticmethod
    def membrane_steady(x: np.ndarray, L: float, C1: float, C2: float) -> np.ndarray:
        """Régime permanent : profil linéaire dans une membrane d'épaisseur L."""
        return C1 + (C2 - C1) * x / L

    def simulate_transient(self, L: float, D: float, C_left: float, C_right: float,
                           C_init: float, t_max: float, nx: int = 50, nt: int = 500) -> dict:
        """Simulation numérique différences finies — diffusion 1D transitoire."""
        dx = L / (nx - 1)
        dt = t_max / nt
        # Stabilité CFL
        if D * dt / dx ** 2 > 0.5:
            dt = 0.4 * dx ** 2 / D
            nt = int(t_max / dt) + 1

        x = np.linspace(0, L, nx)
        C = np.full(nx, C_init)
        C[0] = C_left
        C[-1] = C_right

        snapshots = [{"t": 0.0, "C": C.copy().tolist()}]
        r = D * dt / dx ** 2

        for step in range(nt):
            C_new = C.copy()
            C_new[1:-1] = C[1:-1] + r * (C[2:] - 2 * C[1:-1] + C[:-2])
            C_new[0] = C_left
            C_new[-1] = C_right
            C = C_new
            if step % max(1, nt // 20) == 0:
                snapshots.append({"t": round((step + 1) * dt, 6), "C": C.tolist()})

        return {"x": x.tolist(), "snapshots": snapshots, "D": D, "L": L}


# ══════════════════════════════════════════════════════════════════════════════
# 4. TRANSFERT DE CHALEUR
# ══════════════════════════════════════════════════════════════════════════════

class HeatTransfer:
    """Conduction, Newton's loi de refroidissement, bilan thermique."""

    @staticmethod
    def newton_cooling(t: np.ndarray, T0: float, T_inf: float, h_A_rho_cp: float) -> np.ndarray:
        """T(t) = T_inf + (T0-T_inf)*exp(-h*A/(ρ*cp) * t)"""
        return T_inf + (T0 - T_inf) * np.exp(-h_A_rho_cp * t)

    @staticmethod
    def fourier_1d_steady(x: np.ndarray, T_hot: float, T_cold: float, L: float) -> np.ndarray:
        """Profil linéaire de température en conduction 1D stationnaire."""
        return T_hot + (T_cold - T_hot) * x / L

    def calibrate_cooling(self, t: np.ndarray, T: np.ndarray) -> dict:
        T_inf_guess = float(T[-1])
        T0_guess = float(T[0])

        def model(t, T0, T_inf, k):
            return T_inf + (T0 - T_inf) * np.exp(-k * t)

        try:
            popt, pcov = curve_fit(model, t, T, p0=[T0_guess, T_inf_guess, 0.01], maxfev=10000)
            T_pred = model(t, *popt)
            return {
                "T0": float(popt[0]),
                "T_inf": float(popt[1]),
                "k_cooling": float(popt[2]),
                "r2": r_squared(T, T_pred),
                "rmse": rmse(T, T_pred),
                "T_pred": T_pred.tolist(),
            }
        except Exception as e:
            return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 5. ADSORPTION — ISOTHERME
# ══════════════════════════════════════════════════════════════════════════════

class Adsorption:
    """Isothermes d'adsorption : Langmuir, Freundlich."""

    @staticmethod
    def langmuir(Ce: np.ndarray, qm: float, KL: float) -> np.ndarray:
        """qe = qm*KL*Ce / (1 + KL*Ce)"""
        return qm * KL * Ce / (1.0 + KL * Ce)

    @staticmethod
    def freundlich(Ce: np.ndarray, Kf: float, n: float) -> np.ndarray:
        """qe = Kf * Ce^(1/n)"""
        return Kf * np.power(np.abs(Ce), 1.0 / n)

    def calibrate(self, Ce: np.ndarray, qe: np.ndarray, model: str = "langmuir") -> dict:
        models = {"langmuir": self.langmuir, "freundlich": self.freundlich}
        if model not in models:
            raise ValueError(f"Model must be one of {list(models.keys())}")
        func = models[model]
        try:
            p0 = [max(qe), 0.1] if model == "langmuir" else [1.0, 2.0]
            popt, pcov = curve_fit(func, Ce, qe, p0=p0, bounds=(0, np.inf), maxfev=10000)
            qe_pred = func(Ce, *popt)
            perr = np.sqrt(np.diag(pcov))
            params = (
                {"qm": float(popt[0]), "KL": float(popt[1])}
                if model == "langmuir"
                else {"Kf": float(popt[0]), "n": float(popt[1])}
            )
            return {
                "model": model,
                **params,
                "r2": r_squared(qe, qe_pred),
                "rmse": rmse(qe, qe_pred),
                "qe_pred": qe_pred.tolist(),
            }
        except Exception as e:
            return {"error": str(e), "model": model}
