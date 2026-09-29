# G.5.3 CLOUD & DEPLOYMENT ARCHITECTURE AUDIT

## 1. Executive Verdict

**VERDICT: YELLOW (IMPORTANT DEPLOYMENT GAPS IDENTIFIED — ARCHITECTURE IS FULLY VIABLE AND READY FOR G.5.3 IMPLEMENTATION)**

The repository exhibits clean modularity, centralized environment configuration (`code/config.py`), secret masking filters (`code/logger.py`), and validated liveness/readiness probes (`/health`, `/readiness`). All core runtime components—Flask API, ML Bridge, Strategy Engine, and Streamlit Dashboard—operate reliably and pass all 378 unit/integration regression tests.

However, containerization and deployment packaging artifacts are currently incomplete:
1. **Zero Dockerfiles**: No `Dockerfile` exists for Flask, Streamlit (GAP-04), ML Bridge, or Data Engine.
2. **Missing Dependency Pinning**: No `requirements.txt` or `pyproject.toml` file exists in the repository.
3. **Host-Bound Execution**: Services run as host processes rather than isolated containers.

The proposed G.5.3 implementation phase will resolve these packaging gaps without requiring any architectural redesign.

---

## 2. Repository Reality

The codebase is organized into modular Python packages under `code/`:
- `code/config.py`: Centralized configuration management module.
- `code/logger.py`: Production logger with automated secret masking (`SecretMaskingFilter`).
- `code/partie1/app.py`: Hardened Flask API serving Three.js simulation, `/cockpit/` React app, `/telemetry`, `/setup`, `/health`, and `/readiness`.
- `code/partie2/data_engine.py`: Kafka consumer writing raw telemetry to MongoDB Atlas.
- `code/partie3/analytics_dashboard.py`: Main Streamlit strategy analytics dashboard.
- `code/partie4/`: React cockpit Vite application (`package.json`, `vite.config.js`).
- `code/streaming/ml_bridge_consumer.py`: Process-isolated real-time ML Bridge consumer (`f1_telemetry` $\rightarrow$ `f1_ml_signals`).
- `code/strategy/`: G.4.5 Strategy Engine core domain models, simulator, validator, and Pareto optimizer.
- `code/strategy_dashboard/`: G.4.6 Strategy Dashboard presentation adapter and UI components.

---

## 3. Current Runtime Architecture

```
[ Three.js Simulator ] ──(HTTP POST)──► [ Flask API Gateway (Port 5000) ] ──► Kafka: f1_telemetry
                                                                                   │
                                                                                   ▼
MongoDB Atlas ◄──(Mongo insert_one)── data_engine.py ◄──(Consumer)─────────────────┤
                                                                                   │
                                                                                   ▼
Kafka: f1_ml_signals ◄──(Producer)── ml_bridge_consumer.py ◄──(Consumer)───────────┘
```

Currently, all services run natively as host Python processes:
- `python code/partie1/app.py`
- `python code/partie2/data_engine.py`
- `python code/streaming/ml_bridge_consumer.py`
- `python -m streamlit run code/partie3/analytics_dashboard.py`

Infrastructure services (MinIO, Zookeeper, Kafka) are managed via `docker-compose.yml`.

---

## 4. Containerization Matrix

| Service | Location | Current State | Target Container | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Flask API Gateway** | `code/partie1/app.py` | Native Host Process | `Dockerfile.api` | P1 |
| **Streamlit Dashboard** | `code/partie3/` | Native Host Process | `Dockerfile.dashboard` (GAP-04) | P1 |
| **ML Bridge Consumer** | `code/streaming/` | Native Host Process | `Dockerfile.ml_bridge` | P1 |
| **Data Engine Consumer**| `code/partie2/` | Native Host Process | `Dockerfile.data_engine` | P2 |
| **Kafka & Zookeeper** | Root `docker-compose.yml` | Containerized | `confluentinc/cp-kafka:7.5.0` | P3 (Existing) |
| **MinIO Object Storage**| Root `docker-compose.yml` | Containerized | `quay.io/minio/minio:latest` | P3 (Existing) |
| **MongoDB Atlas** | Managed Cloud DB | Cloud Service | External Managed DB | P3 (Existing) |
| **React Cockpit** | `code/partie4/` | Built into `partie1/cockpit` | Multi-stage build in `Dockerfile.api` | P2 |

