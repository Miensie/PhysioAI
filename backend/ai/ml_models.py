"""
PhysioAI Lab — Machine Learning & Deep Learning Module
Random Forest, SVR, clustering, réseau de neurones PyTorch.
"""

from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline
from typing import Optional

from utils.data_utils import r_squared, rmse, mae


# ══════════════════════════════════════════════════════════════════════════════
# 1. MACHINE LEARNING CLASSIQUE
# ══════════════════════════════════════════════════════════════════════════════

class MLEngine:
    """Random Forest Regressor, GBM, SVR avec validation croisée."""

    def __init__(self):
        self.scaler = StandardScaler()
        self._model = None
        self._model_type = None

    def _build_pipeline(self, model_type: str, **kwargs):
        models = {
            "random_forest": RandomForestRegressor(
                n_estimators=kwargs.get("n_estimators", 100),
                max_depth=kwargs.get("max_depth", None),
                random_state=42,
            ),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=kwargs.get("n_estimators", 100),
                learning_rate=kwargs.get("learning_rate", 0.1),
                random_state=42,
            ),
            "svr": SVR(
                kernel=kwargs.get("kernel", "rbf"),
                C=kwargs.get("C", 1.0),
                epsilon=kwargs.get("epsilon", 0.1),
            ),
        }
        if model_type not in models:
            raise ValueError(f"Modèle ML inconnu: {model_type}")
        return Pipeline([("scaler", StandardScaler()), ("model", models[model_type])])

    def train(self, X: np.ndarray, y: np.ndarray, model_type: str = "random_forest",
              cv_folds: int = 5, **kwargs) -> dict:
        """Entraîne le modèle et retourne les métriques."""
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        pipeline = self._build_pipeline(model_type, **kwargs)
        pipeline.fit(X, y)
        y_pred = pipeline.predict(X)

        # Cross-validation
        cv_scores = cross_val_score(pipeline, X, y, cv=min(cv_folds, len(y)),
                                    scoring="r2")

        self._model = pipeline
        self._model_type = model_type

        result = {
            "model": model_type,
            "r2_train": r_squared(y, y_pred),
            "rmse_train": rmse(y, y_pred),
            "mae_train": mae(y, y_pred),
            "cv_r2_mean": float(cv_scores.mean()),
            "cv_r2_std": float(cv_scores.std()),
            "y_pred": y_pred.tolist(),
        }

        # Feature importances pour RF / GBM
        if hasattr(pipeline["model"], "feature_importances_"):
            result["feature_importances"] = pipeline["model"].feature_importances_.tolist()

        return result

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Le modèle n'est pas encore entraîné.")
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        return self._model.predict(X)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CLUSTERING
# ══════════════════════════════════════════════════════════════════════════════

