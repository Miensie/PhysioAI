"""
================================================================
backend/main.py — Version PRODUCTION
Modifications vs développement :
  - CORS restreint à l'URL GitHub Pages réelle
  - Lecture de FRONTEND_URL depuis variable d'environnement
  - Logs structurés pour les plateformes cloud
================================================================
"""

import logging
import os
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
)
logger = logging.getLogger("physioai")

# ── Configuration ─────────────────────────────────────────────────────────────
ENVIRONMENT  = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")  # ex: https://username.github.io

# Origines autorisées selon l'environnement
if ENVIRONMENT == "production":
    # En production : autoriser l'URL GitHub Pages + Excel Online
    ALLOWED_ORIGINS = [
        o.strip() for o in [
            FRONTEND_URL,
            "https://excel.officeapps.live.com",
            "https://outlook.live.com",
            "https://*.github.io",        # GitHub Pages (tous les sous-domaines)
            "https://*.microsoft.com",    # Excel Online
            "https://*.office.com",
        ] if o.strip()
    ]
else:
    # En développement : tout autoriser
    ALLOWED_ORIGINS = ["*"]

logger.info(f"🌍 Environnement : {ENVIRONMENT}")
logger.info(f"🔗 Origines CORS : {ALLOWED_ORIGINS}")


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 PhysioAI Lab Backend démarré")
    yield
    logger.info("🛑 PhysioAI Lab Backend arrêté")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="PhysioAI Lab API",
    description="Modélisation physico-chimique + IA + Deep Learning",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if ENVIRONMENT != "production" else None,   # Désactiver Swagger en prod si souhaité
    redoc_url="/redoc" if ENVIRONMENT != "production" else None,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.github\.io",   # Match tous les GitHub Pages
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    max_age=600,
)

# ── Timing middleware ─────────────────────────────────────────────────────────
@app.middleware("http")
async def timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
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

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Système"])
async def health():
    import torch, sklearn, numpy, scipy
    return {
        "status":      "ok",
        "environment": ENVIRONMENT,
        "version":     "2.0.0",
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port,
                reload=(ENVIRONMENT == "development"))
