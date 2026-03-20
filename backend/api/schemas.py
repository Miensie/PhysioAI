from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class XYData(BaseModel):
    x: List[float]
    y: List[float]

class MultiColumnData(BaseModel):
    data: Dict[str, List[float]]

class RegressionRequest(BaseModel):
    x: List[float]
    y: List[float]
    model_type: str = "auto"
    degree: int = Field(3, ge=2, le=10)
    alpha: float = Field(1.0, gt=0)

class AnalysisRequest(BaseModel):
    data: Dict[str, List[float]]

class KineticsRequest(BaseModel):
    t: List[float]
    C: Optional[List[float]] = None
    C0: float = 1.0
    k: float = 0.1
    order: int = Field(1, ge=0, le=2)
    fit: bool = False

class CSTRRequest(BaseModel):
    t: List[float]
    V: float = 1.0; F: float = 0.1
    C_in: float = 1.0; C0: float = 0.0; k: float = 0.5

class FickRequest(BaseModel):
    x: List[float]
    t: float = 100.0; D: float = 1e-9; C0: float = 0.0; Cs: float = 1.0

class HeatRequest(BaseModel):
    t: List[float]
    T0: float = 100.0; T_inf: float = 20.0; h: float = 10.0
    m: float = 1.0; cp: float = 4186.0

class AIAdvisorRequest(BaseModel):
    x: List[float]; y: List[float]

class MLRequest(BaseModel):
    X: List[List[float]]; y: List[float]
    model_type: str = "random_forest"
    n_estimators: int = 100; n_clusters: int = 3

class DLRequest(BaseModel):
    X: List[List[float]]; y: List[float]
    hidden_layers: List[int] = [64, 32, 16]
    epochs: int = 200; lr: float = 1e-3

class HybridRequest(BaseModel):
    t: List[float]; C: List[float]
    C0: float; k: float; epochs: int = 300

class SimulationRequest(BaseModel):
    model: str; params: Dict[str, Any]
    t_start: float = 0.0; t_end: float = 100.0; n_points: int = 200


# ── Schemas manquants pour les routes physiques ───────────────────────────────

class PFRRequest(BaseModel):
    z: List[float]
    F: float = 1.0
    A: float = 0.1
    C0: float = 1.0
    k: float = 0.1
    order: int = Field(1, ge=0, le=2)

class DarcyRequest(BaseModel):
    dP: float = 1000.0   # Pa
    mu: float = 0.001    # Pa·s (eau à 20°C)
    k_perm: float = 1e-12  # m²
    L: float = 1.0       # m
    A: float = 0.01      # m²

class AntoineRequest(BaseModel):
    T_range: List[float]
    A: float = 8.07131   # Eau (NIST)
    B: float = 1730.63
    C: float = 233.426

class RTDRequest(BaseModel):
    t: List[float]
    tau: float = 10.0
    N: int = Field(3, ge=1, le=20)


# ── Prédiction ────────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    """Prédiction sur de nouvelles valeurs X avec le modèle entraîné en session."""
    X_train:      List[List[float]] = Field(..., description="Données d'entraînement X")
    y_train:      List[float]       = Field(..., description="Données d'entraînement y")
    X_predict:    List[List[float]] = Field(..., description="Nouvelles valeurs X à prédire")
    model_type:   str  = Field("random_forest",
        description="linear|polynomial|ridge|lasso|random_forest|svr|gradient_boosting|mlp")
    degree:       int   = Field(3, ge=2, le=10)
    alpha:        float = Field(1.0, gt=0)
    n_estimators: int   = Field(100, ge=10)
    hidden_layers: List[int] = Field(default=[64, 32, 16])
    epochs:       int   = Field(150, ge=10)
    confidence_interval: bool = Field(True, description="Calcul intervalle de confiance (RF)")


# ── Décision Globale IA ───────────────────────────────────────────────────────

class GlobalDecisionRequest(BaseModel):
    """Envoie toutes les données à Gemini pour une décision globale."""
    x:               List[float]
    y:               List[float]
    gemini_api_key:  str  = Field(..., description="Clé API Google AI Studio")
    context:         str  = Field("",  description="Contexte métier (ex: 'réaction de dégradation')")
    regression_result: Optional[Dict[str, Any]] = None
    physical_result:   Optional[Dict[str, Any]] = None
    ai_advisor_result: Optional[Dict[str, Any]] = None
    language:        str  = Field("fr", description="fr|en")


# ── Prédiction automatique (tous modèles) ─────────────────────────────────────
class PredictBestRequest(BaseModel):
    X_train:   List[List[float]]
    y_train:   List[float]
    X_predict: List[List[float]]
    degree:    int   = Field(3, ge=2, le=10)
    alpha:     float = Field(1.0, gt=0)
