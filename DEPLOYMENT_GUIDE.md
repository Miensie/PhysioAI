# Guide de déploiement complet — PhysioAI Lab

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│  Votre PC                                                           │
│  git push → GitHub ──────────────────────────────────────────────  │
│                    │                                                │
│                    ├── GitHub Actions (CI/CD)                       │
│                    │         │                                      │
│                    │         ├── Tests pytest ✓                     │
│                    │         ├── Deploy → GitHub Pages (frontend)   │
│                    │         └── Trigger → Render (backend)         │
│                    │                                                │
│  Excel ────────────┼──► GitHub Pages (taskpane.html)               │
│  (Add-in)          │         │                                      │
│                    │         └──► Render API (FastAPI + PyTorch)    │
└─────────────────────────────────────────────────────────────────────┘
```

**Coût total : 0 €** (GitHub Free + Render Free)

---

## Étape 1 — Structurer le dépôt GitHub

### Structure finale du dépôt

```
physioai-lab/                    ← racine du dépôt
│
├── .github/
│   └── workflows/
│       └── deploy.yml           ← CI/CD automatique
│
├── frontend/                    ← Servi par GitHub Pages
│   ├── taskpane.html
│   ├── scripts/
│   │   ├── api.js               ← Version production (URL dynamique)
│   │   ├── app.js
│   │   ├── charts.js
│   │   └── excel.js
│   └── styles/
│       └── app.css
│
├── backend/                     ← Déployé sur Render
│   ├── main.py                  ← Version production (CORS configuré)
│   ├── requirements.txt
│   ├── modeling/
│   ├── ai/
│   ├── api/
│   ├── optimization/
│   └── utils/
│
├── render.yaml                  ← Config Render (à la RACINE)
├── Dockerfile                   ← Pour VPS/Docker/Railway
├── manifest.xml                 ← Manifest Office Add-in
└── index.html                   ← Page d'accueil GitHub Pages
```

### Commandes Git initiales

```bash
# 1. Initialiser le dépôt local
git init
git add .
git commit -m "feat: PhysioAI Lab v2.0 - Initial release"
git remote add origin https://github.com/miensie/PhysioAI.git
git branch -M main
git push -u origin main
```

---

## Étape 2 — Activer GitHub Pages

1. Aller sur votre dépôt GitHub → **Settings**
2. Section **Pages** (menu gauche)
3. **Source** : `Deploy from a branch`
4. **Branch** : `main` / `/ (root)`
5. Cliquer **Save**

⏳ Votre site sera disponible dans 1-2 minutes :
`https://miensie.github.io/PhysioAI`

### Vérification

```bash
curl https://miensie.github.io/PhysioAI/taskpane.html
# → Doit retourner le HTML du taskpane
```

---

## Étape 3 — Déployer le backend sur Render

### Option A : Via render.yaml (recommandé)

1. Créer un compte sur **render.com**
2. Dashboard → **New** → **Web Service**
3. Connecter votre dépôt GitHub `physioai-lab`
4. Render détecte automatiquement `render.yaml`
5. Cliquer **Deploy**

Render utilisera la configuration :
- Root Directory : `backend`
- Build : `pip install -r requirements.txt`
- Start : `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Option B : Configuration manuelle sur Render

| Champ | Valeur |
|-------|--------|
| Name | `physioai-backend` |
| Runtime | Python 3 |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health Check | `/health` |
| Plan | Free |

### Variables d'environnement à configurer sur Render

| Clé | Valeur |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `FRONTEND_URL` | `https://VOTRE-USERNAME.github.io/physioai-lab` |
| `PYTHON_VERSION` | `3.11.0` |

### URL du backend après déploiement

```
https://physioai-backend.onrender.com
https://physioai-backend.onrender.com/health   ← vérification
https://physioai-backend.onrender.com/docs     ← Swagger (si activé)
```

> ⚠️ **Note Render plan Free** : Le service s'arrête après 15 minutes d'inactivité.
> Premier appel = 30-50 secondes de démarrage (cold start).
> Pour un usage professionnel, passer au plan Starter ($7/mois).

---

## Étape 4 — Connecter GitHub → Render (CI/CD)

### Récupérer le Deploy Hook Render

1. Render Dashboard → votre service → **Settings**
2. Section **Deploy Hooks** → **Create Deploy Hook**
3. Copier l'URL (ex: `https://api.render.com/deploy/srv-xxx?key=yyy`)

### Ajouter les secrets GitHub

Aller sur GitHub → votre repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret | Valeur |
|--------|--------|
| `BACKEND_URL` | `https://physioai-backend.onrender.com` |
| `RENDER_DEPLOY_HOOK` | `https://api.render.com/deploy/srv-xxx?key=yyy` |

### Résultat : À chaque `git push main` →

1. ✅ Tests pytest exécutés
2. 🌐 Frontend déployé sur GitHub Pages (URL backend injectée automatiquement)
3. 🚀 Backend re-déployé sur Render

---

## Étape 5 — Mettre à jour le manifest.xml

Remplacer **toutes** les occurrences de `VOTRE-USERNAME` dans `manifest.xml` :

```bash
sed -i 's/VOTRE-USERNAME/votre_vrai_username/g' manifest.xml
sed -i 's/physioai-backend.onrender.com/VOTRE-URL-RENDER.onrender.com/g' manifest.xml
git add manifest.xml
git commit -m "fix: update manifest with production URLs"
git push
```

---

## Étape 6 — Charger l'Add-in dans Excel

