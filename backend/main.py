"""
PhysioAI Lab — Main FastAPI Application
Compatible Render.com : PORT injecté via $PORT, CORS via env var.
"""

import os, sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from api.routes_regression  import router as regression_router
from api.routes_analysis    import router as analysis_router
from api.routes_physical    import router as physical_router
from api.routes_ai          import router as ai_router
from api.routes_simulation  import router as simulation_router
from api.routes_predict     import router as predict_router   # ← NOUVEAU

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL,
           format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
os.makedirs("logs", exist_ok=True)
logger.add("logs/physioai.log", rotation="10 MB", retention="7 days", level="DEBUG")

_raw = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _raw.split(",")] if _raw != "*" else ["*"]

app = FastAPI(
    title="PhysioAI Lab API",
    description=(
        "Backend scientifique pour la modélisation physico-chimique assistée par IA.\n\n"
        "**Nouveautés :** Prédiction sur nouvelles données + Décision globale Gemini AI."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(regression_router,  prefix="/api/v1", tags=["Régression"])
app.include_router(analysis_router,    prefix="/api/v1", tags=["Analyse"])
app.include_router(physical_router,    prefix="/api/v1", tags=["Modèles Physiques"])
app.include_router(ai_router,          prefix="/api/v1", tags=["IA — Entraînement"])
app.include_router(simulation_router,  prefix="/api/v1", tags=["Simulation"])
app.include_router(predict_router,     prefix="/api/v1", tags=["Prédiction & Décision"])  # ← NOUVEAU

@app.get("/", tags=["Santé"])
async def root():
    return {"status": "ok", "app": "PhysioAI Lab", "version": "2.0.0"}

@app.get("/health", tags=["Santé"])
async def health():
    return {"status": "healthy"}

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Erreur non gérée: {exc}")
    return JSONResponse(status_code=500,
        content={"error": "Erreur interne", "detail": str(exc)})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("API_HOST", "0.0.0.0")
    logger.info(f"🚀 PhysioAI Lab v2.0 → http://{host}:{port}/docs")
    uvicorn.run("main:app", host=host, port=port, reload=True)
