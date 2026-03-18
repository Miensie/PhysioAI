"""api/routes_predict.py — Endpoints /predict"""

import logging
from typing import Optional
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sklearn.preprocessing import StandardScaler

router = APIRouter()
logger = logging.getLogger("physioai.api.predict")

# ── Store en mémoire des modèles entraînés ────────────────────────────────────
# En production : remplacer par Redis ou base de données
_MODEL_STORE: dict = {}


class StoreModelRequest(BaseModel):
    model_id:   str
    model_type: str       # "linear" | "polynomial" | "mlp" | "rf" | "physics"
    model_data: dict      # paramètres sérialisés


class PredictRequest(BaseModel):
    X_new:      list[list[float]]
    model_id:   Optional[str]  = None
    model_type: Optional[str]  = None
    # Pour régression linéaire inline (sans model_id)
    slope:      Optional[float] = None
    intercept:  Optional[float] = None
    # Pour polynomial
    coeffs:     Optional[list[float]] = None
    degree:     Optional[int]  = None
    # Pour cinétique
    C0:         Optional[float] = None
    k:          Optional[float] = None
    order:      Optional[int]   = None
    # Scalers (pour ML/DL)
    scaler_X:   Optional[dict]  = None
    scaler_y:   Optional[dict]  = None


@router.post("/store", summary="Sauvegarder un modèle")
async def store_model(req: StoreModelRequest):
    """Sauvegarde les paramètres d'un modèle entraîné en mémoire."""
    _MODEL_STORE[req.model_id] = {"type": req.model_type, **req.model_data}
    logger.info(f"Modèle '{req.model_id}' ({req.model_type}) sauvegardé.")
    return {"status": "ok", "model_id": req.model_id}


@router.post("/", summary="Prédiction sur nouvelles données")
async def predict(req: PredictRequest):
    """
    Prédiction sur nouvelles données X_new.
    Supporte : régression linéaire/polynomiale, cinétique, ML, Deep Learning.
    """
    try:
        X_new = np.asarray(req.X_new, dtype=np.float64)
        if X_new.ndim == 1:
            X_new = X_new.reshape(-1, 1)

        model_type = req.model_type

        # ── Charger depuis le store si model_id fourni ────────────────
        if req.model_id and req.model_id in _MODEL_STORE:
            stored = _MODEL_STORE[req.model_id]
            model_type = stored["type"]
            # Reconstruire les paramètres depuis le store
            if model_type == "linear":
                req.slope     = stored.get("slope")
                req.intercept = stored.get("intercept")
            elif model_type == "polynomial":
                req.coeffs = stored.get("coeffs")
                req.degree = stored.get("degree")

        # ── Régression linéaire ───────────────────────────────────────
        if model_type == "linear":
            if req.slope is None or req.intercept is None:
                raise ValueError("slope et intercept requis pour la prédiction linéaire.")
            y_pred = (req.slope * X_new[:, 0] + req.intercept).tolist()

        # ── Régression polynomiale ────────────────────────────────────
        elif model_type == "polynomial":
            if req.coeffs is None:
                raise ValueError("coeffs requis pour la prédiction polynomiale.")
            x = X_new[:, 0]
            deg = req.degree or (len(req.coeffs) - 1)
            # Reconstruire polynomial features
            from sklearn.preprocessing import PolynomialFeatures, StandardScaler
            from sklearn.pipeline import Pipeline
            from sklearn.linear_model import LinearRegression
            # Prédiction directe via numpy polyval
            y_pred = np.polyval(req.coeffs[::-1], x).tolist()

        # ── Cinétique ─────────────────────────────────────────────────
        elif model_type in ("kinetics", "kinetics_order0", "kinetics_order1", "kinetics_order2"):
            from modeling.physical_models import (
                kinetics_order0, kinetics_order1, kinetics_order2
            )
            t   = X_new[:, 0]
            C0  = req.C0 or 1.0
            k   = req.k  or 0.1
            ord_ = req.order or 1
            fn_map = {0: kinetics_order0, 1: kinetics_order1, 2: kinetics_order2}
            y_pred = fn_map.get(ord_, kinetics_order1)(t, C0, k).tolist()

        # ── Refroidissement de Newton ──────────────────────────────────
        elif model_type == "cooling":
            from modeling.physical_models import newton_cooling
            t     = X_new[:, 0]
            T0    = req.C0 or 100.0
            T_env = req.intercept or 20.0
            h     = req.k or 0.05
            y_pred = newton_cooling(t, T0, T_env, h).tolist()

        # ── MLP PyTorch (depuis state_dict stocké) ────────────────────
        elif model_type in ("mlp", "resnet"):
            if req.model_id not in _MODEL_STORE:
                raise ValueError(f"Modèle '{req.model_id}' non trouvé dans le store.")
            stored   = _MODEL_STORE[req.model_id]
            sc_X     = req.scaler_X or stored.get("scaler_X")
            sc_y     = req.scaler_y or stored.get("scaler_y")

            if sc_X and sc_y:
                import torch
                from ai.deep_learning import MLP, ResNet, DEVICE

                # Reconstruire le scaler
                sc_X_obj = StandardScaler()
                sc_X_obj.mean_  = np.array(sc_X["mean"])
                sc_X_obj.scale_ = np.array(sc_X["std"])

                sc_y_obj = StandardScaler()
                sc_y_obj.mean_  = np.array(sc_y["mean"])
                sc_y_obj.scale_ = np.array(sc_y["std"])

                X_s = sc_X_obj.transform(X_new).astype(np.float32)
                X_t = torch.tensor(X_s).to(DEVICE)

                # Reconstruire le modèle
                arch = stored.get("architecture", [64, 32])
                if model_type == "resnet":
                    model = ResNet(X_new.shape[1], arch[0], len(arch)).to(DEVICE)
                else:
                    model = MLP(X_new.shape[1], arch, 1).to(DEVICE)

                # Charger les poids
                state = stored.get("model_state", {})
                if state:
                    import io
                    state_np = {k: torch.tensor(v) for k, v in state.items()}
                    model.load_state_dict(state_np)

                model.eval()
                with torch.no_grad():
                    y_s = model(X_t).cpu().numpy().ravel()
                y_pred = sc_y_obj.inverse_transform(y_s.reshape(-1, 1)).ravel().tolist()
            else:
                raise ValueError("Scalers manquants pour la prédiction MLP.")

        else:
            raise ValueError(f"Type de modèle inconnu : '{model_type}'")

        logger.info(f"Prédiction {model_type} sur {len(X_new)} points")

        return {
            "status":     "ok",
            "model_type": model_type,
            "n_points":   len(X_new),
            "X_new":      X_new.tolist(),
            "y_pred":     y_pred,
        }

    except Exception as e:
        logger.error(f"/predict : {e}")
        raise HTTPException(400, str(e))


@router.get("/models", summary="Liste des modèles sauvegardés")
async def list_models():
    return {
        "models": [
            {"id": k, "type": v.get("type"), "keys": list(v.keys())}
            for k, v in _MODEL_STORE.items()
        ]
    }