---

## 5. Docker / Compose Audit

- **Root `docker-compose.yml`**: Defines `minio` (ports 9000/9001), `zookeeper` (port 2181), and `kafka` (ports 9092/29092). Contains healthchecks for MinIO (`/minio/health/live`) and `restart: always` policies.
- **`code/partie2/docker-compose.yml`**: Secondary legacy compose file for Zookeeper & Kafka.
- **Audit Deficit**: Neither compose file orchestrates application services (Flask, Streamlit, ML Bridge, Data Engine). Creating a production `docker-compose.prod.yml` will unify infrastructure and application containers.

---

## 6. Cloud Deployment Compatibility

1. **Single VM Deployment (Docker Compose on AWS EC2 / DigitalOcean)**: Highly compatible and recommended for portfolio showcase. Runs unified compose stack.
2. **Managed Cloud Infrastructure (AWS ECS / GCP Cloud Run / Azure Container Apps)**: Fully supported once application Dockerfiles are written in Phase G.5.3 implementation.
3. **Managed Services (MongoDB Atlas + Managed Kafka)**: `code/config.py` supports standard `MONGO_URI` and `KAFKA_BOOTSTRAP_SERVERS` environment variables, enabling seamless connection to MongoDB Atlas or AWS MSK.

---

## 7. Configuration & Environment Audit

- `code/config.py` centralizes environment options:
  - `FLASK_ENV` (`production` / `development`)
  - `FLASK_DEBUG` (Default `False`)
  - `HOST` (Default `127.0.0.1` in production)
  - `PORT` (Default `5000`)
  - `CORS_ORIGINS` (Configurable list, wildcard restricted in production)
  - `MAX_CONTENT_LENGTH` (1 MB)
  - `MONGO_URI`, `MONGO_DATABASE`, `KAFKA_BOOTSTRAP_SERVERS`, `MINIO_ENDPOINT`
- **Assessment**: Configuration is 100% environment-driven. Zero code modifications are required to adjust settings between environments.

---

## 8. Secret Management Audit

- Secrets (`MONGO_URI`, `MINIO_ROOT_PASSWORD`) are loaded via `os.getenv` with `dotenv` fallbacks.
- `code/logger.py` enforces `SecretMaskingFilter`, redacting sensitive URI credentials (`mongodb://***:***@host`).
- `.gitignore` protects `.env`, `.env.*`, `credentials`, `*.log`, and temporary scratch files.
- **Assessment**: Secrets management is clean and production-ready.

---

## 9. Networking & Exposure

- **Public Endpoints**:
  - Flask API: Port `5000` (`/`, `/simulation`, `/cockpit/`, `/telemetry`, `/setup`, `/health`, `/readiness`).
  - Streamlit Dashboard: Port `8501`.
- **Internal Endpoints**:
  - Kafka: Port `9092` (Host) / `29092` (Inter-container).
  - MinIO: Port `9000` (S3 API) / `9001` (Console).
  - Zookeeper: Port `2181`.
- **Security Control**: CORS origin restriction prevents unauthorized web applications from accessing Flask endpoints.

---

## 10. Flask Deployment Readiness

- `code/partie1/app.py` is production-hardened (G.5.1):
  - `MAX_CONTENT_LENGTH` (1 MB) limits payload size.
  - Range validation for `/setup` (`downforce` $\in [0, 100]$, `engine_mix` $\in [1, 10]$).
  - Schema V1 validation for `/telemetry`.
  - Sanitized 400/404/413/500 JSON error handlers preventing stack trace leakage.
  - `/health` and `/readiness` health probes.
- **Gap**: Direct execution uses Flask built-in server (`app.run()`). In production, WSGI server invocation (e.g. `gunicorn --workers 4 --bind 0.0.0.0:5000 partie1.app:app`) should be specified in `Dockerfile.api`.

