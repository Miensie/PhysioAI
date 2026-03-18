"""
================================================================
utils/statistics.py
Analyse statistique descriptive et corrélations.
================================================================
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import (
    f_oneway,
    kendalltau,
    kruskal,
    pearsonr,
    shapiro,
    skew,
    kurtosis,
    spearmanr,
    ttest_ind,
)

logger = logging.getLogger("physioai.stats")


def descriptive_stats(data: dict[str, list]) -> dict[str, Any]:
    """
    Calcule les statistiques descriptives complètes pour chaque variable.

    Args:
        data : {nom_colonne: [valeurs...]}
    """
    results = {}

    for col, values in data.items():
        arr = np.asarray(values, dtype=np.float64)
        arr = arr[np.isfinite(arr)]  # exclure NaN / Inf
        n   = len(arr)

        if n == 0:
            results[col] = {"error": "Aucune donnée valide"}
            continue

        q1, q2, q3 = np.percentile(arr, [25, 50, 75])
        iqr         = q3 - q1

        # Test de normalité (Shapiro si n ≤ 5000)
        is_normal, p_normal = None, None
        if n >= 3:
            try:
                _, p_normal = shapiro(arr[:5000])
                is_normal   = bool(p_normal > 0.05)
            except Exception:
                pass

        # Outliers IQR
        lo_fence  = q1 - 1.5 * iqr
        hi_fence  = q3 + 1.5 * iqr
        n_outliers = int(np.sum((arr < lo_fence) | (arr > hi_fence)))

        results[col] = {
            "n":            n,
            "mean":         float(np.mean(arr)),
            "std":          float(np.std(arr, ddof=1)),
            "variance":     float(np.var(arr, ddof=1)),
            "se":           float(np.std(arr, ddof=1) / np.sqrt(n)),
            "min":          float(arr.min()),
            "max":          float(arr.max()),
            "range":        float(arr.max() - arr.min()),
            "q1":           float(q1),
            "median":       float(q2),
            "q3":           float(q3),
            "iqr":          float(iqr),
            "skewness":     float(skew(arr)),
            "kurtosis":     float(kurtosis(arr)),
            "cv":           float(np.std(arr, ddof=1) / (abs(np.mean(arr)) + 1e-10) * 100),
            "is_normal":    is_normal,
            "p_normal":     float(p_normal) if p_normal is not None else None,
            "n_outliers":   n_outliers,
            "lower_fence":  float(lo_fence),
            "upper_fence":  float(hi_fence),
        }

    return results


def correlation_matrix(data: dict[str, list]) -> dict[str, Any]:
    """
    Calcule la matrice de corrélation (Pearson + Spearman) pour toutes les paires.
    """
    df   = pd.DataFrame({k: np.asarray(v, dtype=np.float64) for k, v in data.items()})
    df   = df.dropna()
    cols = list(df.columns)
    n    = len(df)

    pearson_mat  = {}
    spearman_mat = {}
    p_pearson    = {}
    p_spearman   = {}

    for c1 in cols:
        pearson_mat[c1]  = {}
        spearman_mat[c1] = {}
        p_pearson[c1]    = {}
        p_spearman[c1]   = {}
        for c2 in cols:
            if c1 == c2:
                pearson_mat[c1][c2]  = 1.0
                spearman_mat[c1][c2] = 1.0
                p_pearson[c1][c2]    = 0.0
                p_spearman[c1][c2]   = 0.0
            else:
                try:
                    r_p, p_p = pearsonr(df[c1], df[c2])
                    r_s, p_s = spearmanr(df[c1], df[c2])
                    pearson_mat[c1][c2]  = float(r_p)
                    spearman_mat[c1][c2] = float(r_s)
                    p_pearson[c1][c2]    = float(p_p)
                    p_spearman[c1][c2]   = float(p_s)
                except Exception:
                    pearson_mat[c1][c2] = spearman_mat[c1][c2] = None

    # Paires les plus corrélées
    strong = []
    for i, c1 in enumerate(cols):
        for c2 in cols[i+1:]:
            r = pearson_mat.get(c1, {}).get(c2)
            if r is not None:
                strong.append({"pair": [c1, c2], "pearson": r, "strength": abs(r)})
    strong.sort(key=lambda x: x["strength"], reverse=True)

    return {
        "columns":       cols,
        "n":             n,
        "pearson":       pearson_mat,
        "spearman":      spearman_mat,
        "p_pearson":     p_pearson,
        "p_spearman":    p_spearman,
        "strong_pairs":  strong[:10],
    }


def hypothesis_tests(
    group1: list, group2: list,
    test: str = "ttest",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Tests statistiques sur deux groupes :
    - t-test de Student
    - Test de Mann-Whitney (non-paramétrique)
    - Test de Kruskal-Wallis (plusieurs groupes)
    """
    g1 = np.asarray(group1, dtype=np.float64)
    g2 = np.asarray(group2, dtype=np.float64)

    if test == "ttest":
        stat, p = ttest_ind(g1, g2)
        name = "t-test de Student"
    elif test == "kruskal":
        stat, p = kruskal(g1, g2)
        name = "Test de Kruskal-Wallis"
    else:
        raise ValueError(f"Test '{test}' non supporté.")

    effect_size = float((g1.mean() - g2.mean()) / (np.sqrt((g1.std()**2 + g2.std()**2) / 2) + 1e-10))

    return {
        "test":           name,
        "statistic":      float(stat),
        "p_value":        float(p),
        "alpha":          alpha,
        "significant":    bool(p < alpha),
        "effect_size_d":  effect_size,
        "group1_mean":    float(g1.mean()),
        "group2_mean":    float(g2.mean()),
        "group1_std":     float(g1.std(ddof=1)),
        "group2_std":     float(g2.std(ddof=1)),
        "interpretation": _interpret_p(p, alpha),
    }


def _interpret_p(p: float, alpha: float) -> str:
    if p < 0.001:
        return "Différence hautement significative (p < 0.001)"
    elif p < alpha:
        return f"Différence significative (p = {p:.4f} < {alpha})"
    else:
        return f"Différence non significative (p = {p:.4f} ≥ {alpha})"
