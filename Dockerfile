# ================================================================
# Dockerfile — PhysioAI Lab Backend
# Utilisable sur : Railway, Fly.io, VPS (Docker), Google Cloud Run
#
# Build  : docker build -t physioai-backend .
# Run    : docker run -p 8000:8000 physioai-backend
# ================================================================

FROM python:3.11-slim

# Métadonnées
LABEL maintainer="PhysioAI Lab"
LABEL version="2.0.0"
LABEL description="Backend FastAPI — Modélisation physico-chimique + IA"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=production

# Répertoire de travail
WORKDIR /app

# Installer les dépendances système (pour scipy/numpy)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python en premier (cache Docker)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY backend/ .

# Utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 physioai && chown -R physioai /app
USER physioai

# Exposer le port
EXPOSE 8000

# Health check Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Commande de démarrage
CMD uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2