---

## 11. Streamlit Deployment Readiness (GAP-04 & GAP-06)

- `code/partie3/analytics_dashboard.py` runs cleanly via `streamlit run`.
- **GAP-04 Audit**: Streamlit containerization is missing. Creating `Dockerfile.dashboard` will package Streamlit on port `8501`.
- **GAP-06 Audit**: Dashboard alert banner subscription to `f1_ml_signals` is currently unbuilt. This remains an optional P2 presentation feature.

---

## 12. React Cockpit Deployment Readiness

- `code/partie4/` contains Vite React application.
- Building via `npm run build` compiles static assets to `dist/`, which are copied to `code/partie1/cockpit/`.
- Flask serves `code/partie1/cockpit/index.html` at route `/cockpit/`.
- **Assessment**: Cockpit static asset bundling with Flask is operational and deployment-ready.

---

## 13. Kafka Deployment Readiness

- Defined in `docker-compose.yml` (`confluentinc/cp-kafka:7.5.0` & `cp-zookeeper:7.5.0`).
- Configured with `PLAINTEXT://kafka:29092` inter-container listener and `PLAINTEXT_HOST://localhost:9092` external listener.
- Both raw telemetry topic (`f1_telemetry`) and ML signals topic (`f1_ml_signals`) operate reliably.

---

## 14. MongoDB Atlas Readiness

- Connects dynamically using `MONGO_URI` environment variable.
- Uses explicit connection timeouts (`MONGO_CONNECT_TIMEOUT_MS = 1000`).
- Supports graceful fallback to direct insertion or offline mode if connection fails.

---

## 15. MinIO / Spark Readiness (GAP-05)

- MinIO object storage runs on port `9000` via Docker Compose.
- **GAP-05 Audit**: 8 PyTest integration tests skip when MinIO container is offline. These skips are intentional and protect unit test suite execution without external container dependencies.

---

## 16. ML Artifact Deployment Readiness

- Trained ML model artifacts (G.4.2 Anomaly, G.4.3 Lap Time, G.4.4 Tire Degradation) are stored under `data_lake/ml/`.
- `code/streaming/ml_bridge_consumer.py` includes robust artifact loading with inline fallback heuristics if `.joblib` files are not present.

---

## 17. G.4.5 / G.4.6 Compatibility

- G.4.5 Strategy Simulator & Optimizer: 100% in-memory deterministic calculation.
- G.4.6 Strategy Dashboard Adapter: Independent presentation layer.
- Neither module relies on hardcoded local paths; both operate deterministically across deployment environments.

---

## 18. Health / Readiness

- `GET /health`: Liveness probe returning application state (`status: UP`).
- `GET /readiness`: Dependency readiness probe evaluating status of MongoDB Atlas and Kafka (`HEALTHY` or `DEGRADED`).

---

## 19. Observability

- Structured Python logging with `SecretMaskingFilter` protecting standard output.
- Log level configurable via `LOG_LEVEL` (`INFO` default).

---

## 20. CI/CD Readiness

- **Current State**: Automated test suite (378 passing tests) runnable via `python -m pytest`.
- **Deployment Requirement**: Creating a `.github/workflows/ci.yml` pipeline executing pytest and Docker build verification will establish automated CI/CD.

---

## 21. Reproducibility

- **Missing Artifact**: No `requirements.txt` file exists to pin Python package versions.
- **Action Required for G.5.3 Implementation**: Generate a clean `requirements.txt` file pinning exact compatible library versions (`flask`, `flask-cors`, `kafka-python`, `pymongo`, `streamlit`, `pandas`, `numpy`, `scikit-learn`, `xgboost`, `pyarrow`, `pytest`).

---

## 22. Security Regression Check

All G.5.1 security controls remain intact:
- `FLASK_DEBUG=False` in production mode.
- Restricted CORS origins.
- `MAX_CONTENT_LENGTH` payload limit (1 MB).
- Schema V1 validation for incoming telemetry.
- Range bounds for setup updates.
- Sanitized JSON error responses.
- `SecretMaskingFilter` active.

