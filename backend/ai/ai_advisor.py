"""
ai/ai_advisor.py
=================
Analyse les données, détecte patterns et recommande le modèle optimal.
Expose la fonction standalone analyze_and_advise() attendue par routes_ai.py.
"""

from __future__ import annotations
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.metrics import r2_score
from loguru import logger
from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Helpers d'analyse internes
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


def _check_linearity(x: np.ndarray, y: np.ndarray) -> Dict:
    X = x.reshape(-1, 1)
    lr = LinearRegression().fit(X, y)
    r2_lin = float(r2_score(y, lr.predict(X)))
    pipe3 = make_pipeline(PolynomialFeatures(3), LinearRegression())
    pipe3.fit(X, y)
    r2_poly = float(r2_score(y, pipe3.predict(X)))
    pearson_r, pearson_p = stats.pearsonr(x, y)
    return {
        "r2_linear":            round(r2_lin, 6),
        "r2_polynomial_deg3":   round(r2_poly, 6),
        "pearson_r":            round(float(pearson_r), 6),
        "pearson_p":            round(float(pearson_p), 6),
        "is_linear":            bool(r2_lin > 0.90 and abs(r2_poly - r2_lin) < 0.05),
        "linearity_score":      round(r2_lin, 6),
    }


def _estimate_noise(x: np.ndarray, y: np.ndarray) -> Dict:
    X = x.reshape(-1, 1)
    lr = LinearRegression().fit(X, y)
    residuals = y - lr.predict(X)
    snr = float(np.var(lr.predict(X)) / (np.var(residuals) + 1e-12))
    level = "low" if snr > 10 else "medium" if snr > 2 else "high"
    return {
        "residuals_std": round(float(np.std(residuals)), 6),
        "snr_ratio":     round(snr, 4),
        "noise_level":   level,
    }


def _check_complexity(x: np.ndarray, y: np.ndarray) -> Dict:
    X = x.reshape(-1, 1)
    r2_by_deg = {}
    for deg in [1, 2, 3, 4, 5]:
        try:
            pipe = make_pipeline(PolynomialFeatures(deg), LinearRegression())
            pipe.fit(X, y)
            r2_by_deg[deg] = round(float(r2_score(y, pipe.predict(X))), 6)
        except Exception:
            r2_by_deg[deg] = None
    optimal = next((d for d, r in r2_by_deg.items() if r and r > 0.95), 5)
    label = "low" if optimal <= 1 else "medium" if optimal <= 3 else "high"
    return {"r2_by_degree": r2_by_deg, "optimal_degree": optimal, "complexity_label": label}


def _detect_outliers(y: np.ndarray) -> Dict:
    z = np.abs(stats.zscore(y))
    Q1, Q3 = np.percentile(y, 25), np.percentile(y, 75)
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
    kt, kt_p   = stats.kendalltau(x, y)
    return {
        "spearman_r":     round(float(sp_r), 6),
        "spearman_p":     round(float(sp_p), 6),
        "kendall_tau":    round(float(kt), 6),
        "is_monotone":    bool(abs(sp_r) > 0.85),
        "trend_direction": "increasing" if sp_r > 0 else "decreasing",
    }


def _recommend(desc, lin, noise, complexity, outliers, trends) -> Dict:
    n    = desc["n_points"]
    recs = []

    # Régression
    if lin["is_linear"]:
        recs.append({"type": "regression", "model": "linear",
                     "confidence": "high",
                     "reason": f"R²={lin['r2_linear']:.3f} — relation linéaire."})
    elif complexity["optimal_degree"] <= 3:
        recs.append({"type": "regression", "model": "polynomial",
                     "params": {"degree": complexity["optimal_degree"]},
                     "confidence": "high",
                     "reason": f"Polynôme deg {complexity['optimal_degree']} optimal."})
    else:
        recs.append({"type": "regression",
                     "model": "ridge" if n < 100 else "random_forest",
                     "confidence": "medium",
                     "reason": "Relation complexe — modèle régularisé conseillé."})

    # Modèle physique
    if trends["is_monotone"] and lin["linearity_score"] < 0.95:
        recs.append({"type": "physical", "model": "kinetics_order1",
                     "confidence": "medium",
                     "reason": "Décroissance monotone — cinétique ordre 1 probable."})

    # ML
    if n >= 50 and complexity["complexity_label"] == "high":
        recs.append({"type": "ml", "model": "random_forest",
                     "confidence": "medium",
                     "reason": "Données suffisantes + relation complexe."})

    # DL
    if n >= 50 and complexity["complexity_label"] == "high":
        recs.append({"type": "deep_learning", "model": "neural_network",
                     "params": {"hidden_dims": [64, 32, 16], "epochs": 200},
                     "confidence": "medium",
                     "reason": "Réseau de neurones adapté aux relations complexes."})

    # Hybride
    if n >= 30 and noise["noise_level"] in ("medium", "high"):
        recs.append({"type": "hybrid", "model": "physics_informed_nn",
                     "confidence": "medium",
                     "reason": "Bruit détecté — modèle hybride physique+NN recommandé."})

    order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: order.get(r["confidence"], 3))

    # Qualité données
    score = 100
    if n < 10:   score -= 30
    elif n < 30: score -= 15
    if outliers["outlier_fraction"] > 0.1: score -= 20
    if noise["noise_level"] == "high":     score -= 15

    warnings = []
    if n < 10:
        warnings.append(f"⚠️ Seulement {n} points — résultats peu fiables.")
    if outliers["has_outliers"]:
        warnings.append(f"⚠️ {outliers['z_score_outliers']} outliers détectés (Z-score > 3).")
    if noise["noise_level"] == "high":
        warnings.append("⚠️ Bruit élevé — envisager un filtrage préalable.")

    return {
        "primary_recommendation": recs[0] if recs else None,
        "all_recommendations":    recs,
        "data_quality": {
            "score": max(0, score),
            "label": "excellent" if score >= 80 else "good" if score >= 60 else "fair" if score >= 40 else "poor",
        },
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PUBLIQUE — importée par routes_ai.py
# ─────────────────────────────────────────────────────────────────────────────

def analyze_and_advise(x: List[float], y: List[float]) -> Dict[str, Any]:
    """
    Point d'entrée principal du conseiller IA.
    Analyse les données et retourne un rapport de recommandations structuré.
    """
    logger.info(f"analyze_and_advise — {len(x)} points")
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)

    desc       = _descriptive(xa, ya)
    lin        = _check_linearity(xa, ya)
    noise      = _estimate_noise(xa, ya)
    complexity = _check_complexity(xa, ya)
    outliers   = _detect_outliers(ya)
    trends     = _detect_trends(xa, ya)
    recs       = _recommend(desc, lin, noise, complexity, outliers, trends)

    return {
        "summary": {
            "n_points":   desc["n_points"],
            "trend":      trends["trend_direction"],
            "complexity": complexity["complexity_label"],
            "noise":      noise["noise_level"],
        },
        "data_properties": {
            "descriptive":  desc,
            "linearity":    lin,
            "noise":        noise,
            "complexity":   complexity,
            "outliers":     outliers,
            "trends":       trends,
        },
        "recommendations": recs,
        "priority_action": (
            f"Commencer par : {recs['primary_recommendation']['model']} "
            f"({recs['primary_recommendation']['confidence']} confiance)"
            if recs["primary_recommendation"] else "Données insuffisantes."
        ),
    }
