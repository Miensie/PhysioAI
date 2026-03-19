# ⚗ PhysioAI Lab

> **Modélisation physico-chimique assistée par intelligence artificielle**  
> Excel Web Add-in (Office.js) + Backend Python FastAPI

---

## Architecture

```
physioai-lab/
├── backend/
│   ├── main.py                  # FastAPI — point d'entrée
│   ├── requirements.txt
│   ├── api/
│   │   ├── schemas.py           # Pydantic models
│   │   ├── routes_regression.py # POST /model
│   │   ├── routes_analysis.py   # POST /analyze
│   │   ├── routes_physical.py   # POST /physical/*
│   │   ├── routes_ai.py         # POST /ai/advise, /train_ai, /predict
│   │   └── routes_simulation.py # POST /simulate
│   ├── modeling/
│   │   ├── regression.py        # 7 types de régression
│   │   ├── analysis.py          # Statistiques + corrélation
│   │   └── physical.py          # Cinétique, CSTR, Fick, Newton…
│   ├── ai/
│   │   ├── ai_advisor.py        # Analyse + recommandations IA
│   │   ├── ml_models.py         # Random Forest, SVR, K-Means
│   │   └── deep_learning.py     # MLP PyTorch + modèle hybride
│   ├── optimization/
│   │   └── optimizer.py         # Calibration ODE, minimisation
│   └── data/examples/
│       ├── kinetics_data.json
│       └── regression_data.json
└── frontend/
    ├── manifest.xml             # Office Add-in manifest
    ├── taskpane.html            # Interface principale
    ├── css/taskpane.css
    └── js/taskpane.js
```

---

## Installation

### Backend Python

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
# → API disponible sur http://localhost:8000
# → Documentation Swagger : http://localhost:8000/docs
```

### Frontend Excel Add-in

**Option 1 — Développement local (avec npx)**
```bash
cd frontend
npx office-addin-dev-certs install
npx http-server . -p 3000 --ssl
```

**Option 2 — Sideload dans Excel**
1. Ouvrir Excel → Insérer → Compléments → Gérer les compléments
2. Charger `manifest.xml`
3. L'add-in apparaît dans l'onglet Accueil

---

## Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/model` | Régression (7 types + auto) |
| `POST` | `/api/v1/analyze` | Statistiques + corrélation |
| `POST` | `/api/v1/simulate` | Simulation modèle physique |
| `POST` | `/api/v1/physical/kinetics` | Cinétique chimique ordre 0/1/2 |
| `POST` | `/api/v1/physical/cstr` | CSTR transitoire |
| `POST` | `/api/v1/physical/diffusion` | Loi de Fick |
| `POST` | `/api/v1/physical/heat` | Transfert de chaleur Newton |
| `POST` | `/api/v1/ai/advise` | Conseiller IA intelligent |
| `POST` | `/api/v1/train_ai` | ML (RF, SVR, GBM, KMeans) |
| `POST` | `/api/v1/predict` | Deep Learning MLP PyTorch |
| `POST` | `/api/v1/predict/hybrid` | Modèle hybride Physique + NN |

---

## Exemples de requêtes

### Régression automatique
```bash
curl -X POST http://localhost:8000/api/v1/model \
  -H "Content-Type: application/json" \
  -d '{"x":[1,2,3,4,5],"y":[2.1,4.0,6.2,7.9,10.1],"model_type":"auto"}'
```

### Cinétique ordre 1 + calibration
```bash
curl -X POST http://localhost:8000/api/v1/physical/kinetics \
  -H "Content-Type: application/json" \
  -d '{"t":[0,5,10,15,20],"C":[1.0,0.78,0.61,0.47,0.37],"C0":1.0,"k":0.05,"order":1,"fit":true}'
```

### Conseiller IA
```bash
curl -X POST http://localhost:8000/api/v1/ai/advise \
  -H "Content-Type: application/json" \
  -d '{"x":[0,5,10,15,20,25,30],"y":[1.0,0.78,0.61,0.47,0.37,0.29,0.22]}'
```

### Deep Learning MLP
```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"X":[[0],[5],[10],[15],[20]],"y":[1.0,0.78,0.61,0.47,0.37],"hidden_layers":[32,16],"epochs":100}'
```

---

## Modèles disponibles

### Régression
| Modèle | Équation |
|--------|----------|
| Linéaire | y = a·x + b |
| Logarithmique | y = a·ln(x) + b |
| Exponentielle | y = a·exp(b·x) + c |
| Puissance | y = a·x^b |
| Polynomiale (deg n) | y = Σ aᵢ·xⁱ |
| Ridge (L2) | Régression pénalisée L2 |
| Lasso (L1) | Régression pénalisée L1 |

### Modèles Physiques (Génie des Procédés)
- **Cinétique chimique** : ordre 0, 1, 2 avec calibration par curve_fit
- **CSTR transitoire** : bilan matière avec réaction ordre 1
- **PFR** : réacteur piston multi-ordres
- **Diffusion de Fick** : 1D semi-infini
- **Transfert de chaleur** : refroidissement/chauffage Newton
- **Loi de Darcy** : écoulement en milieu poreux
- **Antoine** : pression de vapeur saturante
- **Tanks-in-Series** : distribution des temps de séjour

### Intelligence Artificielle
- **Random Forest** + cross-validation + feature importance
- **SVR** (noyaux RBF, linéaire, polynomial)
- **Gradient Boosting**
- **K-Means** + courbe elbow + score silhouette
- **MLP PyTorch** avec BatchNorm, Dropout, scheduler LR
- **Modèle hybride** : Cinétique + réseau correcteur de résidus

---

## Variables d'environnement

Créer un fichier `.env` dans `/backend` :
```env
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

---

## Évolution SaaS

Pour déployer en production :
1. **Backend** : Docker + Gunicorn sur Railway/Render/AWS
2. **Frontend** : Azure Static Web Apps ou CDN
3. **Auth** : JWT + OAuth2 (ajouter middleware FastAPI)
4. **Base de données** : PostgreSQL + SQLAlchemy pour persistance des modèles
5. **Queue** : Celery + Redis pour les entraînements longs (DL)

