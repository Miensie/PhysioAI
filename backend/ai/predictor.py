"""
ai/predictor.py
================
Prédiction sur nouvelles données — supporte les 10 modèles :
  Régression analytique (curve_fit) :
    linear, logarithmic, exponential, power
  Régression sklearn :
    polynomial, ridge, lasso
  Machine Learning :
    random_forest, svr, gradient_boosting
  Deep Learning :
    mlp (PyTorch)

Pour chaque modèle, retourne : prédictions, R² entraînement, RMSE,
intervalles de confiance (RF), statistiques des prédictions.
"""

from __future__ import annotations
import numpy as np
from typing import List, Dict, Any, Optional

from scipy.optimize import curve_fit
from scipy import stats
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.metrics import r2_score, mean_squared_error
from loguru import logger

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions analytiques (curve_fit)
# ─────────────────────────────────────────────────────────────────────────────

def _fn_linear(x, a, b):
    return a * x + b

def _fn_log(x, a, b):
    return a * np.log(np.abs(x) + 1e-9) + b

def _fn_exp(x, a, b, c):
    return a * np.exp(b * x) + c

def _fn_power(x, a, b):
    return a * np.power(np.abs(x) + 1e-9, b)


def _fit_analytical(model_type: str,
                    x_train: np.ndarray, y_train: np.ndarray,
                    x_pred:  np.ndarray) -> Dict[str, Any]:
    """
    Ajuste un modèle analytique par curve_fit et prédit.
    Retourne params, équation, R², RMSE, prédictions.
    """
    fns  = {
        "linear":      (_fn_linear,  [1.0, 0.0]),
        "logarithmic": (_fn_log,     [1.0, 0.0]),
        "exponential": (_fn_exp,     [1.0, 0.01, 0.0]),
        "power":       (_fn_power,   [1.0, 1.0]),
    }
    fn, p0 = fns[model_type]

    popt, pcov = curve_fit(fn, x_train, y_train, p0=p0, maxfev=50000)
    perr       = np.sqrt(np.diag(pcov))

    y_train_pred = fn(x_train, *popt)
    y_pred       = fn(x_pred,  *popt)

    r2   = float(r2_score(y_train, y_train_pred))
    rmse = float(np.sqrt(mean_squared_error(y_train, y_train_pred)))

    # Equation lisible
    if model_type == "linear":
        eq = f"y = {popt[0]:.6f}·x + {popt[1]:.6f}"
        params = {"a": popt[0], "b": popt[1]}
    elif model_type == "logarithmic":
        eq = f"y = {popt[0]:.6f}·ln(x) + {popt[1]:.6f}"
        params = {"a": popt[0], "b": popt[1]}
    elif model_type == "exponential":
        eq = f"y = {popt[0]:.6f}·exp({popt[1]:.6f}·x) + {popt[2]:.6f}"
        params = {"a": popt[0], "b": popt[1], "c": popt[2]}
    else:  # power
        eq = f"y = {popt[0]:.6f}·x^{popt[1]:.6f}"
        params = {"a": popt[0], "b": popt[1]}

    return {
        "model_type":  model_type,
        "equation":    eq,
        "params":      {k: round(float(v), 8) for k, v in params.items()},
        "param_std":   {f"std_{i}": round(float(e), 8) for i, e in enumerate(perr)},
        "train_r2":    round(r2, 6),
        "train_rmse":  round(rmse, 6),
        "predictions": y_pred.tolist(),
        "n_train":     int(len(x_train)),
        "n_predict":   int(len(x_pred)),
        "X_predict":   x_pred.tolist(),
        "pred_stats": {
            "mean": round(float(np.mean(y_pred)), 6),
            "std":  round(float(np.std(y_pred)),  6),
            "min":  round(float(np.min(y_pred)),  6),
            "max":  round(float(np.max(y_pred)),  6),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Builders sklearn
# ─────────────────────────────────────────────────────────────────────────────

def _build_sklearn(model_type: str, degree: int, alpha: float,
                   n_estimators: int) -> Any:
    if model_type == "polynomial":
        return Pipeline([
            ("poly",   PolynomialFeatures(degree, include_bias=False)),
            ("scaler", StandardScaler()),
            ("model",  LinearRegression()),
        ])
    elif model_type == "ridge":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  Ridge(alpha=alpha))])
    elif model_type == "lasso":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  Lasso(alpha=alpha, max_iter=10000))])
    elif model_type == "random_forest":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  RandomForestRegressor(
                             n_estimators=n_estimators, random_state=42, n_jobs=-1))])
    elif model_type == "svr":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  SVR(kernel="rbf"))])
    elif model_type == "gradient_boosting":
        return Pipeline([("scaler", StandardScaler()),
                         ("model",  GradientBoostingRegressor(
                             n_estimators=n_estimators, random_state=42))])
    else:
        raise ValueError(f"Modèle sklearn inconnu : {model_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Intervalle de confiance — Random Forest
# ─────────────────────────────────────────────────────────────────────────────

def _rf_confidence_interval(pipe: Pipeline, X_pred: np.ndarray,
                             alpha: float = 0.05) -> Dict[str, list]:
    rf = pipe["model"]
    if not isinstance(rf, RandomForestRegressor):
        return {}
    Xs    = pipe["scaler"].transform(X_pred)
    preds = np.array([tree.predict(Xs) for tree in rf.estimators_])
    mean  = preds.mean(axis=0)
    std   = preds.std(axis=0)
    z     = stats.norm.ppf(1 - alpha / 2)
    return {
        "ci_lower": (mean - z * std).tolist(),
        "ci_upper": (mean + z * std).tolist(),
        "ci_std":   std.tolist(),
        "ci_level": f"{int((1-alpha)*100)}%",
    }


# ─────────────────────────────────────────────────────────────────────────────
# MLP PyTorch
# ─────────────────────────────────────────────────────────────────────────────

class _MLP(nn.Module):
    def __init__(self, in_f, hidden, out_f=1):
        super().__init__()
        layers, prev = [], in_f
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(0.1)]
            prev = h
        layers.append(nn.Linear(prev, out_f))
        self.net = nn.Sequential(*layers)
    def forward(self, x): return self.net(x)


