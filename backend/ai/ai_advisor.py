"""
ai/ai_advisor.py
=================
Conseiller IA — analyse les données et teste les 7 modèles de régression
(linéaire, log, exponentiel, puissance, polynomial, ridge, lasso)
pour donner des recommandations précises basées sur des scores réels.
"""

from __future__ import annotations
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import r2_score
from loguru import logger
from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Test de chaque modèle de régression sur les données
# ─────────────────────────────────────────────────────────────────────────────

def _score_all_regressions(x: np.ndarray, y: np.ndarray) -> Dict[str, Dict]:
    """
    Teste les 7 modèles de régression et retourne le R² de chacun.
    Gère les erreurs silencieusement (curve_fit peut diverger).
    """
    scores = {}

    # 1. Linéaire
    try:
        X = x.reshape(-1, 1)
        m = LinearRegression().fit(X, y)
        scores["linear"] = {
            "r2":      round(float(r2_score(y, m.predict(X))), 6),
            "equation": f"y = {m.coef_[0]:.4f}·x + {m.intercept_:.4f}",
        }
    except Exception as e:
        scores["linear"] = {"r2": -1.0, "error": str(e)}

    # 2. Logarithmique
    try:
        def fn_log(x, a, b): return a * np.log(np.abs(x) + 1e-9) + b
        popt, _ = curve_fit(fn_log, x, y, maxfev=10000)
        scores["logarithmic"] = {
            "r2":      round(float(r2_score(y, fn_log(x, *popt))), 6),
            "equation": f"y = {popt[0]:.4f}·ln(x) + {popt[1]:.4f}",
            "params":  {"a": popt[0], "b": popt[1]},
        }
    except Exception as e:
        scores["logarithmic"] = {"r2": -1.0, "error": str(e)}

    # 3. Exponentielle
    try:
        def fn_exp(x, a, b, c): return a * np.exp(b * x) + c
        popt, _ = curve_fit(fn_exp, x, y, p0=[1., 0.01, 0.], maxfev=50000)
        scores["exponential"] = {
            "r2":      round(float(r2_score(y, fn_exp(x, *popt))), 6),
            "equation": f"y = {popt[0]:.4f}·exp({popt[1]:.4f}·x) + {popt[2]:.4f}",
            "params":  {"a": popt[0], "b": popt[1], "c": popt[2]},
        }
    except Exception as e:
        scores["exponential"] = {"r2": -1.0, "error": str(e)}

    # 4. Puissance
    try:
        def fn_pow(x, a, b): return a * np.power(np.abs(x) + 1e-9, b)
        popt, _ = curve_fit(fn_pow, x, y, p0=[1., 1.], maxfev=10000)
        scores["power"] = {
            "r2":      round(float(r2_score(y, fn_pow(x, *popt))), 6),
            "equation": f"y = {popt[0]:.4f}·x^{popt[1]:.4f}",
            "params":  {"a": popt[0], "b": popt[1]},
        }
    except Exception as e:
        scores["power"] = {"r2": -1.0, "error": str(e)}

    # 5. Polynomiale deg 3
    try:
        X = x.reshape(-1, 1)
        pipe = Pipeline([
            ("poly",  PolynomialFeatures(3, include_bias=False)),
            ("model", LinearRegression()),
        ]).fit(X, y)
        scores["polynomial"] = {
            "r2":      round(float(r2_score(y, pipe.predict(X))), 6),
            "equation": "Polynôme deg 3",
            "degree":   3,
        }
    except Exception as e:
        scores["polynomial"] = {"r2": -1.0, "error": str(e)}

    # 6. Ridge
    try:
        X = x.reshape(-1, 1)
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  Ridge(alpha=1.0)),
        ]).fit(X, y)
        scores["ridge"] = {
            "r2":      round(float(r2_score(y, pipe.predict(X))), 6),
            "equation": "Ridge (α=1.0)",
        }
    except Exception as e:
        scores["ridge"] = {"r2": -1.0, "error": str(e)}

    # 7. Lasso
    try:
        X = x.reshape(-1, 1)
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  Lasso(alpha=0.1, max_iter=10000)),
        ]).fit(X, y)
        scores["lasso"] = {
            "r2":      round(float(r2_score(y, pipe.predict(X))), 6),
            "equation": "Lasso (α=0.1)",
        }
    except Exception as e:
        scores["lasso"] = {"r2": -1.0, "error": str(e)}

    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Helpers d'analyse
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
# Recommandations basées sur les scores réels de régression
# ─────────────────────────────────────────────────────────────────────────────

