# PhysioAI Lab — Add-in Excel de Modélisation Physico-Chimique + IA

> **Plateforme professionnelle de modélisation industrielle avec Deep Learning**  
> Régression · Modèles physiques · Cinétique · Diffusion · Random Forest · PyTorch · Hybride IA+Physique

---

## Architecture

```
physioai-lab/
│
├── manifest.xml                    ← Manifeste Office Add-in
│
├── frontend/
│   ├── taskpane.html               ← Interface principale (6 panneaux)
│   ├── styles/app.css              ← Thème laboratoire industriel sombre
│   └── scripts/
│       ├── api.js                  ← Client HTTP (tous les appels FastAPI)
│       ├── charts.js               ← Graphiques Chart.js (7 types)
│       ├── excel.js                ← Interactions Office.js
│       └── app.js                  ← Orchestrateur principal (1200 lignes)
│
├── backend/
│   ├── main.py                     ← Application FastAPI
│   ├── requirements.txt
│   │
│   ├── modeling/
│   │   ├── regression.py           ← Linéaire, polynomiale, Ridge, Lasso
│   │   └── physical_models.py      ← Cinétique, Fick, Batch, CSTR, Newton
│   │
│   ├── ai/
│   │   ├── ml_models.py            ← Random Forest, SVR, GB, K-Means, DBSCAN
│   │   ├── deep_learning.py        ← MLP, ResNet, Hybride (PyTorch)
│   │   └── ai_advisor.py           ← Conseiller IA automatique
│   │
│   ├── optimization/
│   │   └── optimizer.py            ← curve_fit, Nelder-Mead, Évolution diff.
│   │
│   ├── utils/
│   │   └── statistics.py           ← Statistiques descriptives, corrélations
│   │
│   └── tests/
│       └── test_backend.py         ← 25 tests pytest
│
└── docs/
    └── examples/
        └── sample_kinetics.csv     ← Données de test (cinétique + refroidissement)
```

---

## Installation

### Prérequis
- Python 3.11+
- Node.js 18+ (pour le serveur HTTPS local)
- Microsoft Excel 2019+ ou Microsoft 365

---

### Backend Python

```bash
cd physioai-lab/backend

# Environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate             # Windows

# Dépendances
pip install -r requirements.txt

# Lancer le serveur
python main.py
# → http://localhost:8000
# → Documentation Swagger : http://localhost:8000/docs
```

**Avec GPU CUDA (optionnel) :**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

### Frontend Excel Add-in

```bash
# Option A : serveur statique Python (le plus simple)
cd physioai-lab/frontend
python -m http.server 3000
# → http://localhost:3000/taskpane.html

# Option B : avec HTTPS (requis pour Excel Desktop)
npm install -g http-server
npx http-server . -p 3000 --ssl --cert cert.pem --key key.pem

# Option C : GitHub Pages (déploiement zero-config)
# → Mettre tous les fichiers frontend/ à la racine du dépôt
```

---

### Charger l'Add-in dans Excel

**Excel Desktop :**
1. Insérer → Compléments → Mes compléments → Télécharger un complément
2. Sélectionner `manifest.xml`

**Excel Online :**
1. Insérer → Compléments Office → Charger mon complément
2. Sélectionner `manifest.xml`

---

## Tests

```bash
cd backend
pytest tests/ -v --tb=short

# Avec coverage
pip install pytest-cov
pytest tests/ -v --cov=. --cov-report=html
```

---

## Endpoints API

| Méthode | URL | Description |
|---------|-----|-------------|
| GET  | `/health` | Statut + versions des librairies |
| POST | `/analyze/stats` | Statistiques descriptives |
| POST | `/analyze/correlation` | Corrélations Pearson + Spearman |
| POST | `/analyze/recommend` | Recommandation de modèle IA |
| POST | `/model/regression` | Régression linéaire/polynomiale |
| POST | `/model/physics` | Modèles physico-chimiques |
| POST | `/simulate/` | Simulation sur grille temporelle |
| POST | `/train_ai/ml` | Entraînement ML (RF, SVR, GB) |
| POST | `/train_ai/dl` | Entraînement Deep Learning PyTorch |
| POST | `/predict/` | Prédiction sur nouvelles données |
| POST | `/optimize/calibrate` | Calibration automatique des paramètres |
| POST | `/optimize/auto` | Auto-sélection du meilleur modèle |

---

## Exemples d'utilisation API

### Cinétique ordre 1 (calibration)
```bash
curl -X POST http://localhost:8000/model/physics \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kinetics",
    "t": [0,1,2,3,4,5,8,10,15,20],
    "C": [1.0,0.74,0.54,0.40,0.30,0.22,0.10,0.05,0.01,0.002],
    "order": 1,
    "C0_guess": 1.0,
    "k_guess": 0.1
  }'
```

### Entraîner un MLP
```bash
curl -X POST http://localhost:8000/train_ai/dl \
  -H "Content-Type: application/json" \
  -d '{
    "X": [[0],[1],[2],[3],[4],[5]],
    "y": [1.0, 0.74, 0.54, 0.40, 0.30, 0.22],
    "model": "mlp",
    "hidden_dims": [32, 16],
    "epochs": 300,
    "lr": 0.001
  }'
```

### Recommandation IA
```bash
curl -X POST http://localhost:8000/analyze/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "data": {"t": [0,1,2,3,4,5], "C": [1.0,0.74,0.54,0.40,0.30,0.22]},
    "target": "C",
    "domain": "chemistry"
  }'
```

---

## Fonctionnalités implémentées

### Modèles statistiques
- ✅ Régression linéaire avec intervalles de confiance et p-valeur
- ✅ Régression polynomiale (degré 1–10)
- ✅ Ridge / Lasso (régularisation)

### Modèles physiques
- ✅ Cinétique chimique ordre 0, 1, 2 (calibration + simulation)
- ✅ Réacteur batch (ODE RK45)
- ✅ CSTR état stationnaire
- ✅ Diffusion Fick 1D (solution analytique)
- ✅ Refroidissement de Newton

### Machine Learning
- ✅ Random Forest Regressor (OOB, feature importance)
- ✅ Support Vector Regression (noyaux rbf, linear, poly)
- ✅ Gradient Boosting
- ✅ K-Means (auto-sélection k, Elbow + Silhouette)
- ✅ DBSCAN

### Deep Learning (PyTorch)
- ✅ MLP générique (activation, dropout, batch norm)
- ✅ ResNet tabulaire (blocs résiduels)
- ✅ Early stopping
- ✅ Modèle hybride Physique + NN résiduel

### Optimisation
- ✅ curve_fit (Levenberg-Marquardt)
- ✅ Nelder-Mead (Simplex)
- ✅ Évolution différentielle (global)
- ✅ Auto-sélection du meilleur modèle physique
- ✅ Analyse de sensibilité

### IA Advisor
- ✅ Détection de linéarité (R² LR vs RF)
- ✅ Détection du bruit (SNR)
- ✅ Détection d'outliers (IQR)
- ✅ Test de normalité (Shapiro)
- ✅ Recommandation multi-niveaux (statistique, physique, ML, DL, hybride)

---

## Données de test

Fichier `docs/examples/sample_kinetics.csv` :
- Cinétique ordre 1 : k ≈ 0.30 s⁻¹, C₀ ≈ 1.0
- Refroidissement Newton : T₀=100°C, T_env=20°C, h≈0.04 W/K

---

*PhysioAI Lab v2.0 — Architecture modulaire, prête pour évolution SaaS*
