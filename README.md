# NeuroGuard AI 🧠

> **Passive early Parkinson's disease detection using federated learning, keystroke biometrics, and wearable sleep monitoring.**

[![CI](https://github.com/neuroguard/neuroguard/actions/workflows/ci.yml/badge.svg)](https://github.com/neuroguard/neuroguard/actions/workflows/ci.yml)
[![HIPAA Compliant](https://img.shields.io/badge/HIPAA-Compliant-green)](docs/hipaa.md)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)

---

## Table of Contents

1. [What is NeuroGuard?](#what-is-neuroguard)
2. [Architecture Overview](#architecture-overview)
3. [Quick Start — Run Locally](#quick-start--run-locally)
4. [Accessing the App](#accessing-the-app)
5. [Development Setup](#development-setup)
6. [Running Tests](#running-tests)
7. [Deployment](#deployment)
8. [Environment Variables](#environment-variables)
9. [Project Structure](#project-structure)

---

## What is NeuroGuard?

NeuroGuard AI detects early Parkinson's disease biomarkers through passive monitoring:

- **📱 Keystroke biometrics** — timing metadata (dwell times, inter-key intervals) captured on-device, never the actual text
- **⌚ Wearable sleep metrics** — REM fragmentation index, HRV, nocturnal movement via Fitbit/Apple Watch/Oura
- **🤖 Federated learning** — raw health data never leaves the device; only privacy-preserved gradient updates are sent to the server
- **📊 Risk scoring** — 0–100 score with SHAP-based AI explanations and confidence intervals
- **👨‍⚕️ Clinician dashboard** — web portal for neurologists to monitor patients, review trends, and generate PDF reports

**Privacy model:** ε=0.5 per FL round (total budget ε=10.0), Gaussian DP noise, Byzantine-resilient aggregation.

---

## Architecture Overview

```
┌─────────────┐     HTTPS/REST     ┌─────────────────────────────────────┐
│ Flutter App │ ──────────────────▶ │          nginx (port 8000)           │
│  (mobile)   │                    │                                       │
└─────────────┘                    │  /api/v1/auth      → auth:8001       │
                                   │  /api/v1/health    → health:8003     │
┌─────────────┐     HTTPS/REST     │  /api/v1/risk      → risk:8004       │
│  Next.js    │ ──────────────────▶ │  /api/v1/alerts    → alerts:8005    │
│  Dashboard  │                    │  /api/v1/reports   → reports:8006    │
│  (port 3000)│                    │  /api/v1/federated → federated:8007  │
└─────────────┘                    └──────────────────────────────────────┘
                                              │
                           ┌──────────────────┼──────────────────┐
                           ▼                  ▼                  ▼
                     PostgreSQL 16        Redis 7           Apache Kafka
                      (port 5432)        (port 6379)        (port 9092)
```

---

## Quick Start — Run Locally

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | 4.x+ | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Git | Any | `winget install git.git` |
| Node.js (optional, for web dev) | 20+ | [nodejs.org](https://nodejs.org) |
| Flutter (optional, for mobile dev) | 3.22+ | [flutter.dev](https://flutter.dev/docs/get-started/install) |

> **Note:** Docker Desktop is the only hard requirement to run the complete stack.

### Step 1 — Clone & configure

```bash
git clone https://github.com/your-org/neuroguard.git
cd neuroguard

# Copy environment template
cp .env.example .env
```

Open `.env` and set **at minimum** these values for local dev (the rest have working defaults):

```bash
# Required — get a free Auth0 account at auth0.com
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.neuroguard.health

# Required — generate a random key
FIELD_ENCRYPTION_KEY=<run: python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())">

# Required — for the web dashboard
NEXTAUTH_SECRET=<run: openssl rand -hex 32>
```

> **Fast local demo:** You can skip Auth0 by setting `AUTH0_DOMAIN=dev` and the services will use a mock JWT validator.

### Step 2 — Start the full stack

```bash
cd backend
docker compose up -d
```

This starts:
| Service | Port | Description |
|---------|------|-------------|
| **nginx API gateway** | `8000` | Routes all `/api/v1/*` requests |
| auth-service | `8001` | JWT auth, user registration |
| health-service | `8003` | Keystroke ingest, wearable sync |
| risk-service | `8004` | ML inference, SHAP explanations |
| alerts-service | `8005` | Alert rule engine |
| reports-service | `8006` | PDF generation, patient data |
| federated-service | `8007` | Flower FL server |
| **web-dashboard** | `3000` | Next.js clinician portal |
| PostgreSQL | `5432` | Primary database |
| Redis | `6379` | Cache + token blacklist |
| Kafka | `9092` | Event bus |
| Alembic migrate | — | Runs DB migrations on startup |

Wait ~30 seconds for all services to become healthy:

```bash
docker compose ps
# All services should show "healthy" or "running"
```

---

## Accessing the App

### 🌐 Web Dashboard (Clinician Portal)

Open **http://localhost:3000** in your browser.

**Demo credentials** (created automatically on first startup):
```
Email:    admin@neuroguard.health
Password: NeuroGuard@Demo2026!
Role:     hospital_admin
```

```
Email:    dr.smith@neuroguard.health
Password: Clinician@Demo2026!
Role:     clinician
```

**What you'll see:**
- Dashboard with patient risk overview and high-risk alerts
- Patient list with search, filter by risk tier, pagination
- Individual patient pages: 90-day risk trend chart, SHAP AI explainer, sleep + keystroke biomarker cards
- Alert feed with ability to send messages to patients
- PDF report generation (downloads from S3-compatible local storage)

### 🔌 REST API (API Gateway)

Base URL: **http://localhost:8000/api/v1**

Interactive docs (Swagger UI):
- Auth service: http://localhost:8001/docs
- Health service: http://localhost:8003/docs
- Risk service: http://localhost:8004/docs

**Quick test — get a token:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@neuroguard.health","password":"NeuroGuard@Demo2026!"}'
```

**Use the token:**
```bash
export TOKEN="<access_token from above>"

# Get health summary
curl http://localhost:8000/api/v1/health/summary \
  -H "Authorization: Bearer $TOKEN"

# Get risk score
curl http://localhost:8000/api/v1/risk/score \
  -H "Authorization: Bearer $TOKEN"

# List patients (clinician role)
curl http://localhost:8000/api/v1/clinician/patients \
  -H "Authorization: Bearer $TOKEN"
```

### 📱 Mobile App (Flutter)

**Prerequisites:** Flutter SDK 3.22+ installed, Android emulator or iOS simulator running.

```bash
cd mobile
flutter pub get

# Android emulator (API gateway on 10.0.2.2)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1

# iOS simulator (API gateway on localhost)
flutter run --dart-define=API_BASE_URL=http://localhost:8000/api/v1

# Physical Android device (replace with your machine's IP)
flutter run --dart-define=API_BASE_URL=http://192.168.1.x:8000/api/v1
```

**App features you can test:**
1. Register a new account (onboarding flow with consent screens)
2. Dashboard showing wellness score
3. Sleep insights (tap "Sync Wearable" to add mock sleep data)
4. Keystroke monitoring starts automatically in background
5. Assessments: finger tap test, spiral drawing, voice recording, gait analysis
6. Alerts feed

### 📊 Monitoring (Grafana)

After running `docker compose up -d` in `infra/k8s/monitoring/` (K8s only), or via:

```bash
# Prometheus metrics
curl http://localhost:9090  # Prometheus UI

# Grafana dashboards (K8s deployment)
kubectl port-forward -n monitoring svc/grafana 3001:3000
# Open http://localhost:3001  admin / <grafana secret>
```

---

## Development Setup

### Backend (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Set environment
cp ../.env.example .env

# Run DB + Redis only (for local service dev)
docker compose up -d postgres redis kafka

# Run a single service locally (example: auth)
uvicorn backend.services.auth.main:app --host 0.0.0.0 --port 8001 --reload

# Or run all services via compose
docker compose up
```

### Web Dashboard (Next.js)

```bash
cd web
npm install

# Configure (copy from root .env)
cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=dev-secret-replace-in-prod
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
EOF

# Start dev server with hot reload
npm run dev
# Open http://localhost:3000
```

### ML Model

```bash
cd ml
pip install -r requirements.txt

# Test model forward pass
python -c "
import torch
from models.neuroguard_model import NeuroGuardModel
model = NeuroGuardModel()
out = model(torch.randn(1, 20), torch.randn(1, 15))
print(f'Risk score: {out.item():.4f}')
"

# Run inference pipeline
python -c "
from inference.pipeline import InferencePipeline
import numpy as np
pipeline = InferencePipeline('models/neuroguard_v1.pt')
result = pipeline.predict(
    keystroke_features=np.random.randn(20),
    sleep_features=np.random.randn(15)
)
print(f'Score: {result.risk_score:.3f} | Tier: {result.risk_tier} | Latency: {result.latency_ms:.1f}ms')
"

# Start Flower federated learning server
python -m ml.federated.server --rounds 5 --min-clients 2
```

### Database Migrations

```bash
cd backend

# Run all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "add_new_table"

# Roll back one migration
alembic downgrade -1

# View migration history
alembic history --verbose
```

---

## Running Tests

### Backend
```bash
cd backend
pytest tests/ -v --cov=. --cov-report=html
# Coverage report: htmlcov/index.html
```

### Web
```bash
cd web
npm test                    # Watch mode
npm test -- --coverage      # With coverage
npm run test:ci             # CI mode (no watch)
```

### Flutter
```bash
cd mobile
flutter test --coverage
# View coverage: genhtml coverage/lcov.info -o coverage/html
```

### ML
```bash
cd ml
pytest tests/ -v
```

### Full E2E (requires Docker Compose running)
```bash
# Start the stack
cd backend && docker compose up -d

# Wait for healthy
sleep 30

# Run end-to-end tests
cd .. && pytest e2e/ -v --base-url=http://localhost:8000
```

---

## Deployment

### Production (AWS EKS)

1. **Provision infrastructure with Terraform:**
```bash
cd infra/terraform

# Initialize
terraform init

# Plan (review changes)
terraform plan -var="db_password=<STRONG_PASSWORD>"

# Apply
terraform apply -var="db_password=<STRONG_PASSWORD>" -auto-approve
```

2. **Configure kubeconfig:**
```bash
aws eks update-kubeconfig --region us-east-1 --name neuroguard-prod
```

3. **Create K8s secrets:**
```bash
kubectl create namespace neuroguard

kubectl create secret generic neuroguard-secrets \
  --namespace=neuroguard \
  --from-literal=DATABASE_URL="postgresql+asyncpg://..." \
  --from-literal=REDIS_URL="rediss://..." \
  --from-literal=AUTH0_DOMAIN="your.auth0.com" \
  --from-literal=FIELD_ENCRYPTION_KEY="..." \
  --from-literal=AWS_KMS_KEY_ID="alias/neuroguard-phi"

kubectl create secret generic neuroguard-web-secrets \
  --namespace=neuroguard \
  --from-literal=NEXTAUTH_SECRET="..." \
  --from-literal=AUTH0_CLIENT_SECRET="..."
```

4. **Deploy via CI/CD:**
```bash
git tag v1.0.0
git push origin v1.0.0
# GitHub Actions cd-production.yml takes over automatically
```

5. **Verify deployment:**
```bash
kubectl get pods -n neuroguard
kubectl get hpa -n neuroguard
curl https://api.neuroguard.health/api/v1/health/ping
```

---

## Environment Variables

See [`.env.example`](.env.example) for a complete list with descriptions.

**Critical variables for local dev:**

| Variable | Where to get it |
|----------|-----------------|
| `AUTH0_DOMAIN` | [Auth0 Dashboard](https://auth0.com) → Applications |
| `AUTH0_AUDIENCE` | Auth0 Dashboard → APIs |
| `FIELD_ENCRYPTION_KEY` | `python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |
| `NEXTAUTH_SECRET` | `openssl rand -hex 32` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | [Firebase Console](https://console.firebase.google.com) → Project Settings → Service Accounts |

---

## Project Structure

```
Parkinson/
├── mobile/          # Flutter 3 app (BLoC, GetIt, Dio)
├── web/             # Next.js 14 clinician dashboard
├── backend/
│   ├── shared/      # ORM models, schemas, security, config
│   ├── migrations/  # Alembic DB migrations (13 tables)
│   ├── services/    # 7 FastAPI microservices
│   └── docker/      # Dockerfiles + nginx config
├── ml/
│   ├── models/      # TCN+BiLSTM+Attention hybrid model
│   ├── federated/   # Flower FL server + AdaptiveFedAvg strategy
│   ├── inference/   # Prediction pipeline + SHAP explainer
│   └── privacy/     # Differential privacy mechanism
├── infra/
│   ├── terraform/   # AWS EKS, RDS, ElastiCache, S3, KMS
│   └── k8s/         # Kubernetes manifests (base + monitoring)
├── .github/
│   └── workflows/   # CI (test+scan) + CD (EKS deploy)
├── .env.example     # All required environment variables
└── README.md        # This file
```

---

## Security & Compliance

| Requirement | Implementation |
|-------------|----------------|
| HIPAA §164.312(b) — Audit controls | Append-only `audit_logs` table, middleware on all PHI routes |
| HIPAA §164.312(a)(2)(iv) — Encryption | AES-256-GCM field encryption, TLS 1.3 in transit |
| GDPR Article 17 — Right to erasure | Soft-delete pipeline, 30-day hard delete job |
| GDPR Article 20 — Portability | JSON/CSV export within 30 days |
| Differential Privacy | ε=0.5/round, δ=1e-5, σ=1.1 noise multiplier |
| Keystroke privacy | ONLY timing metadata captured — never actual text content |
| Role-based access | user / clinician / hospital_admin / super_admin (4-tier RBAC) |

---

## Troubleshooting

**Docker Compose won't start:**
```bash
# Check logs for a specific service
docker compose logs auth-service --tail=50

# Full reset (deletes all data!)
docker compose down -v
docker compose up -d
```

**Database migration failed:**
```bash
docker compose logs migrate
# Fix the issue, then:
docker compose restart migrate
```

**Web dashboard shows "Network Error":**
- Ensure Docker Compose is running: `docker compose ps`
- Check nginx is healthy: `curl http://localhost:8000/api/v1/health/ping`
- Verify `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `web/.env.local`

**Flutter "Connection refused" on Android emulator:**
- Use `10.0.2.2` instead of `localhost` for Android emulators
- Run: `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1`

**ML model not found:**
```bash
# Download pre-trained weights (or train from scratch)
cd ml && python training/train.py --epochs 50 --output models/neuroguard_v1.pt
```

---

## License

Proprietary — NeuroGuard Health Inc. All rights reserved.

Research basis: *Federated Learning for Early Parkinson's Disease Detection via Smartphone Keystroke Biometrics and Wearable Sleep Monitoring.*
