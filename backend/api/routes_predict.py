"""
api/routes_predict.py
======================
Deux nouveaux groupes d'endpoints :

  POST /predict/new          — Prédiction sur nouvelles données (tous modèles)
  POST /predict/new/batch    — Prédiction par lot

  POST /decision/global      — Décision globale via Gemini AI (Google AI Studio)
  POST /decision/quick       — Décision rapide sans Gemini (analyse locale seule)
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import PredictionRequest, GlobalDecisionRequest
from ai.predictor import predict_new
from ai.gemini_decision import global_decision
from ai.ai_advisor import analyze_and_advise

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉDICTION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/predict/new",
    summary="Prédiction sur nouvelles données",
    description=(
        "Entraîne un modèle sur (X_train, y_train) "
        "et prédit sur X_predict. "
        "Supporte : linear, polynomial, ridge, lasso, "
        "random_forest, svr, gradient_boosting, mlp."
    ),
)
async def predict_new_data(req: PredictionRequest):
    logger.info(
        f"POST /predict/new  model={req.model_type}  "
        f"train={len(req.X_train)}  predict={len(req.X_predict)}"
    )
    try:
        return predict_new(
            X_train=req.X_train,
            y_train=req.y_train,
            X_predict=req.X_predict,
            model_type=req.model_type,
            degree=req.degree,
            alpha=req.alpha,
            n_estimators=req.n_estimators,
            hidden_layers=req.hidden_layers,
            epochs=req.epochs,
            confidence_interval=req.confidence_interval,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur predict/new: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCISION GLOBALE — GEMINI
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/decision/global",
    summary="Décision globale avec Gemini AI",
    description=(
        "Envoie toutes les analyses PhysioAI à Google Gemini "
        "(Google AI Studio) et retourne un rapport de décision "
        "structuré : verdict, interprétation physique, "
        "recommandations prioritaires, risques, résumé exécutif."
    ),
)
async def decision_global(req: GlobalDecisionRequest):
    logger.info(
        f"POST /decision/global  lang={req.language}  "
        f"n={len(req.x)}  context='{req.context[:40]}'"
    )
    if not req.gemini_api_key or len(req.gemini_api_key) < 10:
        raise HTTPException(
            status_code=400,
            detail="Clé API Gemini invalide ou manquante. "
                   "Obtenez votre clé sur https://aistudio.google.com/app/apikey",
        )
    try:
        return await global_decision(
            x=req.x,
            y=req.y,
            gemini_api_key=req.gemini_api_key,
            context=req.context,
            regression_result=req.regression_result,
            physical_result=req.physical_result,
            ai_advisor_result=req.ai_advisor_result,
            language=req.language,
        )
    except RuntimeError as e:
        logger.error(f"Erreur Gemini API: {e}")
        raise HTTPException(status_code=502, detail=f"Erreur Gemini : {str(e)}")
    except Exception as e:
        logger.error(f"Erreur decision/global: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCISION RAPIDE — sans Gemini (analyse locale seule)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/decision/quick",
    summary="Décision rapide (sans Gemini)",
    description="Analyse locale uniquement — ne nécessite pas de clé API.",
)
async def decision_quick(req: GlobalDecisionRequest):
    """Version sans Gemini pour tester sans clé API."""
    logger.info("POST /decision/quick")
    try:
        advisor_result = analyze_and_advise(req.x, req.y)
        primary = (advisor_result.get("recommendations", {})
                   .get("primary_recommendation", {})) or {}
        warnings = (advisor_result.get("recommendations", {})
                    .get("warnings", []))

        s = advisor_result.get("summary", {})
        return {
            "status":   "success",
            "language": req.language,
            "model":    "physioai-local",
            "report": {
                "decision_globale": {
                    "verdict":    f"{primary.get('model','?')} recommandé "
                                  f"— {primary.get('reason','')}",
                    "confiance":  primary.get("confidence", "?"),
                    "score_qualite_donnees":
                        advisor_result.get("recommendations", {})
                        .get("data_quality", {}).get("score", 0),
                },
                "interpretation_physique": {
                    "phenomene_detecte": s.get("trend", "?"),
                    "complexite":        s.get("complexity", "?"),
                    "bruit":             s.get("noise", "?"),
                },
                "recommandations_prioritaires": [
                    {
                        "priorite":       i + 1,
                        "action":         r.get("model", ""),
                        "type":           r.get("type", ""),
                        "justification":  r.get("reason", ""),
                        "confiance":      r.get("confidence", ""),
                    }
                    for i, r in enumerate(
                        advisor_result.get("recommendations", {})
                        .get("all_recommendations", [])[:4]
                    )
                ],
                "alertes": warnings,
                "resume_executif": advisor_result.get("priority_action", ""),
                "note": "Décision rapide locale — pour l'analyse Gemini complète "
                        "utilisez /decision/global avec une clé API Google AI Studio.",
            },
        }
    except Exception as e:
        logger.error(f"Erreur decision/quick: {e}")
        raise HTTPException(status_code=500, detail=str(e))
