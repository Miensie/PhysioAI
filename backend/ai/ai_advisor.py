"""
PhysioAI Lab — AI Advisor Module
Analyse les données, détecte patterns et recommande le modèle optimal.
Retourne un rapport structuré avec explications.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.metrics import r2_score
from typing import Any


class AIAdvisor:
    """
    Analyse automatique des données et recommandation de modèle.
    Détecte : linéarité, bruit, complexité, outliers, tendances.
    """

    def analyze(self, x: np.ndarray, y: np.ndarray) -> dict:
        """Point d'entrée principal — retourne un rapport complet."""
        report = {}

        # ── 1. Stats descriptives ─────────────────────────────────────────
        report["descriptive_stats"] = self._descriptive(x, y)

        # ── 2. Détection de linéarité ─────────────────────────────────────
        report["linearity"] = self._check_linearity(x, y)

        # ── 3. Détection du bruit ─────────────────────────────────────────
        report["noise"] = self._estimate_noise(x, y)

        # ── 4. Complexité / non-linéarité ─────────────────────────────────
        report["complexity"] = self._check_complexity(x, y)

        # ── 5. Outliers ───────────────────────────────────────────────────
        report["outliers"] = self._detect_outliers(y)

        # ── 6. Tendances (monotonie, périodicité) ─────────────────────────
        report["trends"] = self._detect_trends(x, y)

        # ── 7. Corrélation ────────────────────────────────────────────────
        report["correlation"] = self._compute_correlation(x, y)

        # ── 8. Recommandations ────────────────────────────────────────────
        report["recommendations"] = self._recommend(report)

        return report

    # ─── Méthodes d'analyse ──────────────────────────────────────────────────

    def _descriptive(self, x: np.ndarray, y: np.ndarray) -> dict:
        def stats_for(arr, name):
            return {
                f"{name}_mean": float(np.mean(arr)),
                f"{name}_std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0,
                f"{name}_min": float(np.min(arr)),
                f"{name}_max": float(np.max(arr)),
                f"{name}_range": float(np.max(arr) - np.min(arr)),
                f"{name}_cv": float(np.std(arr, ddof=1) / np.mean(arr)) if np.mean(arr) != 0 else None,
            }
        return {
            "n_points": len(x),
            **stats_for(x, "x"),
            **stats_for(y, "y"),
        }

    def _check_linearity(self, x: np.ndarray, y: np.ndarray) -> dict:
        """Compare R² linéaire vs polynomiale deg=3."""
        X = x.reshape(-1, 1)
        # Linéaire
        lr = LinearRegression().fit(X, y)
        r2_lin = float(r2_score(y, lr.predict(X)))
        # Polynomiale degré 3
        poly_pipe = make_pipeline(PolynomialFeatures(3), LinearRegression())
        poly_pipe.fit(X, y)
        r2_poly = float(r2_score(y, poly_pipe.predict(X)))
        # Test de Pearson
        pearson_r, pearson_p = stats.pearsonr(x, y)
        is_linear = r2_lin > 0.90 and abs(r2_poly - r2_lin) < 0.05
        return {
            "r2_linear": r2_lin,
            "r2_polynomial_deg3": r2_poly,
            "pearson_r": float(pearson_r),
            "pearson_p": float(pearson_p),
            "is_linear": is_linear,
            "linearity_score": r2_lin,  # 0→1
        }

    def _estimate_noise(self, x: np.ndarray, y: np.ndarray) -> dict:
        """Estime le niveau de bruit via les résidus du modèle linéaire."""
        X = x.reshape(-1, 1)
        lr = LinearRegression().fit(X, y)
        residuals = y - lr.predict(X)
        snr = float(np.var(lr.predict(X)) / (np.var(residuals) + 1e-12))
        noise_level = "low" if snr > 10 else "medium" if snr > 2 else "high"
        return {
            "residuals_std": float(np.std(residuals)),
            "snr_db": float(10 * np.log10(snr + 1e-12)),
            "snr_ratio": snr,
            "noise_level": noise_level,
        }

    def _check_complexity(self, x: np.ndarray, y: np.ndarray) -> dict:
        """R² pour différents degrés polynomiaux — indicateur de complexité."""
        X = x.reshape(-1, 1)
        r2_by_degree = {}
        for deg in [1, 2, 3, 4, 5]:
            try:
                pipe = make_pipeline(PolynomialFeatures(deg), LinearRegression())
                pipe.fit(X, y)
                r2_by_degree[deg] = float(r2_score(y, pipe.predict(X)))
            except Exception:
                r2_by_degree[deg] = None

        # Complexité basée sur le degré nécessaire pour R²>0.95
        complexity_score = 1
        for deg, r2 in r2_by_degree.items():
            if r2 and r2 > 0.95:
                complexity_score = deg
                break

        return {
            "r2_by_degree": r2_by_degree,
            "optimal_polynomial_degree": complexity_score,
            "complexity_label": "low" if complexity_score <= 1 else "medium" if complexity_score <= 3 else "high",
        }

    def _detect_outliers(self, y: np.ndarray) -> dict:
        """Détection des outliers via Z-score et IQR."""
        z_scores = np.abs(stats.zscore(y))
        z_outliers = int(np.sum(z_scores > 3))
        Q1, Q3 = np.percentile(y, 25), np.percentile(y, 75)
        IQR = Q3 - Q1
        iqr_outliers = int(np.sum((y < Q1 - 1.5 * IQR) | (y > Q3 + 1.5 * IQR)))
        return {
            "z_score_outliers": z_outliers,
            "iqr_outliers": iqr_outliers,
            "has_outliers": z_outliers > 0 or iqr_outliers > 0,
            "outlier_fraction": float(max(z_outliers, iqr_outliers) / len(y)),
        }

    def _detect_trends(self, x: np.ndarray, y: np.ndarray) -> dict:
        """Détection de monotonie et de la direction de tendance."""
        spearman_r, spearman_p = stats.spearmanr(x, y)
        is_monotone = abs(spearman_r) > 0.85
        kendall_tau, kendall_p = stats.kendalltau(x, y)
        return {
            "spearman_r": float(spearman_r),
            "spearman_p": float(spearman_p),
            "kendall_tau": float(kendall_tau),
            "kendall_p": float(kendall_p),
            "is_monotone": is_monotone,
            "trend_direction": "increasing" if spearman_r > 0 else "decreasing",
        }

    def _compute_correlation(self, x: np.ndarray, y: np.ndarray) -> dict:
        pearson_r, pearson_p = stats.pearsonr(x, y)
        spearman_r, spearman_p = stats.spearmanr(x, y)
        return {
            "pearson_r": float(pearson_r),
            "pearson_r2": float(pearson_r ** 2),
            "pearson_p": float(pearson_p),
            "spearman_r": float(spearman_r),
            "spearman_p": float(spearman_p),
            "correlation_strength": (
                "very_strong" if abs(pearson_r) > 0.9
                else "strong" if abs(pearson_r) > 0.7
                else "moderate" if abs(pearson_r) > 0.5
                else "weak"
            ),
        }

    # ─── Recommandations ─────────────────────────────────────────────────────

    def _recommend(self, report: dict) -> dict:
        lin = report["linearity"]
        noise = report["noise"]
        complexity = report["complexity"]
        outliers = report["outliers"]
        n = report["descriptive_stats"]["n_points"]

        recommendations = []

        # ── Régression ──────────────────────────────────────────────────────
        if lin["is_linear"]:
            recommendations.append({
                "type": "regression",
                "model": "linear",
                "confidence": "high",
                "reason": f"R²={lin['r2_linear']:.3f} — relation quasi-linéaire détectée.",
            })
        elif complexity["optimal_polynomial_degree"] <= 3:
            recommendations.append({
                "type": "regression",
                "model": "polynomial",
                "params": {"degree": complexity["optimal_polynomial_degree"]},
                "confidence": "high",
                "reason": f"Degré polynomial optimal = {complexity['optimal_polynomial_degree']}.",
            })
        else:
            recommendations.append({
                "type": "regression",
                "model": "ridge" if n < 100 else "random_forest",
                "confidence": "medium",
                "reason": "Relation complexe — régression régularisée ou ensemble recommandé.",
            })

        # ── Modèle physique ─────────────────────────────────────────────────
        x_range = report["descriptive_stats"]["x_range"]
        y_mean = report["descriptive_stats"]["y_mean"]
        if report["trends"]["is_monotone"] and lin["linearity_score"] < 0.95:
            if report["descriptive_stats"].get("y_min", 0) >= 0:
                recommendations.append({
                    "type": "physical",
                    "model": "chemical_kinetics_order1",
                    "confidence": "medium",
                    "reason": "Décroissance monotone positive — cinétique d'ordre 1 probable (C = C₀·e^{-kt}).",
                })
            recommendations.append({
                "type": "physical",
                "model": "diffusion_fick",
                "confidence": "low",
                "reason": "Tendance monotone compatible avec un processus de diffusion.",
            })

        # ── Deep Learning ───────────────────────────────────────────────────
        if n >= 50 and complexity["complexity_label"] == "high":
            recommendations.append({
                "type": "deep_learning",
                "model": "neural_network",
                "params": {"hidden_dims": [64, 64, 32], "epochs": 300},
                "confidence": "medium",
                "reason": "Données suffisantes et relation complexe — réseau de neurones adapté.",
            })

        # ── Hybride ─────────────────────────────────────────────────────────
        if n >= 30 and noise["noise_level"] in ("medium", "high"):
            recommendations.append({
                "type": "hybrid",
                "model": "physics_informed_nn",
                "confidence": "medium",
                "reason": "Bruit significatif + structure physique possible — modèle hybride recommandé.",
            })

        # Trier par confiance
        order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: order.get(r["confidence"], 3))

        return {
            "primary_recommendation": recommendations[0] if recommendations else None,
            "all_recommendations": recommendations,
            "data_quality": self._rate_data_quality(report, n),
            "warnings": self._generate_warnings(report),
        }

    def _rate_data_quality(self, report: dict, n: int) -> dict:
        score = 100
        if n < 10:
            score -= 30
        elif n < 30:
            score -= 15
        if report["outliers"]["outlier_fraction"] > 0.1:
            score -= 20
        if report["noise"]["noise_level"] == "high":
            score -= 15
        elif report["noise"]["noise_level"] == "medium":
            score -= 5
        return {
            "score": max(0, score),
            "label": "excellent" if score >= 80 else "good" if score >= 60 else "fair" if score >= 40 else "poor",
            "n_points": n,
        }

    def _generate_warnings(self, report: dict) -> list[str]:
        warnings = []
        n = report["descriptive_stats"]["n_points"]
        if n < 10:
            warnings.append(f"⚠️ Seulement {n} points — résultats peu fiables. Augmenter les données.")
        if report["outliers"]["has_outliers"]:
            warnings.append(f"⚠️ {report['outliers']['z_score_outliers']} outliers détectés (Z-score > 3).")
        if report["noise"]["noise_level"] == "high":
            warnings.append("⚠️ Bruit élevé — envisager un filtrage préalable.")
        if report["correlation"]["pearson_p"] > 0.05:
            warnings.append("⚠️ Corrélation x↔y non significative (p > 0.05).")
        return warnings
