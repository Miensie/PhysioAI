"""
ai/ai_advisor.py
=================
Conseiller IA — analyse les données et teste les 7 modèles de régression.

IMPORTANT : utilise directement les fonctions de modeling/regression.py
pour garantir des résultats strictement identiques à l'onglet Analyser.
"""

from __future__ import annotations
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from loguru import logger
from typing import List, Dict, Any

# ── Import des MÊMES fonctions que l'onglet Analyser ─────────────────────────
from modeling.regression import (
    linear_regression,
    logarithmic_regression,
    exponential_regression,
    power_regression,
    polynomial_regression,
    ridge_regression,
    lasso_regression,
)


# ─────────────────────────────────────────────────────────────────────────────
# Score des 7 modèles — appelle les mêmes fonctions que /model
# ─────────────────────────────────────────────────────────────────────────────

def _score_all_regressions(x: np.ndarray, y: np.ndarray) -> Dict[str, Dict]:
    """
    Teste les 7 modèles via les fonctions de modeling/regression.py.
    Résultats garantis identiques à l'onglet Analyser.
    """
    x_list = x.tolist()
    y_list = y.tolist()
    scores = {}

    runners = {
        "linear":      lambda: linear_regression(x_list, y_list),
        "logarithmic": lambda: logarithmic_regression(x_list, y_list),
        "exponential": lambda: exponential_regression(x_list, y_list),
        "power":       lambda: power_regression(x_list, y_list),
        "polynomial":  lambda: polynomial_regression(x_list, y_list, degree=3),
        "ridge":       lambda: ridge_regression(x_list, y_list, alpha=1.0),
        "lasso":       lambda: lasso_regression(x_list, y_list, alpha=0.1),
    }

    for name, fn in runners.items():
        try:
            result = fn()
            m = result.get("metrics", {})
            scores[name] = {
                "r2":      m.get("r2", -1.0),
                "rmse":    m.get("rmse", None),
                "equation": result.get("equation", ""),
                "params":  result.get("params", {}),
            }
        except Exception as e:
            logger.warning(f"Régression {name} échouée dans advisor: {e}")
            scores[name] = {"r2": -1.0, "error": str(e)}

    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Helpers d'analyse des données
# ─────────────────────────────────────────────────────────────────────────────

def _descriptive(x: np.ndarray, y: np.ndarray) -> Dict:
    def s(arr, n):
        return {
            f"{n}_mean":  float(np.mean(arr)),
            f"{n}_std":   float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            f"{n}_min":   float(np.min(arr)),
            f"{n}_max":   float(np.max(arr)),
            f"{n}_range": float(np.max(arr) - np.min(arr)),
        }
    return {"n_points": int(len(x)), **s(x, "x"), **s(y, "y")}


def _estimate_noise(x: np.ndarray, y: np.ndarray) -> Dict:
    X  = x.reshape(-1, 1)
    lr = LinearRegression().fit(X, y)
    res = y - lr.predict(X)
    snr = float(np.var(lr.predict(X)) / (np.var(res) + 1e-12))
    return {
        "residuals_std": round(float(np.std(res)), 6),
        "snr_ratio":     round(snr, 4),
        "noise_level":   "low" if snr > 10 else "medium" if snr > 2 else "high",
    }


def _detect_outliers(y: np.ndarray) -> Dict:
    z   = np.abs(stats.zscore(y))
    Q1, Q3 = np.percentile(y, [25, 75])
    IQR = Q3 - Q1
    z_out  = int(np.sum(z > 3))
    iq_out = int(np.sum((y < Q1 - 1.5*IQR) | (y > Q3 + 1.5*IQR)))
    return {
        "z_score_outliers": z_out,
        "iqr_outliers":     iq_out,
        "has_outliers":     bool(z_out > 0 or iq_out > 0),
        "outlier_fraction": round(float(max(z_out, iq_out) / len(y)), 4),
    }


