"""
ai/predictor.py
================
Module de prédiction sur nouvelles données.
Supporte tous les modèles (regression sklearn + MLP PyTorch).
Calcule les intervalles de confiance (Random Forest) et les métriques
d'incertitude pour aider à la décision.
"""

from __future__ import annotations
import numpy as np
from typing import List, Dict, Any

from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.metrics import r2_score, mean_squared_error
from scipy import stats
from loguru import logger

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


# ─────────────────────────────────────────────────────────────────────────────
# Builders sklearn
# ─────────────────────────────────────────────────────────────────────────────

def _build_sklearn(model_type: str, degree: int, alpha: float,
                   n_estimators: int) -> Any:
    if model_type == "linear":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  LinearRegression())])
    elif model_type == "polynomial":
        return Pipeline([("poly",   PolynomialFeatures(degree, include_bias=False)),
                         ("scaler", StandardScaler()),
                         ("model",  LinearRegression())])
    elif model_type == "ridge":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  Ridge(alpha=alpha))])
    elif model_type == "lasso":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  Lasso(alpha=alpha, max_iter=10000))])
    elif model_type == "random_forest":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  RandomForestRegressor(n_estimators=n_estimators,
                                                           random_state=42, n_jobs=-1))])
    elif model_type == "svr":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  SVR(kernel="rbf"))])
    elif model_type == "gradient_boosting":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  GradientBoostingRegressor(n_estimators=n_estimators,
                                                               random_state=42))])
    else:
        raise ValueError(f"Modèle inconnu : {model_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Intervalle de confiance Random Forest (méthode des arbres individuels)
# ─────────────────────────────────────────────────────────────────────────────

def _rf_confidence_interval(pipe: Pipeline, X_pred: np.ndarray,
                             alpha: float = 0.05) -> Dict[str, list]:
    """
    Calcule l'intervalle de confiance à (1-alpha)% pour Random Forest
    en utilisant les prédictions de chaque arbre individuellement.
    """
    rf = pipe["model"]
    if not isinstance(rf, RandomForestRegressor):
        return {}
    scaler = pipe["scaler"]
    Xs = scaler.transform(X_pred)
    tree_preds = np.array([tree.predict(Xs) for tree in rf.estimators_])  # (n_trees, n_samples)
    mean  = tree_preds.mean(axis=0)
    std   = tree_preds.std(axis=0)
    z     = stats.norm.ppf(1 - alpha / 2)
    lower = mean - z * std
    upper = mean + z * std
    return {
        "ci_lower":    lower.tolist(),
        "ci_upper":    upper.tolist(),
        "ci_std":      std.tolist(),
        "ci_level":    f"{int((1-alpha)*100)}%",
    }


# ─────────────────────────────────────────────────────────────────────────────
# MLP PyTorch simplifié pour prédiction rapide
# ─────────────────────────────────────────────────────────────────────────────

class _MLP(nn.Module):
    def __init__(self, in_f, hidden, out_f=1):
        super().__init__()
        layers, prev = [], in_f
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU()]
            prev = h
        layers.append(nn.Linear(prev, out_f))
        self.net = nn.Sequential(*layers)
    def forward(self, x): return self.net(x)


