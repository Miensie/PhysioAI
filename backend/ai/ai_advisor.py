"""
ai/ai_advisor.py
=================
Conseiller IA complet :
  - Teste les 7 modèles de régression (via modeling/regression.py)
  - Teste et calibre les 11 modèles physiques (via physical_scorer.py)
  - Retourne un classement objectif basé sur R² réels
"""

from __future__ import annotations
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from loguru import logger
from typing import List, Dict, Any

from modeling.regression import (
    linear_regression, logarithmic_regression, exponential_regression,
    power_regression, polynomial_regression, ridge_regression, lasso_regression,
)
from ai.physical_scorer import score_physical_models


# ─────────────────────────────────────────────────────────────────────────────
# Régressions — mêmes fonctions que l'onglet Analyser
# ─────────────────────────────────────────────────────────────────────────────

def _score_all_regressions(x: np.ndarray, y: np.ndarray) -> Dict[str, Dict]:
    x_l, y_l = x.tolist(), y.tolist()
    runners = {
        "linear":      lambda: linear_regression(x_l, y_l),
        "logarithmic": lambda: logarithmic_regression(x_l, y_l),
        "exponential": lambda: exponential_regression(x_l, y_l),
        "power":       lambda: power_regression(x_l, y_l),
        "polynomial":  lambda: polynomial_regression(x_l, y_l, degree=3),
        "ridge":       lambda: ridge_regression(x_l, y_l, alpha=1.0),
        "lasso":       lambda: lasso_regression(x_l, y_l, alpha=0.1),
    }
    scores = {}
    for name, fn in runners.items():
        try:
            r = fn()
            m = r.get("metrics", {})
            scores[name] = {
                "r2":      m.get("r2", -1.0),
                "rmse":    m.get("rmse", None),
                "equation": r.get("equation", ""),
                "params":  r.get("params", {}),
            }
        except Exception as e:
            logger.warning(f"Regression {name} echouee: {e}")
            scores[name] = {"r2": -1.0, "error": str(e)}
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Helpers statistiques
# ─────────────────────────────────────────────────────────────────────────────

def _descriptive(x, y):
    def s(a, n):
        return {f"{n}_mean": float(np.mean(a)), f"{n}_std": float(np.std(a, ddof=1)) if len(a)>1 else 0.,
                f"{n}_min": float(np.min(a)), f"{n}_max": float(np.max(a)),
                f"{n}_range": float(np.max(a)-np.min(a))}
    return {"n_points": int(len(x)), **s(x,"x"), **s(y,"y")}

def _estimate_noise(x, y):
    lr  = LinearRegression().fit(x.reshape(-1,1), y)
    res = y - lr.predict(x.reshape(-1,1))
    snr = float(np.var(lr.predict(x.reshape(-1,1))) / (np.var(res) + 1e-12))
    return {"residuals_std": round(float(np.std(res)),6), "snr_ratio": round(snr,4),
            "noise_level": "low" if snr>10 else "medium" if snr>2 else "high"}

def _detect_outliers(y):
    z = np.abs(stats.zscore(y))
    Q1,Q3 = np.percentile(y,[25,75]); IQR=Q3-Q1
    zo  = int(np.sum(z>3))
    iqo = int(np.sum((y<Q1-1.5*IQR)|(y>Q3+1.5*IQR)))
    return {"z_score_outliers":zo,"iqr_outliers":iqo,
            "has_outliers":bool(zo>0 or iqo>0),"outlier_fraction":round(float(max(zo,iqo)/len(y)),4)}

def _detect_trends(x, y):
    sp_r,sp_p = stats.spearmanr(x,y); kt,_ = stats.kendalltau(x,y)
    return {"spearman_r":round(float(sp_r),6),"spearman_p":round(float(sp_p),6),
            "kendall_tau":round(float(kt),6),"is_monotone":bool(abs(sp_r)>0.85),
            "trend_direction":"increasing" if sp_r>0 else "decreasing"}


# ─────────────────────────────────────────────────────────────────────────────
# Construction des recommandations
# ─────────────────────────────────────────────────────────────────────────────