def _detect_trends(x: np.ndarray, y: np.ndarray) -> Dict:
    sp_r, sp_p = stats.spearmanr(x, y)
    kt,   kt_p = stats.kendalltau(x, y)
    return {
        "spearman_r":      round(float(sp_r), 6),
        "spearman_p":      round(float(sp_p), 6),
        "kendall_tau":     round(float(kt), 6),
        "is_monotone":     bool(abs(sp_r) > 0.85),
        "trend_direction": "increasing" if sp_r > 0 else "decreasing",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Recommandations basées sur les scores réels
# ─────────────────────────────────────────────────────────────────────────────

def _recommend(desc, reg_scores, noise, outliers, trends) -> Dict:
    n    = desc["n_points"]
    recs = []

    # Trier par R² décroissant (ignorer erreurs)
    valid = {k: v for k, v in reg_scores.items()
             if "error" not in v and v.get("r2", -1) >= 0}
    ranking = sorted(valid.items(), key=lambda x: x[1]["r2"], reverse=True)

    # Top 3 régressions
    for rank, (model, info) in enumerate(ranking[:3]):
        r2 = info["r2"]
        confidence = "high" if r2 > 0.95 else "medium" if r2 > 0.80 else "low"
        recs.append({
            "type":       "regression",
            "model":      model,
            "rank":       rank + 1,
            "r2":         r2,
            "equation":   info.get("equation", ""),
            "confidence": confidence,
            "reason":     (f"R²={r2:.4f} — rang #{rank+1} sur 7 modeles testes. "
                           + info.get("equation", "")),
        })

    # Modèle physique
    best_name = ranking[0][0] if ranking else "linear"
    best_r2   = ranking[0][1]["r2"] if ranking else 0

    if trends["is_monotone"] and trends["trend_direction"] == "decreasing":
        recs.append({
            "type":       "physical",
            "model":      "kinetics_order1",
            "confidence": "medium",
            "reason":     (f"Decroissance monotone — cinetique ordre 1 probable. "
                           f"Meilleure regression: {best_name} (R2={best_r2:.4f})."),
        })
    elif trends["is_monotone"] and trends["trend_direction"] == "increasing":
        recs.append({
            "type":       "physical",
            "model":      "cstr_ou_diffusion",
            "confidence": "low",
            "reason":     "Tendance croissante — CSTR ou diffusion possible.",
        })

    # ML
    if n >= 30:
        recs.append({
            "type":       "ml",
            "model":      "random_forest",
            "confidence": "medium" if n >= 50 else "low",
            "reason":     f"Random Forest pour {n} points.",
        })

    if n >= 50:
        recs.append({
            "type":       "deep_learning",
            "model":      "mlp",
            "confidence": "medium",
            "reason":     f"MLP PyTorch adapte avec {n} points.",
        })

    if n >= 30 and noise["noise_level"] in ("medium", "high"):
        recs.append({
            "type":       "hybrid",
            "model":      "physics_informed_nn",
            "confidence": "medium",
            "reason":     f"Bruit {noise['noise_level']} — modele hybride recommande.",
        })

    # Qualité
    score = 100
    if n < 10:   score -= 30
    elif n < 30: score -= 15
    if outliers["outlier_fraction"] > 0.1: score -= 20
    if noise["noise_level"] == "high":     score -= 15

    warnings = []
    if n < 10:
        warnings.append(f"Seulement {n} points — resultats peu fiables.")
    if outliers["has_outliers"]:
        warnings.append(f"{outliers['z_score_outliers']} outliers detectes (Z>3).")
    if noise["noise_level"] == "high":
        warnings.append("Bruit eleve — filtrage conseille.")

    return {
        "primary_recommendation": recs[0] if recs else None,
        "all_recommendations":    recs,
        "regression_ranking":     [
            {"model": k, "r2": v["r2"], "equation": v.get("equation", "")}
            for k, v in ranking
        ],
        "data_quality": {
            "score": max(0, score),
            "label": ("excellent" if score >= 80 else
                      "good" if score >= 60 else
                      "fair" if score >= 40 else "poor"),
        },
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PUBLIQUE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_and_advise(x: List[float], y: List[float]) -> Dict[str, Any]:
    """
    Analyse complète — utilise les mêmes fonctions que l'onglet Analyser
    pour garantir des résultats parfaitement cohérents.
    """
    logger.info(f"analyze_and_advise — {len(x)} points — 7 regressions (memes fonctions)")
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)

    desc       = _descriptive(xa, ya)
    reg_scores = _score_all_regressions(xa, ya)   # ← MÊMES fonctions que /model
    noise      = _estimate_noise(xa, ya)
    outliers   = _detect_outliers(ya)
    trends     = _detect_trends(xa, ya)
    recs       = _recommend(desc, reg_scores, noise, outliers, trends)

    best_reg = (recs["regression_ranking"][0]
                if recs["regression_ranking"]
                else {"model": "?", "r2": 0})

    return {
        "summary": {
            "n_points":        desc["n_points"],
            "trend":           trends["trend_direction"],
            "noise":           noise["noise_level"],
            "best_regression": best_reg["model"],
            "best_r2":         best_reg["r2"],
        },
        "regression_scores":  reg_scores,
        "data_properties": {
            "descriptive": desc,
            "noise":       noise,
            "outliers":    outliers,
            "trends":      trends,
        },
        "recommendations": recs,
        "priority_action": (
            f"Meilleure regression: {best_reg['model']} (R2={best_reg['r2']:.4f}). "
            + (f"Recommandation: {recs['primary_recommendation']['model']}"
               if recs["primary_recommendation"] else "")
        ),
    }