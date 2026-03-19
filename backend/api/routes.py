"""
PhysioAI Lab — API Routes
Endpoints: /analyze, /model, /simulate, /train_ai, /predict, /optimize
"""

from __future__ import annotations
import logging
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional

from modeling.regression import RegressionEngine
from modeling.physical import (
    ChemicalKinetics, MaterialBalance, FickDiffusion, HeatTransfer, Adsorption
)
from ai.ml_models import MLEngine, ClusteringEngine, DeepLearningEngine, HybridModel
from ai.ai_advisor import AIAdvisor
from optimization.optimizer import ParameterOptimizer
from utils.data_utils import to_numpy, descriptive_stats, r_squared

logger = logging.getLogger("physioai")
router = APIRouter()

# ─── Moteurs singleton ────────────────────────────────────────────────────────
_regression = RegressionEngine()
_ml_engine = MLEngine()
_dl_engine = DeepLearningEngine()
_advisor = AIAdvisor()
_optimizer = ParameterOptimizer()


# ══════════════════════════════════════════════════════════════════════════════
# Schémas Pydantic
# ══════════════════════════════════════════════════════════════════════════════

class DataPayload(BaseModel):
    x: list[float] = Field(..., description="Variable indépendante", min_length=2)
    y: list[float] = Field(..., description="Variable dépendante", min_length=2)

class RegressionRequest(BaseModel):
    x: list[float]
    y: list[float]
    model_type: str = "linear"
    degree: Optional[int] = 3
    alpha: Optional[float] = 1.0

class PhysicalModelRequest(BaseModel):
    model: str = Field(..., description="kinetics_order1 | material_balance | diffusion_fick | heat_transfer | adsorption_langmuir")
    x: list[float]
    y: list[float]
    params: Optional[dict[str, Any]] = {}

class SimulationRequest(BaseModel):
    model: str
    params: dict[str, Any]
    t_start: float = 0.0
    t_end: float = 100.0
    n_points: int = Field(200, ge=10, le=2000)

class TrainAIRequest(BaseModel):
    x: list[float]
    y: list[float]
    model_type: str = "random_forest"
    epochs: int = Field(200, ge=10, le=2000)
    hidden_dims: Optional[list[int]] = None
    n_estimators: Optional[int] = 100

class PredictRequest(BaseModel):
    x: list[float]
    model_type: str = "neural_network"