def _recommend(desc, reg_scores, phys_result, noise, outliers, trends):
    n    = desc["n_points"]
    recs = []

    # ── Top 3 régressions ─────────────────────────────────────────────────────
    valid_reg = {k:v for k,v in reg_scores.items() if "error" not in v and v.get("r2",-1)>=0}
    reg_ranking = sorted(valid_reg.items(), key=lambda x: x[1]["r2"], reverse=True)
    for rank,(model,info) in enumerate(reg_ranking[:3]):
        r2 = info["r2"]
        recs.append({
            "type":"regression","model":model,"rank":rank+1,"r2":r2,
            "equation":info.get("equation",""),
            "confidence":"high" if r2>0.95 else "medium" if r2>0.80 else "low",
            "reason":f"R2={r2:.4f} — rang #{rank+1}/7. {info.get('equation','')}",
        })

    # ── Top 3 modèles physiques (basés sur R² réels) ─────────────────────────
    phys_ranking = phys_result.get("ranking", [])
    for rank, ph in enumerate(phys_ranking[:3]):
        r2 = ph["r2"]
        if r2 < 0: continue
        recs.append({
            "type":       "physical",
            "model":      ph["model"],
            "label":      ph["label"],
            "rank":       rank + 1,
            "r2":         r2,
            "equation":   ph.get("equation",""),
            "params":     ph.get("params",{}),
            "domain":     ph.get("domain",""),
            "confidence": "high" if r2>0.95 else "medium" if r2>0.80 else "low",
            "reason":     (f"R2={r2:.4f} — rang #{rank+1}/{phys_result.get('n_successful',0)} "
                          f"modeles physiques testes. Domaine : {ph.get('domain','')}. "
                          f"Equation : {ph.get('equation','')}."),
        })

    # ── ML ────────────────────────────────────────────────────────────────────
    if n >= 30:
        recs.append({"type":"ml","model":"random_forest",
                     "confidence":"medium" if n>=50 else "low",
                     "reason":f"Random Forest adapte pour {n} points."})
    if n >= 50:
        recs.append({"type":"deep_learning","model":"mlp","confidence":"medium",
                     "reason":f"MLP PyTorch recommande avec {n} points."})
    if n >= 30 and noise["noise_level"] in ("medium","high"):
        recs.append({"type":"hybrid","model":"physics_informed_nn","confidence":"medium",
                     "reason":f"Bruit {noise['noise_level']} detecte — hybride recommande."})

    # ── Qualité ───────────────────────────────────────────────────────────────
    score = 100
    if n<10: score-=30
    elif n<30: score-=15
    if outliers["outlier_fraction"]>0.1: score-=20
    if noise["noise_level"]=="high": score-=15

    warnings = []
    if n<10: warnings.append(f"Seulement {n} points — resultats peu fiables.")
    if outliers["has_outliers"]: warnings.append(f"{outliers['z_score_outliers']} outliers detectes.")
    if noise["noise_level"]=="high": warnings.append("Bruit eleve — filtrage conseille.")

    return {
        "primary_recommendation": recs[0] if recs else None,
        "all_recommendations":    recs,
        "regression_ranking":     [{"model":k,"r2":v["r2"],"equation":v.get("equation","")}
                                    for k,v in reg_ranking],
        "physical_ranking":       phys_ranking,   # ← classement complet physique
        "data_quality":           {"score":max(0,score),
                                   "label":"excellent" if score>=80 else "good" if score>=60
                                           else "fair" if score>=40 else "poor"},
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PUBLIQUE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_and_advise(x: List[float], y: List[float]) -> Dict[str, Any]:
    """
    Analyse complète :
      1. 7 modèles de régression (mêmes fonctions que /model)
      2. 11 modèles physiques calibrés (physical_scorer.py)
      3. Recommandations classées par R² réel
    """
    logger.info(f"analyze_and_advise — {len(x)} pts — 7 regressions + 11 modeles physiques")
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)

    desc        = _descriptive(xa, ya)
    reg_scores  = _score_all_regressions(xa, ya)
    phys_result = score_physical_models(x, y)
    noise       = _estimate_noise(xa, ya)
    outliers    = _detect_outliers(ya)
    trends      = _detect_trends(xa, ya)
    recs        = _recommend(desc, reg_scores, phys_result, noise, outliers, trends)

    best_reg  = recs["regression_ranking"][0] if recs["regression_ranking"] else {"model":"?","r2":0}
    best_phys = phys_result["best_physical"] or {}

    return {
        "summary": {
            "n_points":           desc["n_points"],
            "trend":              trends["trend_direction"],
            "noise":              noise["noise_level"],
            "best_regression":    best_reg["model"],
            "best_r2_regression": best_reg["r2"],
            "best_physical":      best_phys.get("model"),
            "best_r2_physical":   best_phys.get("r2"),
            "best_physical_label":best_phys.get("label"),
        },
        "regression_scores":  reg_scores,
        "physical_scores":    phys_result,   # ← NOUVEAU : scores des 11 modèles physiques
        "data_properties":    {"descriptive":desc,"noise":noise,"outliers":outliers,"trends":trends},
        "recommendations":    recs,
        "priority_action": (
            f"Meilleure regression: {best_reg['model']} (R2={best_reg['r2']:.4f}). "
            f"Meilleur modele physique: {best_phys.get('label','?')} (R2={best_phys.get('r2',0):.4f})."
        ),
    }