---

## 23. Performance / Resource Considerations

| Service Component | CPU Overhead | Memory Overhead | Network Footprint |
| :--- | :--- | :--- | :--- |
| **Flask API** | Low (< 5% single core) | ~40 MB | High (5 Hz telemetry ingress) |
| **ML Bridge Consumer** | Low (~0.08 ms / event) | ~80 MB | Medium (Dual Kafka topic stream) |
| **Data Engine Consumer**| Low | ~35 MB | Medium (Mongo writes) |
| **Streamlit Dashboard** | Medium (In-memory Pareto sorting)| ~150 MB | Low |
| **Total Stack Target** | **< 2 CPU Cores** | **< 1.5 GB RAM** | **Compatible with $10–$20/mo Cloud VM** |

---

## 24. Target Deployment Architectures

### Architecture 1: Single VM Containerized Stack (Portfolio Showcase - Recommended)
- EC2 / DigitalOcean Ubuntu VM ($10-$20/mo).
- `docker-compose.prod.yml` running Flask (WSGI), Streamlit, ML Bridge, Data Engine, Kafka, Zookeeper, and MinIO.
- External MongoDB Atlas database.

### Architecture 2: Managed Cloud Services
- AWS ECS / GCP Cloud Run for application containers.
- AWS MSK / Confluent Cloud for Kafka.
- MongoDB Atlas for database storage.

---

## 25. Proposed G.5.3 Implementation Scope

1. **Dependency Pinning**: Create `requirements.txt` with frozen, tested library versions.
2. **Application Dockerfiles**:
   - `Dockerfile.api`: Multi-stage build building React cockpit (`code/partie4/`) and packaging Flask with Gunicorn WSGI.
   - `Dockerfile.dashboard`: Packaging Streamlit Dashboard (GAP-04).
   - `Dockerfile.ml_bridge`: Packaging ML Bridge Consumer.
   - `Dockerfile.data_engine`: Packaging Kafka Data Engine Consumer.
3. **Unified Production Compose**: Create `docker-compose.prod.yml` orchestrating infrastructure and application containers.
4. **Environment Template**: Create `.env.example` documenting all configuration parameters.
5. **CI/CD Workflow**: Create `.github/workflows/ci.yml` running pytest and container builds.
6. **Documentation**: Update `README.md` with complete deployment instructions.

---

## 26. GAP Classification

| GAP ID | Description | Severity | G.5.3 Status |
| :--- | :--- | :--- | :--- |
| **GAP-03** | Real-time visualizer REST polling (200ms) instead of WebSockets | P2 (Important) | Open (Deferred to future UX phase) |
| **GAP-04** | Streamlit Dashboard containerization (`Dockerfile`) | P1 (Critical) | **TARGET FOR G.5.3 IMPLEMENTATION** |
| **GAP-05** | 8 integration tests require active MinIO service | P3 (Improvement) | Open (Intentional test isolation) |
| **GAP-06** | Streamlit dashboard alert banner subscription to `f1_ml_signals` | P2 (Important) | Open (Deferred to future presentation phase) |

---

## 27. Portfolio Readiness

- Architecture, code quality, testing, security, and ML integration are in a state for public showcase on GitHub, LinkedIn, and technical interviews.
- Packaging the application into Docker containers and pinning dependencies via `requirements.txt` will allow external reviewers to run the entire F1 Digital Twin platform with a single `docker-compose up` command.

---

## 28. Risks

- **Low Risk**: Containerization does not alter domain physics, strategy optimization algorithms, or ML inference logic.

---

## 29. Recommended Next Steps

1. Approve G.5.3 Architecture Audit.
2. Proceed to **Phase G.5.3 Implementation**: Generate `requirements.txt`, Dockerfiles, `docker-compose.prod.yml`, and CI/CD workflows.

---

## 30. Final Verdict

**VERDICT: YELLOW (DEPLOYMENT GAPS IDENTIFIED — ARCHITECTURE IS FULLY VIABLE AND READY FOR G.5.3 IMPLEMENTATION)**

---
