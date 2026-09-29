# F1 Digital Twin — Race Engineering Platform

## Présentation du Projet
Ce projet crée un écosystème complet de simulation de Formule 1 basé sur les données réelles **(Digital Twin)**. Il se divise en trois piliers :

1. **Simulation Web (Partie 1)** : Une interface 3D interactive (Three.js + WebGL) gérant la physique de course et les conditions climatiques.
2. **Data Pipeline (Partie 2)** : Un système de télémétrie en temps réel collectant les données des voitures via Apache Kafka.
3. **Atelier d'Optimisation (Partie 3)** : Un dashboard Streamlit pour analyser et optimiser les performances.

---

## Infrastructure

| Composant | Technologie | État |
|---|---|---|
| Broker de messages | Apache Kafka (Docker) | ✅ Configuré |
| Topic Kafka | `f1_telemetry` | ✅ Créé |
| Base de données | MongoDB Atlas (Cloud) | ✅ Configuré |
| Serveur Web | Flask (Python) | ✅ Opérationnel |

---

## Structure du dossier /code

```
/code
├── partie1/          → Simulation Web (Frontend, Physics engine, API Flask)
│   ├── app.py        → Serveur Flask + endpoint /telemetry
│   ├── index.html    → Page principale (Three.js + UI)
│   ├── simulation.js → Moteur 3D, physique, télémétrie
│   ├── style.css     → Design et thèmes F1
│   ├── car/          → Modèles 3D .glb des voitures
│   └── img/          → Assets images
├── partie2/          → Data Engineering
│   ├── docker-compose.yml  → Kafka + Zookeeper
│   └── data_engine.py      → Consumer Kafka → MongoDB Atlas
└── partie3/          → Analytics Dashboard
    └── analytics_dashboard.py → Streamlit dashboard
```

---

## Lancer le projet

### Prérequis
Créer un fichier `.env` à la racine du projet (déjà fourni, **ne pas committer**) :
```
MONGO_URI=mongodb+srv://...
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC=f1_telemetry
```

### Démarrage complet avec Docker Compose (Stack Production Unified G.5.3)
```bash
# Lancer toute la stack de production (Zookeeper, Kafka, MinIO, Flask API, Streamlit, ML Bridge, Data Engine)
docker compose -f docker-compose.prod.yml up -d
```

### Démarrage manuel (avec Kafka)
```bash
# 1. Démarrer Docker Desktop (avec droits admin)
# 2. Lancer Kafka + Zookeeper
docker compose -f code/partie2/docker-compose.yml up -d

# 3. Lancer le Data Engine (Consumer Kafka → MongoDB)
python code/partie2/data_engine.py

# 4. Lancer le serveur Flask (Simulation + API)
python code/partie1/app.py

# 5. Lancer le Dashboard Streamlit
python -m streamlit run code/partie3/analytics_dashboard.py
```

### Démarrage rapide (sans Kafka — mode simulation)
```bash
# Lancer uniquement la simulation et le dashboard
python code/partie1/app.py
python -m streamlit run code/partie3/analytics_dashboard.py
```

| Service | URL |
|---|---|
| Simulation 3D | http://localhost:5000 |
| Analytics Dashboard | http://localhost:8501 |

---

## Payload de Télémétrie

Format JSON envoyé de la simulation vers Kafka :
```json
{
  "speed": 318.4,
  "wind_speed": 45.2,
  "drag_coefficient": 0.31,
  "downforce": 18400,
  "g_force": 4.7,
  "torque": 612,
  "tire_temp": [89.2, 91.4, 102.7, 98.1],
  "tire_wear": [12.5, 11.3, 8.7, 9.1],
  "pos_x": 120.4,
  "pos_z": -45.8,
  "timestamp": "2026-06-29T10:00:00.000Z"
}
```

---

## Production & Security

### Environment Configuration & Variables
Environment settings are loaded centrally via `code/config.py`.

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | Environment mode (`development`, `testing`, `production`) |
| `FLASK_DEBUG` | `false` | Enable/disable Flask debug mode |
| `HOST` | `127.0.0.1` | Network interface binding |
| `PORT` | `5000` | Application port |
| `CORS_ORIGINS` | Explicit local origins | Allowed origins list or comma-separated string |
| `MAX_CONTENT_LENGTH` | `1048576` (1MB) | Maximum payload body limit |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker bootstrap servers |
| `MINIO_ENDPOINT` | `http://localhost:9000` | MinIO Object Storage endpoint |

### Startup Requirements
1. Install Python dependencies: `pip install -r requirements.txt`.
2. Ensure `.env` is configured with production secrets.
3. Start infrastructure services via Docker: `docker-compose up -d`.

### Health & Readiness Probes
- `GET http://localhost:5000/health`: Liveness status check (`status: UP`).
- `GET http://localhost:5000/readiness`: Dependency status check (`status: HEALTHY` | `DEGRADED`).

### Security Considerations
- Stack trace leakage is disabled; standard JSON error messages are returned on HTTP exceptions.
- Credentials and connection URIs are automatically redacted from application logs via `SecretMaskingFilter`.
- Payload size and numeric parameter ranges (`downforce` $\in [0, 100]$, `engine_mix` $\in [1, 10]$) are strictly validated.

### Development vs Production Distinction
- **Development**: Run `FLASK_ENV=development FLASK_DEBUG=true python code/partie1/app.py`.
- **Production**: Run `FLASK_ENV=production FLASK_DEBUG=false python code/partie1/app.py` with WSGI server (e.g. gunicorn or uWSGI).

### Known Limitations
- Real-time telemetry visualization in Three.js cockpit currently uses 200ms REST polling rather than WebSockets.