class ClusteringEngine:
    """K-Means et DBSCAN."""

    def kmeans(self, X: np.ndarray, n_clusters: int = 3) -> dict:
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(Xs)
        return {
            "method": "kmeans",
            "n_clusters": n_clusters,
            "labels": labels.tolist(),
            "centers": scaler.inverse_transform(model.cluster_centers_).tolist(),
            "inertia": float(model.inertia_),
        }

    def dbscan(self, X: np.ndarray, eps: float = 0.5, min_samples: int = 5) -> dict:
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(Xs)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        return {
            "method": "dbscan",
            "n_clusters": n_clusters,
            "labels": labels.tolist(),
            "noise_points": int(np.sum(labels == -1)),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 3. DEEP LEARNING — RÉSEAU DE NEURONES (PyTorch)
# ══════════════════════════════════════════════════════════════════════════════

class PhysioNet(nn.Module):
    """Réseau de neurones dense configurable pour régression."""

    def __init__(self, input_dim: int = 1, hidden_dims: list[int] = None,
                 output_dim: int = 1, dropout: float = 0.1):
        super().__init__()
        hidden_dims = hidden_dims or [64, 64, 32]
        layers = []
        prev = input_dim
        for h in hidden_dims:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, output_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class DeepLearningEngine:
    """Entraînement et prédiction avec PhysioNet (PyTorch)."""

    def __init__(self):
        self.model: Optional[PhysioNet] = None
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.history: list[dict] = []

    def train(self, X: np.ndarray, y: np.ndarray,
              epochs: int = 200, lr: float = 1e-3, batch_size: int = 32,
              hidden_dims: list[int] = None, dropout: float = 0.1) -> dict:
        """Entraîne le réseau de neurones."""

        if X.ndim == 1:
            X = X.reshape(-1, 1)
        y_2d = y.reshape(-1, 1)

        # Normalisation
        Xs = self.scaler_X.fit_transform(X).astype(np.float32)
        ys = self.scaler_y.fit_transform(y_2d).astype(np.float32)

        X_t = torch.tensor(Xs, device=self.device)
        y_t = torch.tensor(ys, device=self.device)

        dataset = TensorDataset(X_t, y_t)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        input_dim = Xs.shape[1]
        self.model = PhysioNet(input_dim, hidden_dims, 1, dropout).to(self.device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=20, factor=0.5)
        criterion = nn.MSELoss()

        self.history = []
        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for xb, yb in loader:
                optimizer.zero_grad()
                pred = self.model(xb)
                loss = criterion(pred, yb)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                epoch_loss += loss.item() * len(xb)
            avg_loss = epoch_loss / len(dataset)
            scheduler.step(avg_loss)
            if epoch % max(1, epochs // 20) == 0:
                self.history.append({"epoch": epoch, "loss": avg_loss})

        # Métriques finales
        self.model.eval()
        with torch.no_grad():
            y_pred_s = self.model(X_t).cpu().numpy()
        y_pred = self.scaler_y.inverse_transform(y_pred_s).flatten()

        return {
            "model": "neural_network",
            "architecture": f"Input({input_dim}) → {hidden_dims or [64,64,32]} → Output(1)",
            "epochs": epochs,
            "final_loss": self.history[-1]["loss"] if self.history else None,
            "r2": r_squared(y, y_pred),
            "rmse": rmse(y, y_pred),
            "mae": mae(y, y_pred),
            "y_pred": y_pred.tolist(),
            "training_history": self.history,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Le modèle n'est pas encore entraîné.")
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        self.model.eval()
        Xs = self.scaler_X.transform(X).astype(np.float32)
        X_t = torch.tensor(Xs, device=self.device)
        with torch.no_grad():
            y_pred_s = self.model(X_t).cpu().numpy()
        return self.scaler_y.inverse_transform(y_pred_s).flatten()


# ══════════════════════════════════════════════════════════════════════════════
# 4. HYBRID MODELING — Physics-Informed Neural Network (simplifié)
# ══════════════════════════════════════════════════════════════════════════════

class HybridModel:
    """
    Modèle hybride : prédiction = modèle_physique(x, params) + correction_NN(x)
    Le réseau apprend la correction résiduelle.
    """

    def __init__(self, physical_func, p0: list[float]):
        self.physical_func = physical_func    # ex: lambda x, k: C0*exp(-k*x)
        self.p0 = p0
        self.physical_params = None
        self.dl_engine = DeepLearningEngine()

    def train(self, x: np.ndarray, y: np.ndarray, epochs: int = 150, **kw) -> dict:
        from scipy.optimize import curve_fit
        # 1) Calibration du modèle physique
        popt, _ = curve_fit(self.physical_func, x, y, p0=self.p0, maxfev=10000)
        self.physical_params = popt
        y_physical = self.physical_func(x, *popt)

        # 2) Résidus = ce que le modèle physique ne capture pas
        residuals = y - y_physical

        # 3) Le NN apprend les résidus
        dl_result = self.dl_engine.train(x, residuals, epochs=epochs, **kw)

        # 4) Prédiction hybride
        y_correction = self.dl_engine.predict(x)
        y_hybrid = y_physical + y_correction

        return {
            "model": "hybrid",
            "physical_params": {f"p{i}": float(v) for i, v in enumerate(popt)},
            "physical_r2": r_squared(y, y_physical),
            "hybrid_r2": r_squared(y, y_hybrid),
            "hybrid_rmse": rmse(y, y_hybrid),
            "hybrid_mae": mae(y, y_hybrid),
            "nn_details": dl_result,
            "y_physical": y_physical.tolist(),
            "y_hybrid": y_hybrid.tolist(),
            "residuals": residuals.tolist(),
        }

    def predict(self, x: np.ndarray) -> np.ndarray:
        y_physical = self.physical_func(x, *self.physical_params)
        y_correction = self.dl_engine.predict(x)
        return y_physical + y_correction
