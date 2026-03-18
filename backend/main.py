"""
================================================================
PhysioAI Lab — main.py (version corrigée pour Render.com)

Correction clé : ajout de sys.path pour que Python trouve
les modules api/, modeling/, ai/, etc. peu importe depuis
quel répertoire uvicorn est lancé.
================================================================
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

# ── CORRECTION CRITIQUE : ajouter le répertoire backend/ au sys.path ─────────
# Nécessaire quand uvicorn est lancé depuis la racine du repo (cas Render/Railway)
# Exemple :  uvicorn backend.main:app  →  sys.path ne contient pas backend/
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
# ─────────────────────────────────────────────────────────────────────────────

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

# ── Configuration ─────────────────────────────────────────────────────────────
ENVIRONMENT  = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")

# CORS : en prod, autoriser GitHub Pages + Excel Online
if ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        o for o in [
            FRONTEND_URL,
            "https://excel.officeapps.live.com",
            "https://*.microsoft.com",
            "https://*.office.com",
        ] if o
    ]
    ALLOW_ORIGIN_REGEX = r"https://.*\.github\.io"
else:
    ALLOWED_ORIGINS    = ["*"]
    ALLOW_ORIGIN_REGEX = None

logger.info(f"Environnement : {ENVIRONMENT} | PYTHONPATH contient : {_BACKEND_DIR}")

# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 PhysioAI Lab démarré")
    yield
    logger.info("🛑 PhysioAI Lab arrêté")

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="PhysioAI Lab API",
    description="Modélisation physico-chimique + IA + Deep Learning",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
cors_kwargs = dict(
    allow_origins     = ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["GET", "POST", "OPTIONS"],
    allow_headers     = ["Content-Type", "Authorization", "Accept"],
    max_age           = 600,
)
if ALLOW_ORIGIN_REGEX:
    cors_kwargs["allow_origin_regex"] = ALLOW_ORIGIN_REGEX

app.add_middleware(CORSMiddleware, **cors_kwargs)

# ── Timing ────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def timing(request: Request, call_next):
    t0       = time.perf_counter()
    response = await call_next(request)
    elapsed  = time.perf_counter() - t0
    response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.3f}s)")
    return response

# ── Error handler ─────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    logger.error(f"Erreur sur {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc)})

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(router_analyze,  prefix="/analyze",  tags=["Analyse"])
app.include_router(router_model,    prefix="/model",    tags=["Modèle"])
app.include_router(router_simulate, prefix="/simulate", tags=["Simulation"])
app.include_router(router_train,    prefix="/train_ai", tags=["IA/DL"])
app.include_router(router_predict,  prefix="/predict",  tags=["Prédiction"])
app.include_router(router_optimize, prefix="/optimize", tags=["Optimisation"])

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Système"])
async def health():
    import torch, sklearn, numpy, scipy
    return {
        "status":      "ok",
        "environment": ENVIRONMENT,
        "version":     "2.0.0",
        "python_path": _BACKEND_DIR,
        "libs": {
            "numpy":   numpy.__version__,
            "scipy":   scipy.__version__,
            "sklearn": sklearn.__version__,
            "torch":   torch.__version__,
            "cuda":    torch.cuda.is_available(),
        },
    }

@app.get("/", tags=["Système"])
async def root():
    return {"app": "PhysioAI Lab", "status": "running", "version": "2.0.0"}

# ── Lancement ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host    = "0.0.0.0",
        port    = port,
        reload  = (ENVIRONMENT == "development"),
    )