def _train_and_predict_mlp(X_train: np.ndarray, y_train: np.ndarray,
                            X_pred: np.ndarray, hidden_layers: List[int],
                            epochs: int) -> Dict[str, Any]:
    sx, sy = StandardScaler(), StandardScaler()
    Xts = sx.fit_transform(X_train).astype(np.float32)
    yts = sy.fit_transform(y_train.reshape(-1,1)).flatten().astype(np.float32)
    Xps = sx.transform(X_pred).astype(np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model  = _MLP(Xts.shape[1], hidden_layers).to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    crit   = nn.MSELoss()

    ds = TensorDataset(torch.tensor(Xts), torch.tensor(yts))
    dl = DataLoader(ds, batch_size=min(32, len(ds)), shuffle=True)

    history = []
    for ep in range(epochs):
        model.train(); loss_ep = 0
        for xb, yb in dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(); l = crit(model(xb).squeeze(), yb)
            l.backward(); opt.step(); loss_ep += l.item()
        if ep % max(1, epochs // 10) == 0:
            history.append(round(loss_ep / len(dl), 6))

    model.eval()
    Xt_t = torch.tensor(Xts).to(device)
    Xp_t = torch.tensor(Xps).to(device)
    with torch.no_grad():
        y_train_pred_s = model(Xt_t).squeeze().cpu().numpy()
        y_pred_s       = model(Xp_t).squeeze().cpu().numpy()

    y_train_pred = sy.inverse_transform(y_train_pred_s.reshape(-1,1)).flatten()
    y_pred       = sy.inverse_transform(y_pred_s.reshape(-1,1)).flatten()

    r2   = float(r2_score(y_train, y_train_pred))
    rmse = float(np.sqrt(mean_squared_error(y_train, y_train_pred)))

    return {
        "train_r2":      round(r2, 6),
        "train_rmse":    round(rmse, 6),
        "predictions":   y_pred.tolist(),
        "train_history": history,
        "device":        str(device),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def predict_new(
    X_train:      List[List[float]],
    y_train:      List[float],
    X_predict:    List[List[float]],
    model_type:   str   = "random_forest",
    degree:       int   = 3,
    alpha:        float = 1.0,
    n_estimators: int   = 100,
    hidden_layers: List[int] = None,
    epochs:       int   = 150,
    confidence_interval: bool = True,
) -> Dict[str, Any]:
    """
    Entraîne un modèle sur (X_train, y_train) et prédit sur X_predict.
    Retourne les prédictions, métriques et intervalles de confiance (RF).
    """
    if hidden_layers is None:
        hidden_layers = [64, 32, 16]

    logger.info(f"predict_new  model={model_type}  "
                f"train={len(X_train)}  predict={len(X_predict)}")

    Xtr = np.array(X_train, dtype=float)
    ytr = np.array(y_train,  dtype=float)
    Xpr = np.array(X_predict, dtype=float)

    # ── MLP PyTorch ───────────────────────────────────────────────────────────
    if model_type == "mlp":
        result = _train_and_predict_mlp(Xtr, ytr, Xpr, hidden_layers, epochs)
        return {
            "model_type":   "mlp",
            "n_train":      len(Xtr),
            "n_predict":    len(Xpr),
            "predictions":  result["predictions"],
            "train_r2":     result["train_r2"],
            "train_rmse":   result["train_rmse"],
            "training_history": result["train_history"],
            "device":       result["device"],
            "X_predict":    Xpr.flatten().tolist(),
        }

    # ── Modèles sklearn ───────────────────────────────────────────────────────
    pipe = _build_sklearn(model_type, degree, alpha, n_estimators)
    pipe.fit(Xtr, ytr)

    y_train_pred = pipe.predict(Xtr)
    y_pred       = pipe.predict(Xpr)

    r2   = float(r2_score(ytr, y_train_pred))
    rmse = float(np.sqrt(mean_squared_error(ytr, y_train_pred)))

    result: Dict[str, Any] = {
        "model_type":  model_type,
        "n_train":     int(len(Xtr)),
        "n_predict":   int(len(Xpr)),
        "predictions": y_pred.tolist(),
        "train_r2":    round(r2, 6),
        "train_rmse":  round(rmse, 6),
        "X_predict":   Xpr.flatten().tolist(),
        # Statistiques sur les prédictions
        "pred_stats": {
            "mean":  round(float(np.mean(y_pred)), 6),
            "std":   round(float(np.std(y_pred)), 6),
            "min":   round(float(np.min(y_pred)), 6),
            "max":   round(float(np.max(y_pred)), 6),
        },
    }

    # Intervalle de confiance (Random Forest uniquement)
    if confidence_interval and model_type == "random_forest":
        ci = _rf_confidence_interval(pipe, Xpr)
        result.update(ci)

    # Feature importances (RF / GBM)
    m = pipe["model"]
    if hasattr(m, "feature_importances_"):
        result["feature_importances"] = m.feature_importances_.tolist()

    return result
