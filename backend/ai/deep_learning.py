"""
================================================================
ai/deep_learning.py
Deep Learning avec PyTorch :
  - Réseau de neurones MLP (régression)
  - PINN (Physics-Informed Neural Network)
  - Modèle hybride : modèle physique + réseau de neurones
================================================================
"""

import logging
import time
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("physioai.dl")

# Utiliser GPU si disponible
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"PyTorch device : {DEVICE}")


# ══════════════════════════════════════════════════════════════════════════════
#  ARCHITECTURES DE RÉSEAUX DE NEURONES
# ══════════════════════════════════════════════════════════════════════════════

class MLP(nn.Module):
    """
    Perceptron Multicouche (MLP) générique.
    Architecture configurable : [in] → [hidden] → ... → [out]
    Avec BatchNorm, Dropout et activation configurable.
    """
    def __init__(
        self,
        input_dim: int,
        hidden_dims: list[int],
        output_dim: int = 1,
        activation: str = "relu",
        dropout: float = 0.0,
        batch_norm: bool = False,
    ):
        super().__init__()
        act_map = {
            "relu":    nn.ReLU(),
            "tanh":    nn.Tanh(),
            "sigmoid": nn.Sigmoid(),
            "silu":    nn.SiLU(),
            "gelu":    nn.GELU(),
        }
        act = act_map.get(activation, nn.ReLU())

        layers = []
        dims   = [input_dim] + hidden_dims

        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i+1]))
            if batch_norm:
                layers.append(nn.BatchNorm1d(dims[i+1]))
            layers.append(act)
            if dropout > 0:
                layers.append(nn.Dropout(dropout))

        layers.append(nn.Linear(dims[-1], output_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ResidualBlock(nn.Module):
    """Bloc résiduel pour réseau plus profond (évite le vanishing gradient)."""
    def __init__(self, dim: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.SiLU(),
            nn.Linear(dim, dim),
        )

    def forward(self, x):
        return x + self.block(x)


class ResNet(nn.Module):
    """Réseau résiduel pour données tabulaires."""
    def __init__(self, input_dim: int, hidden_dim: int, n_blocks: int, output_dim: int = 1):
        super().__init__()
        self.embed  = nn.Linear(input_dim, hidden_dim)
        self.blocks = nn.ModuleList([ResidualBlock(hidden_dim) for _ in range(n_blocks)])
        self.head   = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        x = self.embed(x)
        for b in self.blocks:
            x = b(x)
        return self.head(x)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRAÎNEMENT
# ══════════════════════════════════════════════════════════════════════════════

def _make_tensors(X_np: np.ndarray, y_np: np.ndarray | None = None):
    X_t = torch.tensor(X_np, dtype=torch.float32).to(DEVICE)
    y_t = torch.tensor(y_np, dtype=torch.float32).unsqueeze(1).to(DEVICE) if y_np is not None else None
    return X_t, y_t


def train_mlp(
    X_data: list[list], y_data: list,
    hidden_dims: list[int] | None = None,
    activation: str = "relu",
    dropout: float = 0.1,
    batch_norm: bool = False,
    lr: float = 1e-3,
    epochs: int = 500,
    batch_size: int = 32,
    patience: int = 50,
    architecture: str = "mlp",
) -> dict[str, Any]:
    """
    Entraîne un réseau MLP ou ResNet sur des données tabulaires.

    Args:
        hidden_dims : liste des tailles des couches cachées (ex: [64, 64, 32])
        architecture: "mlp" ou "resnet"
        patience    : early stopping (nb epochs sans amélioration)
    """
    if hidden_dims is None:
        hidden_dims = [64, 64, 32]

    X_np = np.asarray(X_data, dtype=np.float64)
    y_np = np.asarray(y_data, dtype=np.float64).ravel()

    if X_np.ndim == 1:
        X_np = X_np.reshape(-1, 1)

    # Normalisation
    sc_X = StandardScaler()
    sc_y = StandardScaler()
    X_s  = sc_X.fit_transform(X_np).astype(np.float32)
    y_s  = sc_y.fit_transform(y_np.reshape(-1, 1)).ravel().astype(np.float32)

    n, d_in = X_s.shape

    # Construction du modèle
    if architecture == "resnet":
        model = ResNet(d_in, hidden_dims[0], n_blocks=len(hidden_dims)).to(DEVICE)
    else:
        model = MLP(d_in, hidden_dims, 1, activation, dropout, batch_norm).to(DEVICE)

    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=patience//2, factor=0.5)
    criterion = nn.MSELoss()

    X_t, y_t = _make_tensors(X_s, y_s)
    dataset   = torch.utils.data.TensorDataset(X_t, y_t)
    loader    = torch.utils.data.DataLoader(dataset, batch_size=min(batch_size, n), shuffle=True)

    # ── Boucle d'entraînement ──
    history      = {"train_loss": [], "epoch": []}
    best_loss    = float("inf")
    best_weights = None
    no_improve   = 0
    t0           = time.time()

    for epoch in range(epochs):
        model.train()
        epoch_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item() * len(xb)

        epoch_loss /= n
        scheduler.step(epoch_loss)
        history["train_loss"].append(float(epoch_loss))
        history["epoch"].append(epoch)

        # Early stopping
        if epoch_loss < best_loss - 1e-6:
            best_loss    = epoch_loss
            best_weights = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve   = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info(f"Early stopping à l'epoch {epoch}")
                break

    # Restaurer les meilleurs poids
    if best_weights:
        model.load_state_dict(best_weights)

    # ── Évaluation ──
    model.eval()
    with torch.no_grad():
        y_pred_s = model(X_t).cpu().numpy().ravel()

    y_pred = sc_y.inverse_transform(y_pred_s.reshape(-1, 1)).ravel()
    r2     = float(r2_score(y_np, y_pred))
    rmse   = float(np.sqrt(mean_squared_error(y_np, y_pred)))
    mae    = float(np.mean(np.abs(y_np - y_pred)))
    elapsed = time.time() - t0

    logger.info(f"MLP entraîné : R²={r2:.4f}, RMSE={rmse:.4f}, {elapsed:.1f}s, {epoch+1} epochs")

    return {
        "model":        architecture,
        "architecture": hidden_dims,
        "activation":   activation,
        "epochs_done":  epoch + 1,
        "best_loss":    float(best_loss),
        "training_time": elapsed,
        "r2":           r2,
        "rmse":         rmse,
        "mae":          mae,
        "y_true":       y_np.tolist(),
        "y_pred":       y_pred.tolist(),
        "residuals":    (y_np - y_pred).tolist(),
        "history":      history,
        # Sérialisation du modèle (state dict → liste pour JSON)
        "model_state":  {k: v.cpu().tolist() for k, v in model.state_dict().items()},
        "scaler_X":     {"mean": sc_X.mean_.tolist(), "std": sc_X.scale_.tolist()},
        "scaler_y":     {"mean": sc_y.mean_.tolist(), "std": sc_y.scale_.tolist()},
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MODÈLE HYBRIDE — Physique + IA
# ══════════════════════════════════════════════════════════════════════════════

class HybridKineticsNet(nn.Module):
    """
    Modèle hybride : résidu entre données et modèle physique appris par un réseau.

    Structure :
        y_pred = y_physics(x) + NN_residual(x)

    Le réseau apprend uniquement la partie non modélisée par la physique.
    """
    def __init__(self, input_dim: int, hidden_dims: list[int] = None):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [32, 16]
        self.residual_net = MLP(input_dim, hidden_dims, 1, activation="tanh")

    def forward(self, x_norm: torch.Tensor, y_physics_norm: torch.Tensor) -> torch.Tensor:
        delta = self.residual_net(x_norm)
        return y_physics_norm + delta


def train_hybrid_model(
    X_data: list[list], y_data: list,
    physics_fn,         # callable : X_np → y_physics_np
    hidden_dims: list[int] | None = None,
    lr: float = 1e-3, epochs: int = 500, patience: int = 50,
) -> dict[str, Any]:
    """
    Entraîne un modèle hybride physique + réseau de neurones.

    Args:
        physics_fn : fonction Python qui prend X_np et retourne y_physics_np
                     (ex: lambda X: kinetics_order1(X[:,0], C0=1.0, k=0.1))
    """
    X_np = np.asarray(X_data, dtype=np.float64)
    y_np = np.asarray(y_data, dtype=np.float64).ravel()
    if X_np.ndim == 1:
        X_np = X_np.reshape(-1, 1)

    # Prédiction physique
    y_phy = np.asarray(physics_fn(X_np), dtype=np.float64).ravel()
    residual_np = y_np - y_phy  # ce que le réseau doit apprendre

    # Normalisation
    sc_X = StandardScaler(); sc_y = StandardScaler()
    X_s  = sc_X.fit_transform(X_np).astype(np.float32)
    res_s = sc_y.fit_transform(residual_np.reshape(-1, 1)).ravel().astype(np.float32)

    n, d_in = X_s.shape
    model   = MLP(d_in, hidden_dims or [32, 16], 1, "tanh").to(DEVICE)
    opt     = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    crit    = nn.MSELoss()

    X_t   = torch.tensor(X_s).to(DEVICE)
    res_t = torch.tensor(res_s.reshape(-1, 1)).to(DEVICE)

    history  = []
    best_w   = None
    best_l   = float("inf")
    no_imp   = 0

    for epoch in range(epochs):
        model.train()
        opt.zero_grad()
        pred = model(X_t)
        loss = crit(pred, res_t)
        loss.backward()
        opt.step()
        l = float(loss.item())
        history.append(l)
        if l < best_l - 1e-6:
            best_l = l
            best_w = {k: v.clone() for k, v in model.state_dict().items()}
            no_imp = 0
        else:
            no_imp += 1
            if no_imp >= patience:
                break

    if best_w:
        model.load_state_dict(best_w)

    model.eval()
    with torch.no_grad():
        res_pred_s = model(X_t).cpu().numpy().ravel()

    res_pred = sc_y.inverse_transform(res_pred_s.reshape(-1, 1)).ravel()
    y_pred   = y_phy + res_pred

    r2   = float(r2_score(y_np, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_np, y_pred)))

    # Décomposition des contributions
    r2_physics = float(r2_score(y_np, y_phy))

    logger.info(f"Hybride entraîné : R²={r2:.4f} (physique seul: R²={r2_physics:.4f})")

    return {
        "model":           "hybrid_physics_nn",
        "r2":              r2,
        "rmse":            rmse,
        "r2_physics_only": r2_physics,
        "y_true":          y_np.tolist(),
        "y_physics":       y_phy.tolist(),
        "y_residual_nn":   res_pred.tolist(),
        "y_pred_hybrid":   y_pred.tolist(),
        "residuals":       (y_np - y_pred).tolist(),
        "train_loss_curve": history,
        "epochs_done":     epoch + 1,
    }