### Excel Desktop (Windows/macOS)

1. Ouvrir Excel
2. Menu **Insérer** → **Compléments** → **Mes compléments**
3. Cliquer **Télécharger un complément**
4. Sélectionner votre `manifest.xml` local (ou l'URL raw GitHub)

### Excel Online

1. Ouvrir Excel Online sur office.com
2. **Insérer** → **Compléments Office** → **Charger mon complément**
3. Sélectionner `manifest.xml`

### Vérification

Le bouton **PhysioAI Lab** doit apparaître dans l'onglet **Accueil** du ruban.
Cliquer dessus → le panneau s'ouvre → vérifier que le statut ● est vert.

---

## Étape 7 — Configurer l'URL backend dans l'Add-in

1. Dans le panneau PhysioAI Lab, en haut : champ **URL backend**
2. Saisir : `https://physioai-backend.onrender.com`
3. Appuyer sur Entrée → le point ● passe au vert si le backend répond

Cette URL est sauvegardée en `localStorage` pour les prochaines sessions.

---

## Options d'hébergement backend comparées

| Plateforme | Plan gratuit | RAM | CPU | Cold start | GPU | Recommandé pour |
|------------|-------------|-----|-----|------------|-----|-----------------|
| **Render** | ✅ Oui | 512 MB | Partagé | ~30s | ❌ | Démo / Développement |
| **Railway** | ✅ $5 crédits | 512 MB | Partagé | ~5s | ❌ | Petite production |
| **Fly.io** | ✅ Oui | 256 MB | Partagé | ~3s | ❌ | API légère |
| **VPS (Hetzner)** | ❌ ~€4/mois | 2-4 GB | Dédié | 0s | Optionnel | Production réelle |
| **Google Cloud Run** | ✅ Partiel | Configurable | Partagé | ~2s | ❌ | Scale to zero |

### Déployer sur Railway (alternative Render)

```bash
# Installer Railway CLI
npm install -g @railway/cli

# Login et déploiement
railway login
cd backend
railway init
railway up

# Variables d'environnement
railway variables set ENVIRONMENT=production
railway variables set FRONTEND_URL=https://USERNAME.github.io/physioai-lab
```

### Déployer sur un VPS avec Docker

```bash
# Sur votre VPS (Ubuntu 22.04)
git clone https://github.com/VOTRE-USERNAME/physioai-lab.git
cd physioai-lab

# Build et lancement
docker build -f Dockerfile -t physioai .
docker run -d \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e FRONTEND_URL=https://VOTRE-USERNAME.github.io/physioai-lab \
  --restart unless-stopped \
  --name physioai \
  physioai

# HTTPS avec Nginx + Certbot
apt install nginx certbot python3-certbot-nginx
certbot --nginx -d api.votre-domaine.com

# Config Nginx (/etc/nginx/sites-available/physioai)
# server {
#     server_name api.votre-domaine.com;
#     location / { proxy_pass http://localhost:8000; }
# }
```

---

## Dépannage courant

### ❌ CORS error dans l'Add-in

**Cause** : L'URL du frontend n'est pas dans la liste CORS du backend.

**Fix** : Vérifier que `FRONTEND_URL` est bien défini sur Render :
```
FRONTEND_URL = https://VOTRE-USERNAME.github.io/physioai-lab
```
Et que `main.py` contient bien l'`allow_origin_regex` pour `*.github.io`.

### ❌ Status ● rouge dans l'Add-in

**Causes possibles** :
1. Backend en cold start → attendre 30s et réessayer
2. URL incorrecte → vérifier `https://` et pas de `/` final
3. Backend planté → vérifier les logs sur Render Dashboard

### ❌ manifest.xml refusé par Excel

**Cause** : URLs dans le manifest pointent encore vers `localhost`.

**Fix** :
```bash
grep -n "localhost" manifest.xml
# Remplacer toutes les occurrences par les URLs GitHub Pages
```

### ❌ PyTorch trop lourd pour Render Free

**Symptôme** : Build échoue avec "out of memory" ou timeout.

**Fix** : Remplacer dans `requirements.txt` :
```
# CPU uniquement (plus léger)
torch==2.3.0+cpu --index-url https://download.pytorch.org/whl/cpu
```

### ❌ "Cannot read properties of undefined" dans l'Add-in

**Cause** : Office.js non chargé (page ouverte hors Excel).

**Fix** : L'Add-in ne fonctionne que dans Excel. Pour tester le frontend seul, utiliser la page `index.html`.

---

## Vérification finale

```bash
# 1. Frontend accessible
curl -I https://VOTRE-USERNAME.github.io/physioai-lab/taskpane.html
# → HTTP/2 200

# 2. Backend opérationnel
curl https://physioai-backend.onrender.com/health
# → {"status":"ok","version":"2.0.0",...}

# 3. CORS OK
curl -H "Origin: https://VOTRE-USERNAME.github.io" \
     -I https://physioai-backend.onrender.com/health
# → Access-Control-Allow-Origin: * (ou votre domaine)

# 4. Test d'analyse
curl -X POST https://physioai-backend.onrender.com/analyze/stats \
  -H "Content-Type: application/json" \
  -d '{"data":{"t":[0,1,2,3,4,5],"C":[1.0,0.74,0.54,0.40,0.30,0.22]}}'
# → {"status":"ok","results":{...}}
```

---

*PhysioAI Lab v2.0 — Déploiement complet GitHub Pages + Render*
