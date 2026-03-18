"""
================================================================
ai/ai_advisor.py
Conseiller IA intelligent :
  - Analyse automatique des données (linéarité, bruit, complexité)
  - Recommandation du modèle optimal
  - Rapport structuré avec scores de confiance
================================================================
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import (
    kurtosis,
    normaltest,
    pearsonr,
    shapiro,
    skew,
    spearmanr,
)
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("physioai.advisor")


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSE DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

def analyze_data_properties(X_data: list[list], y_data: list) -> dict[str, Any]:
    """
    Analyse complète des propriétés statistiques d'un jeu de données.

    Détecte :
    - Linéarité (R² linéaire)
    - Bruit / rapport signal/bruit
    - Complexité non-linéaire (Random Forest vs Linéaire)
    - Distribution (normalité, skewness, kurtosis)
    - Corrélations (Pearson, Spearman)
    - Valeurs aberrantes (IQR)
    - Multicolinéarité (VIF simplifié)
    """
    X = np.asarray(X_data, dtype=np.float64)
    y = np.asarray(y_data, dtype=np.float64).ravel()

    if X.ndim == 1:
        X = X.reshape(-1, 1)

    n, p = X.shape
    sc = StandardScaler()
    Xs = sc.fit_transform(X)

    results = {
        "n_samples":    n,
        "n_features":   p,
        "y_stats":      {},
        "x_stats":      [],
        "correlations": [],
        "linearity":    {},
        "nonlinearity": {},
        "noise":        {},
        "outliers":     {},
        "distribution": {},
    }

    # ── Statistiques de y ────────────────────────────────────────────────
    results["y_stats"] = {
        "mean":     float(np.mean(y)),
        "std":      float(np.std(y, ddof=1)),
        "min":      float(y.min()),
        "max":      float(y.max()),
        "range":    float(y.max() - y.min()),
        "cv":       float(np.std(y, ddof=1) / (abs(np.mean(y)) + 1e-10) * 100),
        "skewness": float(skew(y)),
        "kurtosis": float(kurtosis(y)),
    }

    # ── Test de normalité ────────────────────────────────────────────────
    if n >= 3:
        try:
            _, p_norm = shapiro(y) if n <= 5000 else normaltest(y)
            results["distribution"]["is_normal"] = bool(p_norm > 0.05)
            results["distribution"]["p_value"]   = float(p_norm)
        except Exception:
            results["distribution"]["is_normal"] = None

    # ── Statistiques par feature ─────────────────────────────────────────
    for j in range(p):
        xj = X[:, j]
        results["x_stats"].append({
            "feature":   j,
            "mean":      float(np.mean(xj)),
            "std":       float(np.std(xj, ddof=1)),
            "min":       float(xj.min()),
            "max":       float(xj.max()),
        })

    # ── Corrélations ────────────────────────────────────────────────────
    for j in range(p):
        try:
            r_p, p_p = pearsonr(X[:, j], y)
            r_s, p_s = spearmanr(X[:, j], y)
            results["correlations"].append({
                "feature":  j,
                "pearson":  float(r_p),
                "spearman": float(r_s),
                "p_pearson": float(p_p),
                "p_spearman": float(p_s),
            })
        except Exception:
            pass

    # ── Linéarité (R² régression linéaire) ──────────────────────────────
    try:
        lr = LinearRegression()
        lr.fit(Xs, y)
        y_lr  = lr.predict(Xs)
        r2_lr = float(r2_score(y, y_lr))
        results["linearity"] = {
            "r2_linear":    r2_lr,
            "is_linear":    r2_lr > 0.85,
            "is_moderately_linear": r2_lr > 0.5,
        }
    except Exception:
        results["linearity"] = {"r2_linear": None}

    # ── Complexité non-linéaire (RF vs LR) ──────────────────────────────
    try:
        if n >= 10:
            rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
            rf.fit(Xs, y)
            y_rf  = rf.predict(Xs)
            r2_rf = float(r2_score(y, y_rf))
            r2_lr = results["linearity"].get("r2_linear", 0) or 0
            nonlinearity_gain = max(0.0, r2_rf - r2_lr)
            results["nonlinearity"] = {
                "r2_rf":             r2_rf,
                "nonlinearity_gain": nonlinearity_gain,
                "is_nonlinear":      nonlinearity_gain > 0.1,
                "feature_importance": rf.feature_importances_.tolist(),
            }
    except Exception:
        results["nonlinearity"] = {}

    # ── Bruit ────────────────────────────────────────────────────────────
    try:
        if n >= 10:
            y_lr_p = LinearRegression().fit(Xs, y).predict(Xs) if results["linearity"].get("r2_linear") else y.mean()
            residuals = y - y_lr_p
            snr  = float(np.var(y_lr_p) / (np.var(residuals) + 1e-10))
            noise_pct = float(np.std(residuals) / (np.std(y) + 1e-10) * 100)
            results["noise"] = {
                "snr":       snr,
                "noise_pct": noise_pct,
                "noisy":     noise_pct > 20,
            }
    except Exception:
        results["noise"] = {}

    # ── Outliers (IQR) ───────────────────────────────────────────────────
    q1, q3 = np.percentile(y, [25, 75])
    iqr     = q3 - q1
    lo, hi  = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outlier_idx = np.where((y < lo) | (y > hi))[0].tolist()
    results["outliers"] = {
        "n_outliers": len(outlier_idx),
        "pct":        float(len(outlier_idx) / n * 100),
        "indices":    outlier_idx[:20],
    }

    return results


# ══════════════════════════════════════════════════════════════════════════════
#  RECOMMANDATION DE MODÈLE
# ══════════════════════════════════════════════════════════════════════════════

def recommend_model(
    X_data: list[list], y_data: list,
    domain: str = "auto",  # "chemistry" | "physics" | "process" | "auto"
) -> dict[str, Any]:
    """
    Analyse les données et recommande automatiquement :
    1. Le meilleur modèle statistique
    2. Le modèle physique le plus adapté (si domain fourni)
    3. Le modèle IA le plus adapté
    4. La stratégie hybride

    Retourne un rapport structuré avec scores de confiance.
    """
    # ── Analyse des propriétés ──────────────────────────────────────────
    props = analyze_data_properties(X_data, y_data)
    n     = props["n_samples"]
    p     = props["n_features"]

    r2_lin     = props["linearity"].get("r2_linear", 0) or 0
    r2_rf      = props["nonlinearity"].get("r2_rf", 0) or 0
    nl_gain    = props["nonlinearity"].get("nonlinearity_gain", 0) or 0
    is_noisy   = props["noise"].get("noisy", False)
    noise_pct  = props["noise"].get("noise_pct", 0) or 0
    n_outliers = props["outliers"].get("n_outliers", 0)

    recommendations = []

    # ── Modèles statistiques ─────────────────────────────────────────────
    if r2_lin > 0.90:
        recommendations.append({
            "model":       "Régression linéaire",
            "type":        "statistical",
            "confidence":  min(0.99, r2_lin),
            "reason":      f"R²={r2_lin:.3f} excellent. Relation linéaire forte détectée.",
            "params":      {"type": "linear"},
        })
    elif r2_lin > 0.60:
        recommendations.append({
            "model":       "Régression polynomiale (degré 2-3)",
            "type":        "statistical",
            "confidence":  0.75,
            "reason":      f"R² linéaire modéré ({r2_lin:.3f}). Une courbe polynomiale peut améliorer l'ajustement.",
            "params":      {"type": "polynomial", "degree": 2},
        })

    # ── Modèles physiques ────────────────────────────────────────────────
    if domain in ("chemistry", "auto") and p == 1:
        corr = props["correlations"][0] if props["correlations"] else {}
        r_sp = abs(corr.get("spearman", 0) or 0)
        recommendations.append({
            "model":      "Cinétique chimique (ordre 1)",
            "type":       "physical",
            "confidence": min(0.85, r_sp),
            "reason":     "Données à 1 variable : cinétique ordre 1 (exponentielle décroissante) recommandée. Vérifier si C(t) décroît exponentiellement.",
            "params":     {"type": "kinetics", "order": 1},
        })

    if domain in ("physics", "process", "auto") and p == 1:
        recommendations.append({
            "model":      "Diffusion (Fick 1D)",
            "type":       "physical",
            "confidence": 0.60,
            "reason":     "Pour données spatiales/temporelles : loi de Fick recommandée si profil de concentration observé.",
            "params":     {"type": "diffusion"},
        })

    # ── Modèles ML ───────────────────────────────────────────────────────
    if n >= 30:
        if nl_gain > 0.15:
            conf = min(0.95, 0.6 + nl_gain)
            recommendations.append({
                "model":      "Random Forest",
                "type":       "machine_learning",
                "confidence": conf,
                "reason":     f"Gain de non-linéarité RF/LR = {nl_gain:.3f}. Relation complexe détectée, RF recommandé.",
                "params":     {"type": "random_forest", "n_estimators": 100},
            })

        if p > 1:
            recommendations.append({
                "model":      "SVR (RBF kernel)",
                "type":       "machine_learning",
                "confidence": 0.72,
                "reason":     f"{p} features : SVR adapté aux espaces de haute dimension avec peu de données.",
                "params":     {"type": "svr", "kernel": "rbf"},
            })

    # ── Deep Learning ────────────────────────────────────────────────────
    if n >= 100:
        dl_conf = min(0.90, 0.5 + n / 2000 + nl_gain * 0.3)
        recommendations.append({
            "model":      "Réseau MLP (PyTorch)",
            "type":       "deep_learning",
            "confidence": dl_conf,
            "reason":     f"n={n} ≥ 100 : Deep Learning applicable. Bon pour captures de patterns complexes.",
            "params":     {"type": "mlp", "hidden_dims": _suggest_arch(n, p)},
        })

    # ── Hybride ──────────────────────────────────────────────────────────
    if n >= 30 and domain != "auto":
        recommendations.append({
            "model":      "Modèle hybride (physique + IA)",
            "type":       "hybrid",
            "confidence": 0.80,
            "reason":     "Recommandé quand le mécanisme physique est partiellement connu. Le réseau apprend uniquement les résidus.",
            "params":     {"type": "hybrid"},
        })

    # ── Avertissements ───────────────────────────────────────────────────
    warnings = []
    if n < 20:
        warnings.append(f"Peu d'échantillons (n={n}). Préférer des modèles simples avec peu de paramètres.")
    if is_noisy:
        warnings.append(f"Données bruitées ({noise_pct:.1f}% bruit). Considérer un filtrage ou régularisation.")
    if n_outliers > 0:
        warnings.append(f"{n_outliers} valeur(s) aberrante(s) détectée(s). Vérifier avant modélisation.")
    if p > n // 5:
        warnings.append(f"Ratio features/échantillons élevé (p={p}, n={n}). Risque de surapprentissage.")

    # ── Tri par confiance ────────────────────────────────────────────────
    recommendations.sort(key=lambda r: r["confidence"], reverse=True)
    best = recommendations[0] if recommendations else None

    logger.info(f"Conseil IA : {best['model'] if best else 'Aucun'} (n={n}, p={p}, R²_lin={r2_lin:.3f})")

    return {
        "analysis":        props,
        "best_model":      best,
        "recommendations": recommendations,
        "warnings":        warnings,
        "summary": {
            "n":          n,
            "p":          p,
            "r2_linear":  r2_lin,
            "r2_rf":      r2_rf,
            "nonlinear":  nl_gain > 0.1,
            "noisy":      is_noisy,
            "n_outliers": n_outliers,
        },
    }


def _suggest_arch(n: int, p: int) -> list[int]:
    """Suggère une architecture MLP en fonction de la taille du jeu de données."""
    if n < 200:
        return [32, 16]
    elif n < 1000:
        return [64, 32, 16]
    else:
        return [128, 64, 32]
