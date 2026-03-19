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
