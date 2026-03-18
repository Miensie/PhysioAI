"""api/routes_train.py — Endpoints /train_ai"""

import logging
from fastapi import APIRouter, HTTPException
from api.schemas import MLRequest, DLRequest
from ai.ml_models import (
    random_forest_regression, svr_regression,
    gradient_boosting, kmeans_clustering, dbscan_clustering,
)
from ai.deep_learning import train_mlp, train_hybrid_model
import numpy as np

router = APIRouter()
logger = logging.getLogger("physioai.api.train")


@router.post("/ml", summary="Entraînement Machine Learning")
async def train_ml(req: MLRequest):
    """Entraîne un modèle ML : Random Forest, SVR, Gradient Boosting, K-Means, DBSCAN."""
    try:
        m = req.model.value
        if m == "random_forest":
            res = random_forest_regression(req.X, req.y, req.n_estimators, req.max_depth, req.cv_folds)
        elif m == "svr":
            res = svr_regression(req.X, req.y, req.kernel, req.C, req.epsilon, cv_folds=req.cv_folds)
        elif m == "gradient_boosting":
            res = gradient_boosting(req.X, req.y, req.n_estimators, req.learning_rate, cv_folds=req.cv_folds)
        elif m == "kmeans":
            res = kmeans_clustering(req.X, k=req.k)
        elif m == "dbscan":
            res = dbscan_clustering(req.X, eps=req.eps, min_samples=req.min_samples)
        else:
            raise ValueError(f"Modèle ML inconnu : {m}")
        return {"status": "ok", **res}
    except Exception as e:
        logger.error(f"/train_ai/ml : {e}")
        raise HTTPException(400, str(e))


@router.post("/dl", summary="Entraînement Deep Learning (PyTorch)")
async def train_dl(req: DLRequest):
    """
    Entraîne un réseau de neurones MLP ou ResNet.
    Pour le modèle hybride, un modèle physique de base est utilisé comme prior.
    """
    try:
        if req.model == "hybrid":
            if not req.physics_model or not req.physics_params:
                raise ValueError("Modèle hybride : physics_model et physics_params requis.")

            from modeling.physical_models import kinetics_order1
            p = req.physics_params
            order = int(p.get("order", 1))
            C0, k = p.get("C0", 1.0), p.get("k", 0.1)
            fn_map = {0: lambda X: np.maximum(C0 - k * X[:,0], 0),
                      1: lambda X: C0 * np.exp(-k * X[:,0]),
                      2: lambda X: C0 / (1 + k * C0 * X[:,0])}
            physics_fn = fn_map.get(order, fn_map[1])

            res = train_hybrid_model(req.X, req.y, physics_fn, req.hidden_dims, req.lr, req.epochs, req.patience)
        else:
            res = train_mlp(
                req.X, req.y,
                hidden_dims=req.hidden_dims,
                activation=req.activation,
                dropout=req.dropout,
                batch_norm=req.batch_norm,
                lr=req.lr,
                epochs=req.epochs,
                batch_size=req.batch_size,
                patience=req.patience,
                architecture=req.model.value,
            )
        return {"status": "ok", **res}
    except Exception as e:
        logger.error(f"/train_ai/dl : {e}")
        raise HTTPException(400, str(e))