class OptimizeRequest(BaseModel):
    x: list[float]
    y: list[float]
    physical_model: str
    method: str = "least_squares"
    bounds: Optional[list[list[float]]] = None
    p0: Optional[list[float]] = None


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /analyze
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze", tags=["Analysis"])
async def analyze(payload: DataPayload):
    """
    Analyse les données : statistiques descriptives, corrélation,
    détection de linéarité/bruit/outliers + recommandations IA.
    """
    try:
        x, y = np.array(payload.x), np.array(payload.y)
        if len(x) != len(y):
            raise HTTPException(400, "x et y doivent avoir la même longueur.")

        report = _advisor.analyze(x, y)
        report["x_stats"] = descriptive_stats(x)
        report["y_stats"] = descriptive_stats(y)

        # Ajout de la régression sur tous les modèles
        try:
            all_regressions = _regression.fit_all(x, y)
            report["regression_comparison"] = [
                {"model": r.get("model"), "r2": r.get("r2"), "rmse": r.get("rmse")}
                for r in all_regressions if "r2" in r
            ]
        except Exception as e:
            report["regression_comparison"] = []
            logger.warning(f"Regression comparison failed: {e}")

        return {"status": "ok", "analysis": report}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/analyze error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /model
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/model", tags=["Modeling"])
async def model_fit(payload: RegressionRequest):
    """
    Ajuste un modèle de régression (linéaire, log, exp, puissance, poly, ridge, lasso).
    """
    try:
        x, y = np.array(payload.x), np.array(payload.y)
        kwargs = {}
        if payload.degree:
            kwargs["degree"] = payload.degree
        if payload.alpha:
            kwargs["alpha"] = payload.alpha
        result = _regression.fit(x, y, payload.model_type, **kwargs)
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"/model error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/model/physical", tags=["Modeling"])
async def model_physical(payload: PhysicalModelRequest):
    """
    Calibre un modèle physique sur des données expérimentales.
    Modèles: kinetics_order0/1/2, material_balance, diffusion_fick,
             heat_transfer, adsorption_langmuir/freundlich
    """
    try:
        x, y = np.array(payload.x), np.array(payload.y)
        p = payload.params or {}
        m = payload.model

        if m.startswith("kinetics_order"):
            order = int(m[-1])
            result = ChemicalKinetics().calibrate(x, y, order)

        elif m == "material_balance":
            mb = MaterialBalance(
                V=p.get("V", 10.0), F_in=p.get("F_in", 1.0),
                F_out=p.get("F_out", 1.0), C_in=p.get("C_in", 1.0)
            )
            result = mb.simulate((float(x[0]), float(x[-1])), float(y[0]),
                                  k=p.get("k", 0.01), order=p.get("order", 1))

        elif m == "diffusion_fick":
            fd = FickDiffusion()
            # Calibration: ajuster D sur un profil spatial C(x)
            def fick_model(xi, D):
                return fd.semi_infinite(xi, p.get("t", 1.0),
                                        D, p.get("Cs", float(y[0])),
                                        p.get("C0", float(y[-1])))
            from scipy.optimize import curve_fit
            popt, pcov = curve_fit(fick_model, x, y, p0=[1e-9], bounds=(1e-15, 1.0), maxfev=10000)
            y_pred = fick_model(x, *popt)
            result = {"D": float(popt[0]), "r2": r_squared(y, y_pred), "y_pred": y_pred.tolist()}

        elif m == "heat_transfer":
            result = HeatTransfer().calibrate_cooling(x, y)

        elif m.startswith("adsorption_"):
            isotherm = m.split("_")[1]  # langmuir or freundlich
            result = Adsorption().calibrate(x, y, isotherm)

        else:
            raise HTTPException(400, f"Modèle physique inconnu: {m}")

        return {"status": "ok", "model": m, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/model/physical error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /simulate
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/simulate", tags=["Simulation"])
async def simulate(payload: SimulationRequest):
    """
    Lance une simulation temporelle d'un phénomène physique.
    """
    try:
        p = payload.params
        t_span = (payload.t_start, payload.t_end)
        n = payload.n_points
        t_eval = np.linspace(*t_span, n).tolist()

        if payload.model == "kinetics_order1":
            C0, k = p.get("C0", 1.0), p.get("k", 0.05)
            C = (C0 * np.exp(-k * np.array(t_eval))).tolist()
            return {"status": "ok", "t": t_eval, "C": C, "model": "kinetics_order1", "C0": C0, "k": k}

        elif payload.model == "kinetics_order2":
            C0, k = p.get("C0", 1.0), p.get("k", 0.1)
            t_arr = np.array(t_eval)
            C = (C0 / (1.0 + k * C0 * t_arr)).tolist()
            return {"status": "ok", "t": t_eval, "C": C, "model": "kinetics_order2"}

        elif payload.model == "material_balance":
            mb = MaterialBalance(
                V=p.get("V", 10.0), F_in=p.get("F_in", 1.0),
                F_out=p.get("F_out", 1.0), C_in=p.get("C_in", 1.0)
            )
            result = mb.simulate(t_span, p.get("C0", 0.0),
                                  k=p.get("k", 0.01), order=p.get("order", 1), n_points=n)
            return {"status": "ok", **result}

        elif payload.model == "diffusion_fick_transient":
            fd = FickDiffusion()
            result = fd.simulate_transient(
                L=p.get("L", 1.0), D=p.get("D", 1e-9),
                C_left=p.get("C_left", 1.0), C_right=p.get("C_right", 0.0),
                C_init=p.get("C_init", 0.0), t_max=payload.t_end, nx=50, nt=n
            )
            return {"status": "ok", **result}

        elif payload.model == "heat_cooling":
            T0, T_inf, k = p.get("T0", 100.0), p.get("T_inf", 20.0), p.get("k", 0.05)
            T = HeatTransfer.newton_cooling(np.array(t_eval), T0, T_inf, k).tolist()
            return {"status": "ok", "t": t_eval, "T": T, "model": "heat_cooling"}

        else:
            raise HTTPException(400, f"Modèle de simulation inconnu: {payload.model}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/simulate error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /train_ai
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/train_ai", tags=["AI / ML"])
async def train_ai(payload: TrainAIRequest):
    """
    Entraîne un modèle ML ou Deep Learning.
    model_type: random_forest | gradient_boosting | svr | neural_network
    """
    try:
        x, y = np.array(payload.x), np.array(payload.y)

        if payload.model_type == "neural_network":
            result = _dl_engine.train(
                x, y,
                epochs=payload.epochs,
                hidden_dims=payload.hidden_dims,
            )
        else:
            result = _ml_engine.train(
                x, y,
                model_type=payload.model_type,
                n_estimators=payload.n_estimators or 100,
            )

        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"/train_ai error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /predict
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/predict", tags=["AI / ML"])
async def predict(payload: PredictRequest):
    """
    Génère des prédictions avec le dernier modèle entraîné.
    """
    try:
        x = np.array(payload.x)
        if payload.model_type == "neural_network":
            y_pred = _dl_engine.predict(x)
        else:
            y_pred = _ml_engine.predict(x)
        return {"status": "ok", "x": payload.x, "y_pred": y_pred.tolist()}
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"/predict error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /optimize
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/optimize", tags=["Optimization"])
async def optimize(payload: OptimizeRequest):
    """
    Optimise les paramètres d'un modèle physique sur des données.
    """
    try:
        x, y = np.array(payload.x), np.array(payload.y)
        bounds_list = [tuple(b) for b in payload.bounds] if payload.bounds else None

        MODELS = {
            "order1": (lambda t, C0, k: C0 * np.exp(-k * t), ["C0", "k"]),
            "order2": (lambda t, C0, k: C0 / (1 + k * C0 * t), ["C0", "k"]),
            "langmuir": (lambda Ce, qm, KL: qm * KL * Ce / (1 + KL * Ce), ["qm", "KL"]),
            "exponential": (lambda t, a, b: a * np.exp(b * t), ["a", "b"]),
            "power": (lambda x, a, b: a * np.abs(x) ** b, ["a", "b"]),
        }
        if payload.physical_model not in MODELS:
            raise HTTPException(400, f"Modèle inconnu: {payload.physical_model}. Choix: {list(MODELS.keys())}")

        func, param_names = MODELS[payload.physical_model]
        result = _optimizer.optimize(
            func, x, y, param_names,
            bounds=bounds_list,
            method=payload.method,
            p0=payload.p0,
        )
        return {"status": "ok", "model": payload.physical_model, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/optimize error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT /report
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/report", tags=["Report"])
async def generate_report(payload: DataPayload):
    """
    Génère un rapport complet : analyse + meilleur modèle + prédictions.
    """
    try:
        x, y = np.array(payload.x), np.array(payload.y)

        # Analyse
        analysis = _advisor.analyze(x, y)

        # Toutes les régressions
        all_regressions = _regression.fit_all(x, y)
        best = all_regressions[0] if all_regressions else {}

        # ML si données suffisantes
        ml_result = None
        if len(x) >= 20:
            try:
                ml_result = _ml_engine.train(x, y, model_type="random_forest")
            except Exception:
                pass

        report = {
            "summary": {
                "n_points": len(x),
                "best_regression_model": best.get("model"),
                "best_r2": best.get("r2"),
                "data_quality": analysis["recommendations"]["data_quality"],
                "primary_recommendation": analysis["recommendations"]["primary_recommendation"],
            },
            "analysis": analysis,
            "regression_results": all_regressions[:3],
            "ml_result": ml_result,
            "warnings": analysis["recommendations"]["warnings"],
        }

        return {"status": "ok", "report": report}
    except Exception as e:
        logger.error(f"/report error: {e}", exc_info=True)
        raise HTTPException(500, str(e))
