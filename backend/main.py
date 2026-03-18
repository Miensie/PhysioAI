"""
================================================================
PhysioAI Lab — main.py
Point d'entrée FastAPI

Architecture :
  /analyze    → Analyse statistique + conseil IA
  /model      → Régression, modèles physiques
  /simulate   → Simulation ODE / cinétique
  /train_ai   → Entraînement ML / Deep Learning
  /predict    → Prédiction sur nouvelles données
  /optimize   → Optimisation paramètres
================================================================
"""

import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes_analyze   import router as router_analyze
from api.routes_model     import router as router_model
from api.routes_simulate  import router as router_simulate
from api.routes_train     import router as router_train
from api.routes_predict   import router as router_predict
from api.routes_optimize  import router as router_optimize

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("physioai")


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 PhysioAI Lab démarré")
    yield
    logger.info("🛑 PhysioAI Lab arrêté")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="PhysioAI Lab API",
    description="""
## API de modélisation physico-chimique avec IA

Fonctionnalités :
- **Analyse** : statistiques descriptives, corrélation, conseil IA
- **Modélisation** : régression linéaire/polynomiale, modèles physiques
- **Simulation** : ODE, cinétique chimique, diffusion
- **IA/ML** : Random Forest, SVR, Deep Learning PyTorch
- **Hybride** : modèle physique + réseau de neurones
- **Optimisation** : calibration automatique de paramètres
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # En production : ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware de timing ──────────────────────────────────────────────────────
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.3f}s)")
    return response


# ── Gestionnaire d'erreurs global ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Erreur non gérée sur {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Erreur interne du serveur", "detail": str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(router_analyze,  prefix="/analyze",  tags=["Analyse"])
app.include_router(router_model,    prefix="/model",    tags=["Modélisation"])
app.include_router(router_simulate, prefix="/simulate", tags=["Simulation"])
app.include_router(router_train,    prefix="/train_ai", tags=["IA / Deep Learning"])
app.include_router(router_predict,  prefix="/predict",  tags=["Prédiction"])
app.include_router(router_optimize, prefix="/optimize", tags=["Optimisation"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Système"])
async def health():
    import torch, sklearn, numpy, scipy
    return {
        "status": "ok",
        "version": "2.0.0",
        "libs": {
            "numpy":      numpy.__version__,
            "scipy":      scipy.__version__,
            "sklearn":    sklearn.__version__,
            "torch":      torch.__version__,
            "cuda":       torch.cuda.is_available(),
        },
    }


@app.get("/", tags=["Système"])
async def root():
    return {
        "app": "PhysioAI Lab",
        "docs": "/docs",
        "health": "/health",
    }


# ── Lancement ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
