from fastapi import APIRouter, HTTPException
from loguru import logger
from api.schemas import AIAdvisorRequest, MLRequest, DLRequest, HybridRequest
from ai.ai_advisor import analyze_and_advise
from ai.ml_models import random_forest_regression, svr_regression, gradient_boosting, kmeans_clustering
from ai.deep_learning import train_mlp, train_hybrid_model

router = APIRouter()

@router.post("/ai/advise")
async def advise(req: AIAdvisorRequest):
    try: return analyze_and_advise(req.x, req.y)
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/train_ai")
async def train_ai(req: MLRequest):
    try:
        m = req.model_type
        if m == "random_forest":    return random_forest_regression(req.X, req.y, req.n_estimators)
        elif m == "svr":            return svr_regression(req.X, req.y)
        elif m == "gradient_boosting": return gradient_boosting(req.X, req.y, req.n_estimators)
        elif m == "kmeans":         return kmeans_clustering(req.X, req.n_clusters)
        else: raise HTTPException(400, f"Type inconnu: {m}")
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/predict")
async def predict_dl(req: DLRequest):
    try: return train_mlp(req.X, req.y, req.hidden_layers, req.epochs, req.lr)
    except Exception as e: raise HTTPException(500, str(e))

@router.post("/predict/hybrid")
async def predict_hybrid(req: HybridRequest):
    try: return train_hybrid_model(req.t, req.C, req.C0, req.k, req.epochs)
    except Exception as e: raise HTTPException(500, str(e))
