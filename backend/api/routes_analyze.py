"""api/routes_analyze.py — Endpoints /analyze"""

import logging
from fastapi import APIRouter, HTTPException
from api.schemas import AnalyzeRequest, StatsRequest, CorrelationRequest
from utils.statistics import descriptive_stats, correlation_matrix
from ai.ai_advisor import recommend_model, analyze_data_properties

router = APIRouter()
logger = logging.getLogger("physioai.api.analyze")


@router.post("/stats", summary="Statistiques descriptives")
async def stats(req: StatsRequest):
    """Calcule min, max, mean, std, médiane, skewness, kurtosis, normalité pour chaque colonne."""
    try:
        return {"status": "ok", "results": descriptive_stats(req.data)}
    except Exception as e:
        logger.error(f"/analyze/stats : {e}")
        raise HTTPException(400, str(e))


@router.post("/correlation", summary="Matrice de corrélation")
async def correlation(req: CorrelationRequest):
    """Calcule les corrélations de Pearson et Spearman entre toutes les paires de variables."""
    try:
        return {"status": "ok", "results": correlation_matrix(req.data)}
    except Exception as e:
        logger.error(f"/analyze/correlation : {e}")
        raise HTTPException(400, str(e))


@router.post("/recommend", summary="Recommandation de modèle IA")
async def recommend(req: AnalyzeRequest):
    """
    Analyse les propriétés des données et recommande automatiquement :
    - Le meilleur modèle statistique
    - Le modèle physique adapté
    - Le modèle IA/ML optimal
    - Une stratégie hybride si pertinente
    """
    try:
        if req.target is None:
            # Prendre la dernière colonne comme cible
            cols   = list(req.data.keys())
            target = cols[-1]
            X_cols = cols[:-1]
        else:
            target = req.target
            X_cols = [c for c in req.data if c != target]

        y = req.data[target]
        X = [req.data[c] for c in X_cols] if X_cols else [[i] for i in range(len(y))]
        # Transpose X
        X_T = list(map(list, zip(*X))) if X_cols else [[v] for v in range(len(y))]

        result = recommend_model(X_T, y, domain=req.domain)
        return {"status": "ok", "target": target, **result}
    except Exception as e:
        logger.error(f"/analyze/recommend : {e}")
        raise HTTPException(400, str(e))


@router.post("/full", summary="Analyse complète")
async def full_analysis(req: AnalyzeRequest):
    """Analyse complète : statistiques + corrélations + recommandation en une seule requête."""
    try:
        stats_res = descriptive_stats(req.data)
        corr_res  = correlation_matrix(req.data)

        rec_res = None
        if req.include_recommendation and req.target and req.target in req.data:
            y = req.data[req.target]
            X_cols = [c for c in req.data if c != req.target]
            X_T = list(map(list, zip(*[req.data[c] for c in X_cols]))) if X_cols else [[v] for v in range(len(y))]
            rec_res = recommend_model(X_T, y, domain=req.domain)

        return {
            "status":         "ok",
            "statistics":     stats_res,
            "correlations":   corr_res,
            "recommendation": rec_res,
        }
    except Exception as e:
        logger.error(f"/analyze/full : {e}")
        raise HTTPException(400, str(e))
