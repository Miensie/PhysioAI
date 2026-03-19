import numpy as np
import pandas as pd
from scipy import stats
from typing import List, Dict, Any
from loguru import logger

def descriptive_stats(data: Dict[str, List[float]]) -> Dict[str, Any]:
    df = pd.DataFrame(data)
    result = {}
    for col in df.columns:
        s = df[col].dropna()
        result[col] = {
            "count": int(s.count()), "mean": round(float(s.mean()),6),
            "std": round(float(s.std()),6), "min": round(float(s.min()),6),
            "q25": round(float(s.quantile(.25)),6), "median": round(float(s.median()),6),
            "q75": round(float(s.quantile(.75)),6), "max": round(float(s.max()),6),
            "skewness": round(float(s.skew()),6), "kurtosis": round(float(s.kurtosis()),6),
            "cv": round(float(s.std()/s.mean()) if s.mean()!=0 else 0, 6),
        }
    return result

def correlation_analysis(data: Dict[str, List[float]]) -> Dict[str, Any]:
    df = pd.DataFrame(data).dropna()
    cols = df.columns.tolist()
    corr_matrix = df.corr(method="pearson").round(6).to_dict()
    pval_matrix = {}
    for c1 in cols:
        pval_matrix[c1] = {}
        for c2 in cols:
            if c1 == c2: pval_matrix[c1][c2] = 0.0
            else:
                _, pval = stats.pearsonr(df[c1], df[c2])
                pval_matrix[c1][c2] = round(float(pval), 6)
    interpretations = {}
    for c1 in cols:
        for c2 in cols:
            if c1 < c2:
                r = corr_matrix[c1][c2]
                strength = "très forte" if abs(r)>.9 else "forte" if abs(r)>.7 else "modérée" if abs(r)>.5 else "faible"
                direction = "positive" if r > 0 else "négative"
                interpretations[f"{c1}_vs_{c2}"] = f"Corrélation {strength} {direction} (r={r:.4f})"
    return {"pearson_matrix": corr_matrix, "pvalue_matrix": pval_matrix,
            "interpretations": interpretations, "columns": cols}

def normality_test(data: List[float]) -> Dict[str, Any]:
    arr = np.array(data)
    sw_stat, sw_p = stats.shapiro(arr[:5000])
    jb_stat, jb_p = stats.jarque_bera(arr)
    return {
        "shapiro_wilk": {"statistic": round(float(sw_stat),6), "pvalue": round(float(sw_p),6), "normal": bool(sw_p>0.05)},
        "jarque_bera":  {"statistic": round(float(jb_stat),6), "pvalue": round(float(jb_p),6), "normal": bool(jb_p>0.05)},
    }
