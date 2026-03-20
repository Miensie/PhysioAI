# 🚀 Guide de Déploiement — GitHub + Render

## Vue d'ensemble

```
GitHub (code source)
    └── push sur main
         ├── Render → physioai-lab-api      (Backend FastAPI Python)
         └── Render → physioai-lab-frontend (Frontend statique HTML/JS)
```

---

## ÉTAPE 1 — Préparer le dépôt GitHub

### 1.1 Créer le dépôt

1. Aller sur [github.com/new](https://github.com/new)
2. Nommer le dépôt : `physioai-lab`
3. Visibilité : **Public** (requis pour Render plan gratuit)
4. Ne pas initialiser avec README (vous avez déjà le code)
5. Cliquer **Create repository**

### 1.2 Pousser le code

```bash
# Dans le dossier racine physioai-lab/
git init
git add .
git commit -m "feat: initial PhysioAI Lab"
git branch -M main
git remote add origin https://github.com/miensie/physioAI.git
git push -u origin main
```

---

## ÉTAPE 2 — Déployer sur Render

### 2.1 Créer un compte Render

Aller sur [render.com](https://render.com) → Sign Up avec votre compte GitHub.

---

### 2.2 Déployer le Backend (FastAPI)

1. Dashboard Render → **New** → **Web Service**
2. Connecter votre repo GitHub `physioai-lab`
3. Remplir le formulaire :

| Champ | Valeur |
|-------|--------|
| **Name** | `physioai-lab-api` |
| **Region** | Frankfurt (EU) |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free |

4. Section **Environment Variables** → Add :

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.11.0` |
| `LOG_LEVEL` | `INFO` |
| `CORS_ORIGINS` | `*` *(à restreindre après)* |

5. Cliquer **Create Web Service**
6. ⏳ Attendre le build (~3-5 min)
7. Copier l'URL générée : `https://physioai-lab-api.onrender.com`

> ✅ Tester : `https://physioai-lab-api.onrender.com/health`
> Réponse attendue : `{"status": "healthy"}`

---

### 2.3 Déployer le Frontend (statique)

1. Dashboard Render → **New** → **Static Site**
2. Connecter le même repo GitHub
3. Remplir :

| Champ | Valeur |
|-------|--------|
| **Name** | `physioai-lab-frontend` |
| **Branch** | `main` |
| **Root Directory** | `frontend` |
| **Build Command** | *(laisser vide)* |
| **Publish Directory** | `.` |

4. Cliquer **Create Static Site**
5. Copier l'URL : `https://physioai-lab-frontend.onrender.com`

---

### 2.4 Connecter frontend → backend

Ouvrir `frontend/js/config.js` et remplacer :

```js
const RENDER_API_URL = "https://physioai-lab-api.onrender.com";
```

Par votre URL réelle copiée à l'étape 2.2.

```bash
git add frontend/js/config.js
git commit -m "config: set Render backend URL"
git push
```

Render redéploie automatiquement les deux services.

---

### 2.5 (Optionnel) Restreindre le CORS

Une fois le frontend déployé, aller dans les **Environment Variables** du backend Render et mettre :

| Key | Value |
|-----|-------|
| `CORS_ORIGINS` | `https://physioai-lab-frontend.onrender.com` |

---

## ÉTAPE 3 — Charger l'Add-in dans Excel

### Option A — Excel Online (Office 365)

1. Ouvrir Excel Online
2. **Insérer** → **Compléments** → **Charger un complément**
3. Uploader `frontend/manifest.xml`

### Option B — Excel Desktop (Windows/Mac)

1. Ouvrir Excel
2. **Fichier** → **Options** → **Centre de gestion de la confidentialité** → **Catalogues de compléments approuvés**
3. Ajouter l'URL : `https://physioai-lab-frontend.onrender.com`
4. **Insérer** → **Mes compléments** → PhysioAI Lab

> 📝 Dans `manifest.xml`, remplacer toutes les occurrences de
> `https://localhost:3000` par `https://physioai-lab-frontend.onrender.com`

---

## ÉTAPE 4 — Mise à jour du manifest.xml pour la production

```bash
# Remplacer l'URL localhost par l'URL Render du frontend
sed -i 's|https://localhost:3000|https://physioai-lab-frontend.onrender.com|g' \
    frontend/manifest.xml

git add frontend/manifest.xml
git commit -m "config: update manifest with Render URLs"
git push
```

---

## Schéma de déploiement final

```
Vous (local)
    │
    │  git push
    ▼
GitHub — physioai-lab (main)
    │
    ├──► Render Web Service (Python)
    │        backend/
    │        URL: https://physioai-lab-api.onrender.com
    │        /docs    → Swagger UI
    │        /health  → Health check
    │        /api/v1/ → Tous les endpoints
    │
    └──► Render Static Site
             frontend/
             URL: https://physioai-lab-frontend.onrender.com
             taskpane.html  → Interface Excel Add-in
             manifest.xml   → À charger dans Excel
```

---

## ⚠️ Notes importantes (Plan Gratuit Render)

| Limitation | Détail |
|------------|--------|
| **Sleep après 15 min** | Le backend s'endort en l'absence de requêtes. Premier appel = ~30s de latence |
| **750h/mois** | Suffisant pour usage personnel/démo |
| **RAM 512 MB** | PyTorch fonctionne mais limiter `epochs` à 100-200 |
| **Pas de GPU** | Calculs CPU uniquement sur plan gratuit |

**Solution pour éviter le sleep** : Ajouter un service de ping gratuit comme [UptimeRobot](https://uptimerobot.com) qui appelle `/health` toutes les 5 minutes.

---

## Flux de développement continu

```bash
# Développer en local
cd backend && uvicorn main:app --reload

# Tester les changements
# ...

# Déployer
git add .
git commit -m "feat: nouvelle fonctionnalité"
git push
# → Render redéploie automatiquement ✅
```
