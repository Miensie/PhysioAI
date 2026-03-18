"""
================================================================
api/schemas.py
Modèles Pydantic pour la validation des requêtes/réponses API.
================================================================
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Énumérations ─────────────────────────────────────────────────────────────

class RegressionType(str, Enum):
    linear      = "linear"
    polynomial  = "polynomial"
    ridge       = "ridge"
    lasso       = "lasso"
    multivariate = "multivariate"


class PhysicsModel(str, Enum):
    kinetics    = "kinetics"
    diffusion   = "diffusion"
    batch_reactor = "batch_reactor"
    cstr        = "cstr"
    cooling     = "cooling"


class MLModel(str, Enum):
    random_forest      = "random_forest"
    svr                = "svr"
    gradient_boosting  = "gradient_boosting"
    kmeans             = "kmeans"
    dbscan             = "dbscan"


class DLModel(str, Enum):
    mlp    = "mlp"
    resnet = "resnet"
    hybrid = "hybrid"


class OptMethod(str, Enum):
    curve_fit              = "curve_fit"
    nelder_mead            = "nelder_mead"
    differential_evolution = "differential_evolution"


class KineticsOrder(int, Enum):
    zero  = 0
    first = 1
    second = 2


# ── Données communes ──────────────────────────────────────────────────────────

class XYData(BaseModel):
    x: list[float] = Field(..., min_length=3, description="Valeurs de la variable indépendante")
    y: list[float] = Field(..., min_length=3, description="Valeurs de la variable dépendante")

    @field_validator("y")
    @classmethod
    def check_same_length(cls, v, info):
        if "x" in info.data and len(v) != len(info.data["x"]):
            raise ValueError("x et y doivent avoir la même longueur.")
        return v


class MatrixYData(BaseModel):
    X: list[list[float]] = Field(..., description="Matrice de features (n_samples × n_features)")
    y: list[float]        = Field(..., description="Variable cible")
    feature_names: Optional[list[str]] = None

    @field_validator("y")
    @classmethod
    def check_consistency(cls, v, info):
        if "X" in info.data and len(v) != len(info.data["X"]):
            raise ValueError(f"X ({len(info.data['X'])} lignes) et y ({len(v)}) incompatibles.")
        return v


# ── Requêtes Analyse ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    data:         dict[str, list[float]] = Field(..., description="Colonnes de données {nom: [valeurs]}")
    target:       Optional[str]          = Field(None, description="Nom de la colonne cible (y)")
    domain:       str                    = Field("auto", description="Domaine : chemistry | physics | process | auto")
    include_recommendation: bool         = Field(True)


class StatsRequest(BaseModel):
    data: dict[str, list[float]]


class CorrelationRequest(BaseModel):
    data: dict[str, list[float]]


# ── Requêtes Modèle ───────────────────────────────────────────────────────────

class RegressionRequest(BaseModel):
    x:      list[float]
    y:      list[float]
    type:   RegressionType = RegressionType.linear
    degree: int            = Field(2, ge=1, le=10)
    alpha:  float          = Field(1.0, gt=0)


class PhysicsRequest(BaseModel):
    model:    PhysicsModel
    # Cinétique
    t:        Optional[list[float]] = None
    C:        Optional[list[float]] = None
    order:    KineticsOrder         = KineticsOrder.first
    C0_guess: float                 = 1.0
    k_guess:  float                 = 0.1
    t_max:    Optional[float]       = None
    # Diffusion
    D:        float = Field(1e-9, description="Coefficient de diffusion [m²/s]")
    C_surface: float = 1.0
    C_init:    float = 0.0
    x_max:     float = 1e-3
    t_values:  Optional[list[float]] = None
    # Réacteurs
    V:         float = 1.0
    t_end:     float = 100.0
    # Refroidissement
    T0:        float = 100.0
    T_env:     float = 20.0
    h:         float = 0.05
    T_data:    Optional[list[float]] = None
    t_obs:     Optional[list[float]] = None


# ── Requêtes Simulation ───────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    model:     PhysicsModel
    params:    dict[str, float] = Field(default_factory=dict)
    t_start:   float = 0.0
    t_end:     float = 100.0
    n_points:  int   = Field(300, ge=10, le=10000)
    compare_with: Optional[dict] = None  # données observées pour comparaison


# ── Requêtes IA / ML ─────────────────────────────────────────────────────────

class MLRequest(BaseModel):
    X:            list[list[float]]
    y:            list[float]
    model:        MLModel
    # Random Forest
    n_estimators: int   = Field(100, ge=10, le=1000)
    max_depth:    Optional[int] = None
    # SVR
    kernel:       str   = "rbf"
    C:            float = 1.0
    epsilon:      float = 0.1
    # Gradient Boosting
    learning_rate: float = 0.1
    # K-Means
    k:            Optional[int] = None
    # DBSCAN
    eps:          float = 0.5
    min_samples:  int   = 5
    # CV
    cv_folds:     int   = Field(5, ge=2, le=20)


class DLRequest(BaseModel):
    X:            list[list[float]]
    y:            list[float]
    model:        DLModel = DLModel.mlp
    hidden_dims:  list[int] = Field(default_factory=lambda: [64, 32])
    activation:   str   = "relu"
    dropout:      float = Field(0.1, ge=0, le=0.9)
    batch_norm:   bool  = False
    lr:           float = Field(1e-3, gt=0)
    epochs:       int   = Field(500, ge=10, le=5000)
    batch_size:   int   = Field(32, ge=4, le=512)
    patience:     int   = Field(50, ge=5)
    # Hybride
    physics_model: Optional[str] = None
    physics_params: Optional[dict[str, float]] = None


# ── Requêtes Prédiction ───────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    X_new:      list[list[float]] = Field(..., description="Nouvelles données à prédire")
    model_type: str               = Field(..., description="Type de modèle sauvegardé")
    model_id:   Optional[str]     = None


# ── Requêtes Optimisation ─────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    physics_model: PhysicsModel
    x_data:        list[float]
    y_data:        list[float]
    param_names:   list[str]
    p0:            Optional[list[float]] = None
    bounds_min:    Optional[list[float]] = None
    bounds_max:    Optional[list[float]] = None
    method:        OptMethod = OptMethod.curve_fit


class SensitivityRequest(BaseModel):
    physics_model:  PhysicsModel
    base_params:    dict[str, float]
    x_data:         list[float]
    variation_pct:  float = Field(10.0, gt=0, le=100)
