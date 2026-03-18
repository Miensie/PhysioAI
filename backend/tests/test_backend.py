"""
================================================================
tests/test_backend.py
Suite de tests complète pour PhysioAI Lab
Exécuter : pytest tests/ -v
================================================================
"""

import math
import numpy as np
import pytest
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.main import app

client = TestClient(app)

# ── Données de test ───────────────────────────────────────────────────────────
np.random.seed(42)
N = 40
T_TEST  = np.linspace(0, 10, N).tolist()
C_TEST  = (np.exp(-0.3 * np.array(T_TEST)) + np.random.normal(0, 0.02, N)).tolist()
X_MULTI = [[t, t**2] for t in T_TEST]
Y_MULTI = C_TEST


# ══════════════════════════════════════════════════════════════════════════════
#  SANTÉ
# ══════════════════════════════════════════════════════════════════════════════

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert "torch" in d["libs"]
    assert "sklearn" in d["libs"]


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSE
# ══════════════════════════════════════════════════════════════════════════════

def test_stats():
    r = client.post("/analyze/stats", json={"data": {"t": T_TEST, "C": C_TEST}})
    assert r.status_code == 200
    d = r.json()["results"]
    assert "t" in d and "C" in d
    assert abs(d["t"]["mean"] - np.mean(T_TEST)) < 0.01

def test_correlation():
    r = client.post("/analyze/correlation", json={"data": {"t": T_TEST, "C": C_TEST}})
    assert r.status_code == 200
    d = r.json()["results"]
    assert "pearson" in d
    assert abs(d["pearson"]["t"]["C"]) > 0.8   # forte corrélation négative