def _train_and_predict_mlp(X_train, y_train, X_pred,
                            hidden_layers, epochs) -> Dict[str, Any]:
    sx, sy = StandardScaler(), StandardScaler()
    Xts = sx.fit_transform(X_train).astype(np.float32)
    yts = sy.fit_transform(y_train.reshape(-1,1)).flatten().astype(np.float32)
    Xps = sx.transform(X_pred).astype(np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model  = _MLP(Xts.shape[1], hidden_layers).to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched  = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=20, factor=0.5)
    crit   = nn.MSELoss()

    ds = TensorDataset(torch.tensor(Xts), torch.tensor(yts))
    dl = DataLoader(ds, batch_size=min(32, len(ds)), shuffle=True)
    history = []

    for ep in range(epochs):
        model.train(); ep_loss = 0
        for xb, yb in dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            l = crit(model(xb).squeeze(), yb)
            l.backward(); opt.step(); ep_loss += l.item()
        avg = ep_loss / len(dl)
        sched.step(avg)
        if ep % max(1, epochs // 10) == 0:
            history.append(round(avg, 6))

    model.eval()
    with torch.no_grad():
        ytr_s = model(torch.tensor(Xts).to(device)).squeeze().cpu().numpy()
        ypr_s = model(torch.tensor(Xps).to(device)).squeeze().cpu().numpy()

    y_train_pred = sy.inverse_transform(ytr_s.reshape(-1,1)).flatten()
    y_pred       = sy.inverse_transform(ypr_s.reshape(-1,1)).flatten()

    return {
        "model_type":  "mlp",
        "train_r2":    round(float(r2_score(y_train, y_train_pred)), 6),
        "train_rmse":  round(float(np.sqrt(mean_squared_error(y_train, y_train_pred))), 6),
        "predictions": y_pred.tolist(),
        "n_train":     int(len(X_train)),
        "n_predict":   int(len(X_pred)),
        "X_predict":   X_pred.flatten().tolist(),
        "training_history": history,
        "device":      str(device),
        "pred_stats": {
            "mean": round(float(np.mean(y_pred)), 6),
            "std":  round(float(np.std(y_pred)),  6),
            "min":  round(float(np.min(y_pred)),  6),
            "max":  round(float(np.max(y_pred)),  6),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

ANALYTICAL_MODELS = {"linear", "logarithmic", "exponential", "power"}
SKLEARN_MODELS    = {"polynomial", "ridge", "lasso",
                     "random_forest", "svr", "gradient_boosting"}

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
    if hidden_layers is None:
        hidden_layers = [64, 32, 16]

    logger.info(f"predict_new  model={model_type}  "
                f"train={len(X_train)}  predict={len(X_predict)}")

    Xtr = np.array(X_train,   dtype=float)
    ytr = np.array(y_train,    dtype=float)
    Xpr = np.array(X_predict,  dtype=float)

    # ── Modèles analytiques ───────────────────────────────────────────────────
    if model_type in ANALYTICAL_MODELS:
        x1d_tr = Xtr.flatten()
        x1d_pr = Xpr.flatten()
        return _fit_analytical(model_type, x1d_tr, ytr, x1d_pr)

    # ── MLP PyTorch ───────────────────────────────────────────────────────────
    if model_type == "mlp":
        return _train_and_predict_mlp(Xtr, ytr, Xpr, hidden_layers, epochs)

    # ── Modèles sklearn ───────────────────────────────────────────────────────
    if model_type in SKLEARN_MODELS:
        pipe = _build_sklearn(model_type, degree, alpha, n_estimators)
        pipe.fit(Xtr, ytr)

        y_train_pred = pipe.predict(Xtr)
        y_pred       = pipe.predict(Xpr)

        result: Dict[str, Any] = {
            "model_type":  model_type,
            "train_r2":    round(float(r2_score(ytr, y_train_pred)), 6),
            "train_rmse":  round(float(np.sqrt(mean_squared_error(ytr, y_train_pred))), 6),
            "predictions": y_pred.tolist(),
            "n_train":     int(len(Xtr)),
            "n_predict":   int(len(Xpr)),
            "X_predict":   Xpr.flatten().tolist(),
            "pred_stats": {
                "mean": round(float(np.mean(y_pred)), 6),
                "std":  round(float(np.std(y_pred)),  6),
                "min":  round(float(np.min(y_pred)),  6),
                "max":  round(float(np.max(y_pred)),  6),
            },
        }

        if confidence_interval and model_type == "random_forest":
            result.update(_rf_confidence_interval(pipe, Xpr))

        m = pipe["model"]
        if hasattr(m, "feature_importances_"):
            result["feature_importances"] = m.feature_importances_.tolist()

        if model_type == "polynomial":
            result["degree"] = degree
        elif model_type in ("ridge", "lasso"):
            result["alpha"] = alpha

        return result

    raise ValueError(
        f"Modèle '{model_type}' inconnu. Valides : "
        + ", ".join(sorted(ANALYTICAL_MODELS | SKLEARN_MODELS | {"mlp"}))
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMPARAISON AUTOMATIQUE — tous les modèles
# ─────────────────────────────────────────────────────────────────────────────

def predict_best(
    X_train:   List[List[float]],
    y_train:   List[float],
    X_predict: List[List[float]],
    degree:    int   = 3,
    alpha:     float = 1.0,
) -> Dict[str, Any]:
    """
    Lance tous les modèles de régression (analytiques + sklearn),
    retourne le meilleur par R² + le comparatif complet.
    """
    logger.info(f"predict_best — comparaison tous modèles  n={len(X_train)}")

    candidates = [
        ("linear",       {}),
        ("logarithmic",  {}),
        ("exponential",  {}),
        ("power",        {}),
        ("polynomial",   {"degree": degree}),
        ("ridge",        {"alpha": alpha}),
        ("lasso",        {"alpha": alpha}),
        ("random_forest",{"n_estimators": 100}),
        ("svr",          {}),
        ("gradient_boosting", {"n_estimators": 100}),
    ]

    results = {}
    for model_type, extra in candidates:
        try:
            r = predict_new(
                X_train, y_train, X_predict,
                model_type=model_type,
                degree=degree, alpha=alpha,
                **extra,
            )
            results[model_type] = r
        except Exception as e:
            logger.warning(f"Modèle {model_type} échoué: {e}")
            results[model_type] = {"error": str(e), "train_r2": -999}

    # Classement par R² décroissant
    ranking = sorted(
        [(k, v.get("train_r2", -999)) for k, v in results.items()],
        key=lambda x: x[1], reverse=True
    )
    best_model = ranking[0][0]

    return {
        "best_model":   best_model,
        "best_r2":      results[best_model].get("train_r2"),
        "best_result":  results[best_model],
        "ranking":      [{"model": k, "train_r2": r} for k, r in ranking],
        "all_results":  results,
    }