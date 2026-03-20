"""
api/routes_predict.py
======================
POST /predict/new          — Prédiction avec un modèle choisi (10 modèles)
POST /predict/best         — Comparaison automatique tous modèles, retourne le meilleur
POST /decision/global      — Décision Gemini AI (Google AI Studio)
POST /decision/quick       — Décision rapide locale (sans clé API)
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import PredictionRequest, PredictBestRequest, GlobalDecisionRequest
from ai.predictor import predict_new, predict_best
from ai.gemini_decision import global_decision
from ai.ai_advisor import analyze_and_advise

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉDICTION — modèle choisi
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/predict/new",
    summary="Prédiction sur nouvelles données",
    description=(
        "Supporte : linear, logarithmic, exponential, power, "
        "polynomial, ridge, lasso, random_forest, svr, "
        "gradient_boosting, mlp."
    ))
async def predict_new_data(req: PredictionRequest):
    logger.info(f"POST /predict/new  model={req.model_type}  "
                f"train={len(req.X_train)}  predict={len(req.X_predict)}")
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
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"predict/new error: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# PRÉDICTION AUTOMATIQUE — tous les modèles
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/predict/best",
    summary="Comparaison automatique — tous les modèles",
    description=(
        "Teste les 10 modèles (linéaire, log, exp, puissance, polynomial, "
        "ridge, lasso, random_forest, svr, gradient_boosting), "
        "les classe par R² et retourne le meilleur + le comparatif complet."
    ))
async def predict_best_model(req: PredictBestRequest):
    logger.info(f"POST /predict/best  train={len(req.X_train)}  "
                f"predict={len(req.X_predict)}")
    try:
        return predict_best(
            X_train=req.X_train,
            y_train=req.y_train,
            X_predict=req.X_predict,
            degree=req.degree,
            alpha=req.alpha,
        )
    except Exception as e:
        logger.error(f"predict/best error: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCISION GLOBALE — GEMINI
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/decision/global",
    summary="Décision globale avec Gemini AI (Google AI Studio)")
async def decision_global(req: GlobalDecisionRequest):
    logger.info(f"POST /decision/global  lang={req.language}  n={len(req.x)}")
    if not req.gemini_api_key or len(req.gemini_api_key) < 10:
        raise HTTPException(400,
            "Clé API Gemini invalide. "
            "Obtenez la vôtre sur https://aistudio.google.com/app/apikey")
    try:
        return await global_decision(
            x=req.x, y=req.y,
            gemini_api_key=req.gemini_api_key,
            context=req.context,
            regression_result=req.regression_result,
            physical_result=req.physical_result,
            ai_advisor_result=req.ai_advisor_result,
            language=req.language,
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Erreur Gemini : {e}")
    except Exception as e:
        logger.error(f"decision/global error: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCISION RAPIDE — locale
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/decision/quick",
    summary="Décision rapide locale (sans clé API)")
async def decision_quick(req: GlobalDecisionRequest):
    logger.info("POST /decision/quick")
    try:
        adv = analyze_and_advise(req.x, req.y)
        primary = (adv.get("recommendations", {})
                   .get("primary_recommendation") or {})
        ranking = (adv.get("recommendations", {})
                   .get("regression_ranking", []))
        warnings = adv.get("recommendations", {}).get("warnings", [])
        s = adv.get("summary", {})

        # Contexte de régression si disponible
        reg_detail = ""
        if req.regression_result:
            bm = (req.regression_result.get("best_model")
                  or req.regression_result.get("model", "?"))
            m  = (req.regression_result.get("all_models", {}).get(bm, {})
                  .get("metrics") or req.regression_result.get("metrics") or {})
            reg_detail = f"Régression externe : {bm} (R²={m.get('r2','?')})"

        return {
            "status":   "success",
            "language": req.language,
            "model":    "physioai-local",
            "report": {
                "decision_globale": {
                    "verdict": (
                        f"Meilleure régression : {s.get('best_regression','?')} "
                        f"(R²={s.get('best_r2',0):.4f}). "
                        + (f"Recommandation : {primary.get('model','?')}"
                           if primary else "")
                    ),
                    "confiance":              primary.get("confidence", "?"),
                    "score_qualite_donnees":  (
                        adv.get("recommendations", {})
                        .get("data_quality", {}).get("score", 0)
                    ),
                },
                "classement_regressions": ranking,        # ← les 7 modèles classés
                "interpretation_physique": {
                    "tendance":    s.get("trend", "?"),
                    "bruit":       s.get("noise", "?"),
                    "n_points":    s.get("n_points", 0),
                },
                "recommandations_prioritaires": [
                    {
                        "priorite":      i + 1,
                        "action":        r.get("model", ""),
                        "type":          r.get("type", ""),
                        "r2":            r.get("r2", ""),
                        "justification": r.get("reason", ""),
                        "confiance":     r.get("confidence", ""),
                    }
                    for i, r in enumerate(
                        adv.get("recommendations", {})
                        .get("all_recommendations", [])[:5]
                    )
                ],
                "scores_regressions": adv.get("regression_scores", {}),  # ← scores bruts
                "alertes": warnings,
                "contexte_externe": reg_detail,
                "resume_executif": adv.get("priority_action", ""),
                "note": (
                    "Analyse locale — pour rapport Gemini complet "
                    "utilisez /decision/global avec une clé Google AI Studio."
                ),
            },
        }
    except Exception as e:
        logger.error(f"decision/quick error: {e}")
        raise HTTPException(500, str(e))