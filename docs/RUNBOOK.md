# RECON-X Operations Runbook

## 1. Prerequisites
- Python 3.11+ (Python 3.13 tested)
- Node.js 18+ and npm (v11+ tested)
- Docker & Docker Compose (optional for containerized production)

---

## 2. Quick Local Execution

### Run Full Test Suite (78 Automated Tests)
```bash
cd backend
python -m pytest tests/ -v
```
All 78 tests across 7 test suites pass in ~18 seconds.

### Run End-to-End Demo Script
Executes 5,000 synthetic transaction ingestion, 4-tier matching, AI investigation, policy guardrail enforcement, and empirical baseline benchmarking:
```bash
python scripts/run_demo.py
```

---

## 3. Starting the Full Stack Locally

### Step 1: Start Backend Server
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- API Swagger Documentation: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`

### Step 2: Start Frontend Application
```bash
cd frontend
npm install
npm run dev
```
- Frontend UI: `http://localhost:5173`

---

## 4. Production Docker Deployment
```bash
docker-compose up --build
```
This boots:
- PostgreSQL 16 on port 5432
- RECON-X FastAPI Backend on port 8000
- RECON-X React Frontend on port 80
