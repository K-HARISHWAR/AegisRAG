# AegisRAG - Secure Enterprise RAG Platform

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-5+-646CFF.svg)](https://vite.dev)

AegisRAG is a production-grade, secure enterprise document assistant powered by Retrieval-Augmented Generation (RAG). It combines granular Role-Based Access Control (RBAC), multi-format document ingestion (PDF, DOCX, XLSX), semantic vector search via ChromaDB, and prompt-shielded LLM generation.

---

## Key Features

- **Document Ingestion**: Multi-format extraction for PDF (page preserved), DOCX (section/paragraph preserved), and XLSX (sheet/cell range preserved).
- **Server-Verified RBAC**: PostgreSQL is the single source of truth for users, roles, departments, and document grants.
- **Two-Tier Retrieval Authorization**: Candidate chunks are filtered before vector retrieval and revalidated against PostgreSQL permissions before entering LLM context.
- **Accurate Citations & Abstention**: Answers cite exact document names and pages/sheets; abstains gracefully if ground truth evidence is absent.
- **Prompt Injection Defense**: Untrusted document content is isolated and delimited from system instructions.
- **Full Observability**: Structured logging with unique request IDs and tamper-resistant audit event recording.

---

## Architecture Overview

```text
Browser (React + TypeScript + Vite)
      │
      │ HTTPS + Bearer Token
      ▼
FastAPI Application (Modular Monolith)
  ├── Auth & Server-Side RBAC Enforcement
  ├── Document Ingestion & Parsers (PDF, DOCX, XLSX)
  ├── Retrieval Pipeline (Pre-search Filter + Post-search Revalidation)
  ├── LLM Adapter (Groq / OpenAI-compatible)
  └── Audit Event Logger
      │
      ├── PostgreSQL (Users, Roles, Departments, Document Grants, Audit)
      ├── ChromaDB (Vector Embeddings & Chunk Metadata)
      └── Storage (Local disk in development, Amazon S3 in cloud)
```

---

## Prerequisites

Before setting up AegisRAG locally, ensure the following tools are installed:

- **Git**: 2.49+
- **Python**: 3.12+ (accessible via `py -3.12` or `python`)
- **Node.js**: LTS v22+
- **npm**: v10+
- **PostgreSQL**: Local instance or Docker Compose (optional for initial setup)

---

## Local Setup Instructions

### 1. Clone & Configure Environment
```bash
git clone <repo-url> aegisrag
cd aegisrag

# Copy environment variables template
cp .env.example .env
```

### 2. Backend Setup
```powershell
# Create Python 3.12 virtual environment
py -3.12 -m venv backend/venv

# Activate virtual environment
# On Windows (PowerShell):
.\backend\venv\Scripts\Activate.ps1
# On Linux/macOS:
# source backend/venv/bin/activate

# Upgrade pip and install backend
python -m pip install --upgrade pip
pip install -e backend/

# Run backend development server
uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API will be available at:
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health/live](http://localhost:8000/health/live)

### 3. Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
The frontend interface will be available at [http://localhost:5173](http://localhost:5173).

### 4. Running Tests
```powershell
# Run backend test suite
pytest backend/tests/ -v

# Run frontend tests
cd frontend
npm test
```

---

## Implementation Roadmap

| Phase | Milestone | Status |
| :---: | :--- | :---: |
| **0** | Scope, requirements, threat model, evaluation dataset | Done |
| **1** | Repository tooling, AGENTS.md, .gitignore, environment config | **In Progress** |
| **2** | Backend skeleton, typed settings, structured logging, health checks | Upcoming |
| **3** | PostgreSQL database schema, Alembic migrations, RBAC model | Upcoming |
| **4** | Document upload, validation, and multi-format text extraction | Upcoming |
| **5** | Chunking strategies, embedding pipeline, ChromaDB vector indexing | Upcoming |
| **6** | Secure retrieval, dual-stage RBAC filtering, citation generation | Upcoming |
| **7** | React + TypeScript + Vite frontend interface & workflows | Upcoming |
| **8** | Automated evaluation (Ragas), security regression, latency benchmarks | Upcoming |
| **9** | Docker containerization & AWS cloud deployment | Upcoming |
| **10**| Hardening, portfolio documentation, and interactive demo | Upcoming |

---

## Security Policy

- All endpoints default to deny access unless explicitly granted.
- Vector store metadata is treated as an optimization index, never an authorization authority.
- API keys, credentials, and secrets must remain server-side and never leak to client or logs.
