# AegisRAG - Antigravity Agent Guidelines & Project Guardrails

Welcome to **AegisRAG**, a secure enterprise document assistant featuring Retrieval-Augmented Generation (RAG) with server-verified Role-Based Access Control (RBAC), evaluation, and cloud deployment.

## 1. Core Architectural Principles

- **Modular Monolith**: One backend application (`backend/`) with cleanly separated modules. Split services only if there is a demonstrated need.
- **PostgreSQL is the Authority**: PostgreSQL is the single source of truth for users, roles, departments, document metadata, and access grants. Vector-store metadata can filter search candidates, but **must never** be the sole authority for access control.
- **Default-Deny Policy**: All authorization checks fail closed. If a grant, role, or user status is missing, invalid, or indeterminate, access is strictly denied.
- **Two-Stage Authorization Filter**:
  1. *Pre-retrieval*: Vector search candidate querying is pre-filtered by user-authorized document IDs computed from trusted PostgreSQL records.
  2. *Post-retrieval*: Every retrieved candidate chunk is revalidated against PostgreSQL permissions before entering LLM context.
- **Untrusted Document Context**: All document content is treated as untrusted data. Prompts must be shielded against indirect prompt injection.

## 2. Directory Structure

```text
AegisRAG/
├── AGENTS.md                  # Agent workflow and security guardrails
├── README.md                  # Setup instructions and project overview
├── .gitignore                 # Excluded environments, secrets, and artifacts
├── .env.example               # Config template with placeholders only
├── docs/                      # Architectural specifications and threat model
│   ├── requirements.md        # User personas, roles, and functional specs
│   ├── architecture.md        # Component diagrams and trust boundaries
│   ├── threat-model.md        # STRIDE security analysis and checklists
│   └── implementation-log.md  # Progress record across phases
├── evals/                     # Quality evaluation and security benchmark
│   ├── questions.jsonl        # Evaluation questions with ground truth
│   └── README.md              # Evaluation execution guide
├── backend/                   # Python + FastAPI application
│   ├── app/
│   │   ├── api/routes/        # Endpoint routers
│   │   ├── core/              # Config (pydantic-settings), security, logging
│   │   ├── db/                # SQLAlchemy database session & engine
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic schemas (request/response)
│   │   ├── services/          # Business logic: documents, extraction, chunking,
│   │   │                      # embeddings, vector_store, retrieval, generation, audit
│   │   └── main.py            # FastAPI application factory
│   ├── tests/                 # pytest test suite
│   ├── alembic/               # Database migrations
│   └── pyproject.toml         # Dependencies and project packaging
├── frontend/                  # React + TypeScript + Vite application
│   ├── src/
│   │   ├── api/               # Typed API client
│   │   ├── auth/              # Auth context and token management
│   │   ├── components/        # Reusable UI components
│   │   ├── pages/             # Chat, documents, and admin dashboards
│   │   └── types/             # TypeScript definitions
│   └── package.json
└── infra/                     # Deployment configurations
    ├── docker/                # Local and production Dockerfiles
    └── aws/                   # Cloud infrastructure templates
```

## 3. Development Workflow & Commands

### Prerequisites
- Python 3.12 (`py -3.12`)
- Node.js LTS (v22+) & npm (v10+)
- Git 2.49+

### Backend Commands (PowerShell / Windows)
```powershell
# Create virtual environment
py -3.12 -m venv backend/venv

# Activate virtual environment
.\backend\venv\Scripts\Activate.ps1

# Install backend dependencies
python -m pip install --upgrade pip
pip install -e backend/

# Run backend server
uvicorn app.main:app --app-dir backend --reload --port 8000

# Run tests
pytest backend/tests/ -v
```

### Frontend Commands
```powershell
cd frontend
npm install
npm run dev
npm test
```

## 4. Security Rules & Git Protocol (Mandatory)

1. **Never Hardcode Secrets**: No API keys, passwords, private keys, or tokens in source code, commits, chat messages, or logs.
2. **Never Trust the Client**: Role, department, and permissions must be derived exclusively on the server from verified database records.
3. **Fail Closed**: Any error in authentication, authorization, or database lookup must reject the request. Never fall back to unrestricted retrieval.
4. **Sanitize Errors**: Return generic error messages to clients. Never expose stack traces or internal server details in API responses.
5. **No Dangerous Execution**: Never execute macros, active content, or untrusted code in uploaded documents.
6. **No Automatic Remote Push**: Never run `git push` automatically. After completing a phase and running tests, commit locally, summarize the changes, and notify the user so they can review and push to remote themselves.

## 5. Working Phase-by-Phase

Always follow the phased workflow:
1. **Plan**: Inspect existing files, list proposed changes, and verify prerequisites.
2. **Implement**: Keep changes minimal, modular, and well-typed.
3. **Test**: Run the test suite after every change. Never weaken tests to force a pass.
4. **Record**: Log completed tasks in `docs/implementation-log.md`.