def _recommend(desc, reg_scores, noise, outliers, trends) -> Dict:
    n    = desc["n_points"]
    recs = []

    # ── Trier les régressions par R² décroissant ──────────────────────────────
    valid_regs = {
        k: v for k, v in reg_scores.items()
        if "error" not in v and v.get("r2", -1) >= 0
    }
    ranking = sorted(valid_regs.items(), key=lambda x: x[1]["r2"], reverse=True)

    # Top 3 régressions
    for rank, (model, info) in enumerate(ranking[:3]):
        r2 = info["r2"]
        confidence = "high" if r2 > 0.95 else "medium" if r2 > 0.80 else "low"
        eq = info.get("equation", "")
        recs.append({
            "type":       "regression",
            "model":      model,
            "rank":       rank + 1,
            "r2":         r2,
            "equation":   eq,
            "confidence": confidence,
            "reason":     f"R²={r2:.4f} — rang #{rank+1} sur 7 modèles testés. {eq}",
        })

    # ── Modèle physique ───────────────────────────────────────────────────────
    best_reg_name = ranking[0][0] if ranking else "linear"
    best_r2       = ranking[0][1]["r2"] if ranking else 0

    if trends["is_monotone"] and trends["trend_direction"] == "decreasing":
        if best_reg_name in ("exponential", "power", "logarithmic") or best_r2 < 0.95:
            recs.append({
                "type":       "physical",
                "model":      "kinetics_order1",
                "confidence": "medium",
                "reason":     (f"Décroissance monotone compatible avec "
                               f"cinétique ordre 1 (C=C₀·e^(-kt)). "
                               f"Meilleure régression : {best_reg_name} (R²={best_r2:.4f})."),
            })
    elif trends["is_monotone"] and trends["trend_direction"] == "increasing":
        recs.append({
            "type":       "physical",
            "model":      "cstr_ou_diffusion",
            "confidence": "low",
            "reason":     "Tendance croissante — CSTR transitoire ou diffusion possible.",
        })

    # ── ML ────────────────────────────────────────────────────────────────────
    if n >= 30:
        recs.append({
            "type":       "ml",
            "model":      "random_forest",
            "confidence": "medium" if n >= 50 else "low",
            "reason":     (f"Random Forest recommandé pour {n} points. "
                           f"Capture les non-linéarités non couvertes par régression."),
        })

    if n >= 50:
        recs.append({
            "type":       "deep_learning",
            "model":      "mlp",
            "confidence": "medium",
            "reason":     f"MLP PyTorch adapté avec {n} points pour modélisation complexe.",
        })

    # ── Hybride ───────────────────────────────────────────────────────────────
    if n >= 30 and noise["noise_level"] in ("medium", "high"):
        recs.append({
            "type":       "hybrid",
            "model":      "physics_informed_nn",
            "confidence": "medium",
            "reason":     f"Bruit {noise['noise_level']} détecté — modèle hybride Physique+NN recommandé.",
        })

    # ── Qualité données ───────────────────────────────────────────────────────
    score = 100
    if n < 10:   score -= 30
    elif n < 30: score -= 15
    if outliers["outlier_fraction"] > 0.1: score -= 20
    if noise["noise_level"] == "high":     score -= 15

    warnings = []
    if n < 10:
        warnings.append(f"⚠️ Seulement {n} points — résultats peu fiables.")
    if outliers["has_outliers"]:
        warnings.append(f"⚠️ {outliers['z_score_outliers']} outliers (Z>3).")
    if noise["noise_level"] == "high":
        warnings.append("⚠️ Bruit élevé — filtrage conseillé.")

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
    Analyse complète :
    1. Teste les 7 modèles de régression (scores réels)
    2. Détecte bruit, outliers, tendances
    3. Retourne recommandations classées par R² réel
    """
    logger.info(f"analyze_and_advise — {len(x)} points — teste 7 régressions")
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)

    desc       = _descriptive(xa, ya)
    reg_scores = _score_all_regressions(xa, ya)
    noise      = _estimate_noise(xa, ya)
    outliers   = _detect_outliers(ya)
    trends     = _detect_trends(xa, ya)
    recs       = _recommend(desc, reg_scores, noise, outliers, trends)

    # Meilleur modèle de régression
    best_reg = (recs["regression_ranking"][0] if recs["regression_ranking"]
                else {"model": "?", "r2": 0})

    return {
        "summary": {
            "n_points":       desc["n_points"],
            "trend":          trends["trend_direction"],
            "noise":          noise["noise_level"],
            "best_regression": best_reg["model"],
            "best_r2":         best_reg["r2"],
        },
        "regression_scores": reg_scores,       # ← scores des 7 modèles
        "data_properties": {
            "descriptive": desc,
            "noise":       noise,
            "outliers":    outliers,
            "trends":      trends,
        },
        "recommendations": recs,
        "priority_action": (
            f"Meilleure régression : {best_reg['model']} (R²={best_reg['r2']:.4f}). "
            + (f"Recommandation principale : {recs['primary_recommendation']['model']}"
               if recs["primary_recommendation"] else "")
        ),
    }