def test_recommend():
    r = client.post("/analyze/recommend", json={
        "data": {"t": T_TEST, "C": C_TEST},
        "target": "C",
        "domain": "chemistry",
    })
    assert r.status_code == 200
    d = r.json()
    assert "recommendations" in d
    assert len(d["recommendations"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
#  RÉGRESSION
# ══════════════════════════════════════════════════════════════════════════════

def test_linear_regression():
    x = np.linspace(0, 10, 30).tolist()
    y = (2.5 * np.array(x) + 1.0 + np.random.normal(0, 0.1, 30)).tolist()
    r = client.post("/model/regression", json={"x": x, "y": y, "type": "linear"})
    assert r.status_code == 200
    d = r.json()
    assert d["r2"] > 0.98
    assert abs(d["slope"] - 2.5) < 0.2

def test_polynomial_regression():
    x = np.linspace(-2, 2, 40).tolist()
    y = (x_i**2 - 2*x_i + 1 for x_i in x)
    y = [yi + np.random.normal(0, 0.1) for yi in y]
    r = client.post("/model/regression", json={"x": x, "y": y, "type": "polynomial", "degree": 2})
    assert r.status_code == 200
    assert r.json()["r2"] > 0.95

def test_ridge_regression():
    r = client.post("/model/regression", json={"x": T_TEST, "y": C_TEST, "type": "ridge", "alpha": 0.5, "degree": 3})
    assert r.status_code == 200
    assert r.json()["r2"] > 0.9


# ══════════════════════════════════════════════════════════════════════════════
#  MODÈLES PHYSIQUES
# ══════════════════════════════════════════════════════════════════════════════

def test_kinetics_order1_calibration():
    r = client.post("/model/physics", json={
        "model": "kinetics",
        "t": T_TEST, "C": C_TEST,
        "order": 1, "C0_guess": 1.0, "k_guess": 0.1,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["params"]["k"] > 0
    assert d["r2"] > 0.90

def test_kinetics_order0():
    t = np.linspace(0, 5, 20).tolist()
    C = [max(1.0 - 0.2*ti + np.random.normal(0, 0.02), 0) for ti in t]
    r = client.post("/model/physics", json={"model": "kinetics", "t": t, "C": C, "order": 0, "C0_guess": 1.0, "k_guess": 0.2})
    assert r.status_code == 200
    assert r.json()["r2"] > 0.85

def test_batch_reactor():
    r = client.post("/model/physics", json={
        "model": "batch_reactor", "order": 1,
        "C0_guess": 1.0, "k_guess": 0.3, "t_end": 20.0, "V": 2.0,
    })
    assert r.status_code == 200
    d = r.json()
    assert len(d["t"]) > 10
    assert d["conversion"][-1] > 0.9

def test_diffusion():
    r = client.post("/model/physics", json={
        "model": "diffusion", "D": 1e-9,
        "C_surface": 1.0, "x_max": 1e-3,
        "t_values": [10, 100, 1000],
    })
    assert r.status_code == 200
    d = r.json()
    assert "profiles" in d

def test_cooling():
    t = np.linspace(0, 200, 30).tolist()
    T_obs = [20 + 80*math.exp(-0.04*ti) + np.random.normal(0, 0.5) for ti in t]
    r = client.post("/model/physics", json={
        "model": "cooling", "T0": 100.0, "T_env": 20.0, "h": 0.04,
        "t_obs": t, "T_data": T_obs, "t_end": 200.0,
    })
    assert r.status_code == 200
    assert r.json()["r2"] > 0.95


# ══════════════════════════════════════════════════════════════════════════════
#  SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

def test_simulate_kinetics():
    r = client.post("/simulate/", json={
        "model": "kinetics",
        "params": {"C0": 1.0, "k": 0.3, "order": 1},
        "t_start": 0.0, "t_end": 20.0, "n_points": 100,
    })
    assert r.status_code == 200
    d = r.json()
    assert len(d["t_sim"]) == 100

def test_simulate_batch():
    r = client.post("/simulate/", json={
        "model": "batch_reactor",
        "params": {"C0": 2.0, "k": 0.5, "order": 2, "V": 1.0},
        "t_end": 30.0, "n_points": 150,
    })
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
#  MACHINE LEARNING
# ══════════════════════════════════════════════════════════════════════════════

def test_random_forest():
    r = client.post("/train_ai/ml", json={
        "X": X_MULTI, "y": Y_MULTI,
        "model": "random_forest", "n_estimators": 50, "cv_folds": 3,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["r2"] > 0.85
    assert "feature_importance" in d

def test_svr():
    r = client.post("/train_ai/ml", json={
        "X": X_MULTI, "y": Y_MULTI,
        "model": "svr", "kernel": "rbf", "C": 10.0,
    })
    assert r.status_code == 200
    assert r.json()["r2"] > 0.80

def test_gradient_boosting():
    r = client.post("/train_ai/ml", json={
        "X": X_MULTI, "y": Y_MULTI,
        "model": "gradient_boosting", "n_estimators": 50, "learning_rate": 0.1,
    })
    assert r.status_code == 200
    assert r.json()["r2"] > 0.85

def test_kmeans():
    X_clust = [[np.random.normal(i*3, 0.5), np.random.normal(i*3, 0.5)] for i in [0,1,2] for _ in range(20)]
    r = client.post("/train_ai/ml", json={"X": X_clust, "y": [0]*60, "model": "kmeans", "k": 3})
    assert r.status_code == 200
    d = r.json()
    assert d["k"] == 3
    assert d["silhouette"] > 0.5


# ══════════════════════════════════════════════════════════════════════════════
#  DEEP LEARNING
# ══════════════════════════════════════════════════════════════════════════════

def test_mlp_training():
    r = client.post("/train_ai/dl", json={
        "X": X_MULTI, "y": Y_MULTI,
        "model": "mlp",
        "hidden_dims": [32, 16],
        "lr": 1e-3, "epochs": 100, "patience": 20,
    })
    assert r.status_code == 200
    d = r.json()
    assert "r2" in d
    assert "history" in d
    assert len(d["history"]["train_loss"]) > 0

def test_hybrid_model():
    r = client.post("/train_ai/dl", json={
        "X": [[t] for t in T_TEST],
        "y": C_TEST,
        "model": "hybrid",
        "physics_model": "kinetics",
        "physics_params": {"C0": 1.0, "k": 0.25, "order": 1},
        "hidden_dims": [16, 8],
        "epochs": 80, "patience": 20,
    })
    assert r.status_code == 200
    d = r.json()
    assert "r2_physics_only" in d
    assert "y_residual_nn" in d


# ══════════════════════════════════════════════════════════════════════════════
#  OPTIMISATION
# ══════════════════════════════════════════════════════════════════════════════

def test_calibrate_curve_fit():
    r = client.post("/optimize/calibrate", json={
        "physics_model": "kinetics",
        "x_data": T_TEST, "y_data": C_TEST,
        "param_names": ["C0", "k"],
        "p0": [1.0, 0.1],
        "bounds_min": [0, 1e-6], "bounds_max": [10, 10],
        "method": "curve_fit",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["r2"] > 0.90
    assert abs(d["params"]["k"] - 0.3) < 0.1

def test_calibrate_nelder_mead():
    r = client.post("/optimize/calibrate", json={
        "physics_model": "kinetics",
        "x_data": T_TEST, "y_data": C_TEST,
        "param_names": ["C0", "k"],
        "p0": [1.0, 0.2],
        "method": "nelder_mead",
    })
    assert r.status_code == 200
    assert r.json()["r2"] > 0.88

def test_auto_optimize():
    r = client.post("/optimize/auto", params={
        "model": "kinetics",
        "method": "curve_fit",
    }, json={"x_data": T_TEST, "y_data": C_TEST})
    # auto_optimize prend les params en query pour simplicité
    # test avec POST direct
    import json
    resp = client.post(
        "/optimize/auto",
        content=json.dumps({"x_data": T_TEST, "y_data": C_TEST}),
        headers={"Content-Type": "application/json"},
        params={"model": "kinetics", "method": "curve_fit"},
    )
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
#  PRÉDICTION
# ══════════════════════════════════════════════════════════════════════════════

def test_predict_linear():
    r = client.post("/predict/", json={
        "X_new": [[1.0], [2.0], [3.0]],
        "model_type": "linear",
        "slope": 2.5, "intercept": 1.0,
    })
    assert r.status_code == 200
    d = r.json()
    assert len(d["y_pred"]) == 3
    assert abs(d["y_pred"][0] - 3.5) < 0.01

def test_predict_kinetics():
    r = client.post("/predict/", json={
        "X_new": [[0.0], [1.0], [5.0]],
        "model_type": "kinetics",
        "C0": 1.0, "k": 0.3, "order": 1,
    })
    assert r.status_code == 200
    d = r.json()
    # C(0) ≈ 1.0, C(5) ≈ exp(-1.5) ≈ 0.22
    assert abs(d["y_pred"][0] - 1.0) < 0.01
    assert abs(d["y_pred"][2] - math.exp(-1.5)) < 0.05
